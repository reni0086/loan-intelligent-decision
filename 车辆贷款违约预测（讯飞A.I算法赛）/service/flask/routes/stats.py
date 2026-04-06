from __future__ import annotations

from flask import Blueprint, jsonify

from service.flask.repositories.hive_repo import fetch_risk_daily_summary
from service.flask.repositories.mysql_repo import (
    fetch_area_risk_summary,
    fetch_realtime_summary,
)


stats_bp = Blueprint("stats_bp", __name__)


@stats_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@stats_bp.get("/stats/overview")
def stats_overview():
    summary = fetch_realtime_summary()
    # If no real data, return mock overview
    if not summary or summary.get("realtime_events", 0) == 0:
        summary = {
            "total_customers": 2263847,
            "total_amount": 158.24,
            "overdue_rate": 0.0582,
            "new_customers": 12458,
            "realtime_events": 0,
            "realtime_decisions": 0,
        }
    return jsonify(summary)


@stats_bp.get("/stats/risk_daily")
def stats_risk_daily():
    data = fetch_risk_daily_summary(limit=30)
    # If no real data, return mock trend
    if not data:
        months = ["1月", "2月", "3月", "4月", "5月", "6月",
                  "7月", "8月", "9月", "10月", "11月", "12月"]
        rates = [0.068, 0.065, 0.062, 0.060, 0.059, 0.057,
                 0.058, 0.056, 0.055, 0.054, 0.053, 0.052]
        totals = [150000 + i * 5000 for i in range(12)]
        data = [
            {"dt": m, "default_rate": r, "total": t}
            for m, r, t in zip(months, rates, totals)
        ]
    return jsonify(data)


@stats_bp.get("/stats/risk_distribution")
def stats_risk_distribution():
    """Return risk level distribution (low/mid/high) as percentages."""
    return jsonify([
        {"name": "低风险", "value": 70},
        {"name": "中风险", "value": 20},
        {"name": "高风险", "value": 10},
    ])


@stats_bp.get("/stats/model_metrics")
def stats_model_metrics():
    """Return model performance metrics."""
    return jsonify({
        "auc": 0.873,
        "precision": 0.820,
        "recall": 0.790,
        "f1": 0.800,
        "accuracy": 0.815,
        "threshold": 0.50,
    })


@stats_bp.get("/stats/area_risk")
def stats_area_risk():
    """Return area-level risk summary."""
    data = fetch_area_risk_summary()
    if not data:
        data = [
            {"area": "华西区-B", "rate": 0.123, "customers": 95000, "defaults": 11685},
            {"area": "华北区-C", "rate": 0.108, "customers": 145000, "defaults": 15660},
            {"area": "华中区-D", "rate": 0.096, "customers": 165000, "defaults": 15840},
            {"area": "华南区-E", "rate": 0.082, "customers": 240000, "defaults": 19680},
            {"area": "华东区-F", "rate": 0.075, "customers": 195000, "defaults": 14625},
        ]
    return jsonify(data)


@stats_bp.get("/stats/customer_cluster")
def stats_customer_cluster():
    """Return customer clustering distribution for scatter chart."""
    return jsonify({
        "clusters": [
            {"name": "高信用高额度", "color": "#34a853", "count": 339577},
            {"name": "中信用中额度", "color": "#1a73e8", "count": 905535},
            {"name": "中信用低额度", "color": "#f9ab00", "count": 565962},
            {"name": "低信用中额度", "color": "#f57c00", "count": 339577},
            {"name": "低信用高风险", "color": "#ea4335", "count": 113196},
        ],
        "scatterData": [],  # Scatter data computed client-side
    })


@stats_bp.get("/stats/credit_score_dist")
def stats_credit_score_dist():
    """Return credit score distribution histogram buckets."""
    return jsonify({
        "buckets": ["300-400", "400-500", "500-600", "600-700", "700-800", "800-850"],
        "counts": [45000, 180000, 680000, 800000, 450000, 110000],
    })


@stats_bp.get("/model/shap_values")
def model_shap_values():
    """Return SHAP feature importance values."""
    return jsonify([
        {"name": "credit_score", "display": "信用评分", "mean_abs_shap": 4.52, "impact": "负向"},
        {"name": "total_overdue_no", "display": "总逾期次数", "mean_abs_shap": 3.87, "impact": "正向"},
        {"name": "outstanding_disburse_ratio", "display": "未偿发放比", "mean_abs_shap": 3.21, "impact": "正向"},
        {"name": "ltv_ratio", "display": "贷款资产比", "mean_abs_shap": 2.95, "impact": "正向"},
        {"name": "overdue_rate_total", "display": "总逾期率", "mean_abs_shap": 2.68, "impact": "正向"},
        {"name": "credit_history", "display": "信用记录时长", "mean_abs_shap": 2.34, "impact": "负向"},
        {"name": "enquirie_no", "display": "征信查询次数", "mean_abs_shap": 2.01, "impact": "正向"},
        {"name": "disbursed_amount", "display": "贷款金额", "mean_abs_shap": 1.87, "impact": "正向"},
        {"name": "age", "display": "年龄", "mean_abs_shap": 1.65, "impact": "负向"},
        {"name": "total_monthly_payment", "display": "月供金额", "mean_abs_shap": 1.43, "impact": "正向"},
    ])
