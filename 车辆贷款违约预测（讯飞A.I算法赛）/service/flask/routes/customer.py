"""Customer profile routes."""

from __future__ import annotations

import json
import math
from datetime import datetime

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify

from service.flask.model_loader import predict_default, predict_fraud, predict_limit, score_credit
from service.flask.repositories.mysql_repo import fetch_customer_profile, fetch_customer_similar

customer_bp = Blueprint("customer_bp", __name__, url_prefix="/customer")


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0 or math.isnan(b) or math.isnan(a):
        return default
    return a / b


def _compute_radar_scores(profile: dict) -> dict:
    """Compute 5-dimension radar chart scores for a customer."""
    credit_score = float(profile.get("credit_score") or 0)

    # Dimension 1: 信用评分 (0-850 -> 0-100 scaled)
    credit_dim = min(credit_score / 8.5, 100)

    # Dimension 2: 还款能力 (基于债务收入比)
    disbursed = float(profile.get("disbursed_amount") or 0)
    outstanding = float(profile.get("total_outstanding_loan") or 0)
    asset_cost = float(profile.get("asset_cost") or 1)
    ratio = _safe_div(outstanding, disbursed if disbursed else asset_cost)
    repay_ability = max(0, min(100, 100 - ratio * 80))

    # Dimension 3: 资产状况 (基于贷款资产比)
    ltv = _safe_div(disbursed, asset_cost)
    asset_status = max(0, min(100, 100 - (ltv - 0.5) * 100))

    # Dimension 4: 历史记录 (基于逾期次数和逾期率)
    overdue_no = float(profile.get("total_overdue_no") or 0)
    account_no = float(profile.get("total_account_loan_no") or 1)
    overdue_rate = _safe_div(overdue_no, account_no)
    history_score = max(0, min(100, 100 - overdue_no * 15 - overdue_rate * 40))

    # Dimension 5: 稳定性 (基于年龄和工作类型)
    age = float(profile.get("age") or 35)
    emp_type = int(profile.get("employment_type") or 0)
    stability = max(0, min(100, 100 - abs(age - 40) * 1.5 - (emp_type == 2) * 10))

    return {
        "credit": round(credit_dim, 2),
        "repay_ability": round(repay_ability, 2),
        "asset_status": round(asset_status, 2),
        "history": round(history_score, 2),
        "stability": round(stability, 2),
    }


def _build_mock_profile(customer_id: int) -> dict:
    """Generate deterministic mock profile for demo purposes."""
    rng_seed = customer_id % 1000
    np.random.seed(rng_seed)

    base_score = 500 + rng_seed
    overdue_count = rng_seed % 5

    profile = {
        "customer_id": customer_id,
        "age": 25 + (rng_seed % 40),
        "employment_type": rng_seed % 3,
        "area_id": rng_seed % 10,
        "credit_score": base_score,
        "disbursed_amount": 10000 + (rng_seed % 80000),
        "total_outstanding_loan": 5000 + (rng_seed % 30000),
        "asset_cost": 15000 + (rng_seed % 100000),
        "total_overdue_no": overdue_count,
        "total_account_loan_no": 1 + (rng_seed % 6),
        "main_account_overdue_no": overdue_count,
        "main_account_loan_no": 1 + (rng_seed % 4),
        "total_monthly_payment": 500 + (rng_seed % 3000),
        "total_disbursed_loan": 10000 + (rng_seed % 80000),
        "last_six_month_new_loan_no": rng_seed % 3,
        "last_six_month_defaulted_no": overdue_count % 2,
        "credit_history": 1 + (rng_seed % 10),
        "enquirie_no": rng_seed % 8,
        "loan_default": 1 if rng_seed % 7 == 0 else 0,
    }
    return profile


def _build_mock_timeline(customer_id: int) -> list[dict]:
    """Generate mock loan timeline for demo."""
    rng_seed = customer_id % 1000
    np.random.seed(rng_seed)

    events = [
        {
            "date": f"2024-{1 + rng_seed % 11:02d}-15",
            "type": "loan-apply",
            "title": "提交贷款申请",
            "detail": f"申请金额: {10000 + (rng_seed % 50000):,}元, 用途: 购车",
        },
        {
            "date": f"2024-{2 + rng_seed % 11:02d}-18",
            "type": "loan-disbursed",
            "title": "贷款发放",
            "detail": f"实际发放: {10000 + (rng_seed % 50000):,}元, 利率: {5.5 + (rng_seed % 5):.1f}%, 期限: {12 + (rng_seed % 4) * 12}期",
        },
    ]

    months = 3 + rng_seed % 10
    for m in range(months):
        month = 3 + m + rng_seed % 9
        if month > 12:
            month -= 12
        if m == overdue_count if 'overdue_count' in dir() else False:
            events.append({
                "date": f"2024-{month:02d}-{10 + rng_seed % 15:02d}",
                "type": "overdue",
                "title": "逾期还款",
                "detail": f"逾期{1 + rng_seed % 7}天, 罚款: {50 + rng_seed * 5}元, 已补缴",
            })
        else:
            events.append({
                "date": f"2024-{month:02d}-{10 + rng_seed % 15:02d}",
                "type": "ontime-repay",
                "title": "按时还款",
                "detail": f"本期还款: {300 + rng_seed * 100:,}元",
            })

    overdue_count = rng_seed % 5
    if rng_seed % 3 == 0:
        events.append({
            "date": f"2025-{1 + rng_seed % 3:02d}-10",
            "type": "closed",
            "title": "贷款结清",
            "detail": "全部本金还清，结清证明已生成",
        })

    return events


@customer_bp.get("/<int:customer_id>/profile")
def get_customer_profile(customer_id: int):
    """Return complete customer profile with radar scores."""
    # Try to fetch from MySQL first
    db_profile = fetch_customer_profile(customer_id)

    if db_profile:
        profile = db_profile
    else:
        # Fall back to mock data for demo
        profile = _build_mock_profile(customer_id)

    # Compute radar chart scores
    radar = _compute_radar_scores(profile)

    # Get prediction results
    try:
        pred_default = predict_default([profile])
        pred_fraud = predict_fraud([profile])
        pred_limit = predict_limit([profile])

        default_prob = pred_default[0]["default_probability"] if pred_default else 0.0
        fraud_prob = pred_fraud[0]["fraud_probability"] if pred_fraud else 0.0
        limit_val = pred_limit[0]["predicted_limit"] if pred_limit else 0.0
        credit_score_val = score_credit([default_prob])[0]
    except Exception:
        # Fallback mock predictions
        base_prob = (1000 - (customer_id % 1000)) / 1000.0
        default_prob = max(0.01, min(0.99, base_prob))
        fraud_prob = max(0.01, min(0.5, (customer_id % 50) / 100))
        limit_val = 10000 + (customer_id % 80000)
        credit_score_val = 600 - 50 * math.log(default_prob / (1 - default_prob))

    result = {
        "customer_id": customer_id,
        "profile": {
            "age": profile.get("age"),
            "employment_type": profile.get("employment_type"),
            "area_id": profile.get("area_id"),
            "credit_score": profile.get("credit_score"),
            "disbursed_amount": profile.get("disbursed_amount"),
            "total_overdue_no": profile.get("total_overdue_no"),
            "total_account_loan_no": profile.get("total_account_loan_no"),
            "loan_default": profile.get("loan_default"),
        },
        "radar_scores": radar,
        "decision": {
            "default_probability": round(default_prob, 4),
            "default_pred": 1 if default_prob >= 0.5 else 0,
            "fraud_probability": round(fraud_prob, 4),
            "fraud_pred": 1 if fraud_prob >= 0.5 else 0,
            "predicted_limit": round(limit_val, 2),
            "credit_score": round(credit_score_val, 1),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    return jsonify(result)


@customer_bp.get("/<int:customer_id>/similar")
def get_similar_customers(customer_id: int):
    """Return Top-K similar customers based on feature cosine similarity."""
    db_similar = fetch_customer_similar(customer_id, k=5)

    if db_similar:
        return jsonify(db_similar)

    # Generate mock similar customers for demo
    rng_seed = customer_id % 1000
    np.random.seed(rng_seed)

    # Create mock target profile
    target_score = 500 + rng_seed
    target_overdue = rng_seed % 5

    similar = []
    for i in range(5):
        offset = (i + 1) * 5
        sim_id = customer_id + offset * 100
        sim_score = max(300, min(850, target_score + np.random.randint(-30, 30)))
        sim_overdue = max(0, min(5, target_overdue + np.random.randint(-1, 1)))

        default_actual = 1 if sim_overdue >= 3 else 0
        performance = "正常还款" if default_actual == 0 else "部分违约"
        similarity = max(0.70, 0.99 - i * 0.04 - abs(sim_score - target_score) / 1000)

        similar.append({
            "customer_id": int(sim_id),
            "credit_score": int(sim_score),
            "disbursed_amount": float(10000 + (sim_id % 80000)),
            "total_overdue_no": int(sim_overdue),
            "actual_default": int(default_actual),
            "actual_performance": performance,
            "similarity": round(similarity, 4),
        })

    return jsonify(similar)


@customer_bp.get("/<int:customer_id>/loan_history")
def get_customer_loan_history(customer_id: int):
    """Return loan behavior timeline for a customer."""
    timeline = _build_mock_timeline(customer_id)
    return jsonify({
        "customer_id": customer_id,
        "events": timeline,
        "total_events": len(timeline),
    })
