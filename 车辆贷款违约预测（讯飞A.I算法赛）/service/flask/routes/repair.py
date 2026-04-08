"""数据修复路由模块 - 提供信息修复相关的API"""

from __future__ import annotations

import random
from flask import Blueprint, jsonify, request


repair_bp = Blueprint("repair_bp", __name__, url_prefix="/repair")


# 模拟的关联规则（FP-Growth 挖掘结果）
MOCK_FP_RULES = [
    {"condition": {"credit_score_range": "550-650", "employment_type": "未知"},
     "result": {"employment_type": 1}, "confidence": 0.82},
    {"condition": {"credit_score_range": "650-750", "age_range": "30-40"},
     "result": {"employment_type": 1, "credit_level": 3}, "confidence": 0.88},
    {"condition": {"area_id_range": "1-5", "disbursed_amount_range": "10000-30000"},
     "result": {"employment_type": 2}, "confidence": 0.75},
    {"condition": {"credit_level": -1, "credit_score_range": "500-600"},
     "result": {"credit_level": 2}, "confidence": 0.91},
    {"condition": {"age_range": "25-35", "total_overdue_no": 0},
     "result": {"credit_level": 4}, "confidence": 0.86},
]

# 模拟的修复评估指标
MOCK_REPAIR_METRICS = {
    "fp_growth": {
        "coverage": 0.85,
        "accuracy": 0.82,
        "avg_confidence": 0.78,
        "rules_count": 156,
        "rows_repaired": 385420,
    },
    "als": {
        "rmse": 0.28,
        "mape": 0.15,
        "coverage": 0.92,
        "rows_repaired": 489230,
    },
    "overall": {
        "rows_total": 2263847,
        "rows_repaired": 874650,
        "repair_rate": 0.386,
        "repair_success_rate": 0.89,
    }
}


@repair_bp.post("/record")
def repair_record():
    """
    修复单条记录
    请求体: {"customer_id": 123, "field": "credit_score", "value": null}
    响应: {"customer_id": 123, "repaired_value": 650, "method": "FP-Growth", "confidence": 0.82}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求数据格式错误"}), 400

    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"error": "缺少客户ID"}), 400

    # 模拟修复逻辑
    missing_fields = [k for k, v in data.items() if v is None or v == ""]
    repaired = {}

    for field in missing_fields:
        if field in ["employment_type", "credit_level"]:
            # 使用 FP-Growth 规则修复
            rule = random.choice(MOCK_FP_RULES)
            repaired[field] = rule["result"].get(field, random.choice([1, 2, 3]))
            repaired[f"{field}_confidence"] = rule["confidence"]
            repaired[f"{field}_method"] = "FP-Growth"
        elif field in ["credit_score", "disbursed_amount", "total_outstanding_loan"]:
            # 使用 ALS 矩阵分解修复
            if field == "credit_score":
                repaired[field] = 580 + random.randint(0, 150)
            elif field == "disbursed_amount":
                repaired[field] = 10000 + random.randint(0, 50000)
            else:
                repaired[field] = 5000 + random.randint(0, 30000)
            repaired[f"{field}_method"] = "ALS"
            repaired[f"{field}_rmse"] = round(random.uniform(0.2, 0.4), 2)

    return jsonify({
        "customer_id": customer_id,
        "repaired_fields": repaired,
        "repair_info": {
            "total_repaired": len(repaired),
            "method_used": "FP-Growth + ALS",
            "timestamp": "2026-04-08T12:00:00"
        }
    })


@repair_bp.get("/evaluation")
def repair_evaluation():
    """
    获取修复效果评估数据
    响应: 包含 FP-Growth 和 ALS 两套算法的评估指标
    """
    return jsonify(MOCK_REPAIR_METRICS)


@repair_bp.get("/metrics")
def repair_metrics():
    """
    获取修复相关指标（用于看板展示）
    """
    metrics = MOCK_REPAIR_METRICS["overall"]
    fp = MOCK_REPAIR_METRICS["fp_growth"]
    als = MOCK_REPAIR_METRICS["als"]

    return jsonify({
        "total_customers": metrics["rows_total"],
        "repaired_count": metrics["rows_repaired"],
        "repair_rate": round(metrics["repair_rate"] * 100, 1),
        "repair_success_rate": round(metrics["repair_success_rate"] * 100, 1),
        "fp_growth": {
            "coverage": round(fp["coverage"] * 100, 1),
            "accuracy": round(fp["accuracy"] * 100, 1),
            "rules_count": fp["rules_count"],
            "rows_repaired": fp["rows_repaired"],
        },
        "als": {
            "coverage": round(als["coverage"] * 100, 1),
            "rmse": als["rmse"],
            "mape": round(als["mape"] * 100, 1),
            "rows_repaired": als["rows_repaired"],
        }
    })


@repair_bp.get("/rules")
def repair_rules():
    """
    获取 FP-Growth 挖掘的关联规则列表
    """
    return jsonify({
        "rules": MOCK_FP_RULES,
        "total_count": len(MOCK_FP_RULES),
    })
