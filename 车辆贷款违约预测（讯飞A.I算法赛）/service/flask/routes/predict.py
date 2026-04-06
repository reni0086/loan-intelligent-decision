from __future__ import annotations

from flask import Blueprint, jsonify, request

from service.flask.model_loader import predict_default, predict_fraud, predict_limit, score_credit
from service.flask.repositories.mysql_repo import insert_realtime_decision


predict_bp = Blueprint("predict_bp", __name__)


@predict_bp.post("/predict/default")
def api_predict_default():
    payload = request.get_json(force=True)
    records = payload if isinstance(payload, list) else [payload]
    result = predict_default(records)
    return jsonify(result)


@predict_bp.post("/predict/fraud")
def api_predict_fraud():
    payload = request.get_json(force=True)
    records = payload if isinstance(payload, list) else [payload]
    result = predict_fraud(records)
    return jsonify(result)


@predict_bp.post("/predict/limit")
def api_predict_limit():
    payload = request.get_json(force=True)
    records = payload if isinstance(payload, list) else [payload]
    result = predict_limit(records)
    return jsonify(result)


@predict_bp.post("/predict/full")
def api_predict_full():
    payload = request.get_json(force=True)
    records = payload if isinstance(payload, list) else [payload]
    defaults = predict_default(records)
    frauds = predict_fraud(records)
    limits = predict_limit(records)
    merged = []
    for i in range(len(records)):
        item = {
            "customer_id": records[i].get("customer_id"),
            "default_probability": defaults[i]["default_probability"],
            "default_pred": defaults[i]["default_pred"],
            "fraud_probability": frauds[i]["fraud_probability"],
            "fraud_pred": frauds[i]["fraud_pred"],
            "predicted_limit": limits[i]["predicted_limit"],
        }
        item["credit_score"] = score_credit([item["default_probability"]])[0]
        insert_realtime_decision(item)
        merged.append(item)
    return jsonify(merged)


@predict_bp.post("/score/credit")
def api_score_credit():
    payload = request.get_json(force=True)
    probs = payload["default_probability"]
    return jsonify({"credit_score": score_credit(probs)})
