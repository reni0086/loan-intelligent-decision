import json
import secrets
import sqlite3
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from flask import (Blueprint, Flask, jsonify, redirect,
                   render_template_string, request,
                   send_from_directory, session)
from flask_login import login_required, login_user, logout_user

from features_v2 import add_features
from src.auth import AuthUser, setup_login_manager, validate_login
from src.config import ProjectConfig, get_config
from src.decision import score_from_probability
from src.ingest_storage import consume_queue_once


def _load_bundle(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Artifact missing: {path}")
    return joblib.load(path)


def _append_monitoring(cfg: ProjectConfig, payload: dict) -> None:
    cfg.monitoring_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.monitoring_dir / "metrics.log"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _predict_default(cfg: ProjectConfig, records: list[dict]) -> list[dict]:
    bundle = _load_bundle(cfg.artifacts_dir / "default_model.joblib")
    model = bundle["model"]
    cols = bundle["feature_cols"]
    df = pd.DataFrame(records)
    df = add_features(df).replace([np.inf, -np.inf], np.nan)
    x = df.reindex(columns=cols)
    proba = model.predict_proba(x)[:, 1]
    score = score_from_probability(proba)
    out = []
    for i, p in enumerate(proba):
        out.append(
            {
                "customer_id": records[i].get("customer_id"),
                "default_probability": float(p),
                "default_pred": int(p >= 0.5),
                "credit_score": float(score[i]),
            }
        )
    return out


def _predict_fraud(cfg: ProjectConfig, records: list[dict]) -> list[dict]:
    bundle = _load_bundle(cfg.artifacts_dir / "fraud_model.joblib")
    model = bundle["model"]
    cols = bundle["feature_cols"]
    df = pd.DataFrame(records)
    df = add_features(df).replace([np.inf, -np.inf], np.nan)
    x = df.reindex(columns=cols)
    proba = model.predict_proba(x)[:, 1]
    return [
        {
            "customer_id": records[i].get("customer_id"),
            "fraud_probability": float(proba[i]),
            "fraud_pred": int(proba[i] >= 0.5),
        }
        for i in range(len(records))
    ]


def _predict_limit(cfg: ProjectConfig, records: list[dict]) -> list[dict]:
    bundle = _load_bundle(cfg.artifacts_dir / "limit_model.joblib")
    model = bundle["model"]
    cols = bundle["feature_cols"]
    fill_values = bundle.get("fill_values", {})
    df = pd.DataFrame(records)
    df = add_features(df).replace([np.inf, -np.inf], np.nan)
    x = df.reindex(columns=cols).fillna(fill_values).fillna(0)
    pred = model.predict(x)
    return [
        {
            "customer_id": records[i].get("customer_id"),
            "predicted_limit": float(max(0.0, pred[i])),
            "model_name": bundle.get("best_model_name", "unknown"),
        }
        for i in range(len(records))
    ]


def run_micro_batch_worker(
    cfg: ProjectConfig,
    iterations: int = 5,
    batch_size: int = 200,
    interval_sec: float = 1.0,
) -> dict:
    total_processed = 0
    batch_latencies = []
    cfg.monitoring_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(cfg.sqlite_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS realtime_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            default_probability REAL,
            default_pred INTEGER,
            credit_score REAL,
            predicted_limit REAL,
            fraud_probability REAL,
            fraud_pred INTEGER,
            created_at TEXT
        )
        """
    )
    conn.commit()

    for _ in range(iterations):
        consumed = consume_queue_once(cfg, batch_size=batch_size)
        if consumed <= 0:
            time.sleep(interval_sec)
            continue

        start = time.time()
        events = pd.read_sql_query(
            f"SELECT * FROM realtime_events ORDER BY event_id DESC LIMIT {consumed}", conn
        )
        records = [json.loads(x) for x in events["payload_json"].tolist()]

        default_out = _predict_default(cfg, records)
        fraud_out = _predict_fraud(cfg, records)
        limit_out = _predict_limit(cfg, records)

        now = datetime.now().isoformat(timespec="seconds")
        rows = []
        for i in range(len(records)):
            rows.append(
                {
                    "customer_id": default_out[i]["customer_id"],
                    "default_probability": default_out[i]["default_probability"],
                    "default_pred": default_out[i]["default_pred"],
                    "credit_score": default_out[i]["credit_score"],
                    "predicted_limit": limit_out[i]["predicted_limit"],
                    "fraud_probability": fraud_out[i]["fraud_probability"],
                    "fraud_pred": fraud_out[i]["fraud_pred"],
                    "created_at": now,
                }
            )
        pd.DataFrame(rows).to_sql("realtime_decisions", conn, if_exists="append", index=False)

        elapsed = time.time() - start
        total_processed += len(rows)
        batch_latencies.append(elapsed)
        _append_monitoring(
            cfg,
            {
                "ts": now,
                "batch_size": len(rows),
                "latency_sec": round(elapsed, 4),
                "throughput_per_sec": round(len(rows) / max(elapsed, 1e-6), 2),
            },
        )
        time.sleep(interval_sec)

    conn.close()
    avg_latency = float(np.mean(batch_latencies)) if batch_latencies else 0.0
    return {"total_processed": total_processed, "avg_latency_sec": avg_latency}


def create_app(cfg: ProjectConfig | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app_cfg = cfg or get_config()

    # 初始化登录管理器
    setup_login_manager(app, app_cfg)

    # ---- 登录 / 登出 路由 ----
    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password", "")
            user = validate_login(app_cfg, username, password)
            if user:
                login_user(user)
                next_url = request.args.get("next", "/dashboard/index.html")
                return redirect(next_url)
            return render_template_string(_LOGIN_TEMPLATE, error="用户名或密码错误"), 401
        return render_template_string(_LOGIN_TEMPLATE, error=None)

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect("/login")

    @app.route("/api/auth/status")
    def auth_status():
        from flask_login import current_user
        if current_user.is_authenticated:
            return jsonify({
                "authenticated": True,
                "username": current_user.username,
                "role": current_user.role,
            })
        return jsonify({"authenticated": False})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "time": datetime.now().isoformat(timespec="seconds")})

    @app.post("/predict/default")
    @login_required
    def predict_default():
        data = request.get_json(force=True)
        records = data if isinstance(data, list) else [data]
        result = _predict_default(app_cfg, records)
        return jsonify(result)

    @app.post("/predict/fraud")
    @login_required
    def predict_fraud():
        data = request.get_json(force=True)
        records = data if isinstance(data, list) else [data]
        result = _predict_fraud(app_cfg, records)
        return jsonify(result)

    @app.post("/predict/limit")
    @login_required
    def predict_limit():
        data = request.get_json(force=True)
        records = data if isinstance(data, list) else [data]
        result = _predict_limit(app_cfg, records)
        return jsonify(result)

    @app.post("/score/credit")
    @login_required
    def score_credit():
        data = request.get_json(force=True)
        probs = np.array(data["default_probability"], dtype=float)
        scores = score_from_probability(probs)
        return jsonify({"credit_score": scores.tolist()})

    @app.post("/repair/record")
    @login_required
    def repair_record():
        data = request.get_json(force=True)
        rec = data.copy()
        defaults = {
            "credit_score": 650,
            "Credit_level": 2,
            "total_monthly_payment": 0,
            "total_outstanding_loan": 0,
        }
        for k, v in defaults.items():
            if k not in rec or rec[k] is None:
                rec[k] = v
        return jsonify(rec)

    @app.get("/stats/overview")
    @login_required
    def stats_overview():
        conn = sqlite3.connect(app_cfg.sqlite_path)
        try:
            decisions = pd.read_sql_query("SELECT COUNT(*) AS c FROM realtime_decisions", conn)["c"].iloc[0]
        except Exception:
            decisions = 0
        try:
            events = pd.read_sql_query("SELECT COUNT(*) AS c FROM realtime_events", conn)["c"].iloc[0]
        except Exception:
            events = 0
        conn.close()
        return jsonify({"realtime_events": int(events), "realtime_decisions": int(decisions)})

    @app.get("/stats/risk_daily")
    @login_required
    def stats_risk_daily():
        conn = sqlite3.connect(app_cfg.sqlite_path)
        try:
            df = pd.read_sql_query(
                """
                SELECT DATE(created_at) AS dt,
                       COUNT(*) AS total,
                       SUM(default_pred) AS defaults
                FROM realtime_decisions
                WHERE created_at IS NOT NULL
                GROUP BY DATE(created_at)
                ORDER BY dt DESC
                LIMIT 30
                """,
                conn,
            )
            rows = [
                {"dt": r["dt"], "total": int(r["total"]), "default_rate": round(r["defaults"] / r["total"], 4)}
                for _, r in df.iterrows()
            ]
        except Exception:
            rows = []
        conn.close()
        return jsonify(rows)

    @app.get("/")
    @login_required
    def dashboard():
        dashboard_dir = app_cfg.base_dir / "dashboard"
        return send_from_directory(dashboard_dir, "index.html")

    @app.get("/dashboard/<path:filename>")
    @login_required
    def dashboard_assets(filename: str):
        dashboard_dir = app_cfg.base_dir / "dashboard"
        return send_from_directory(dashboard_dir, filename)

    return app


# ---------------------------------------------------------------------------
# 内嵌登录页面模板（无需额外文件）
# ---------------------------------------------------------------------------
_LOGIN_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>贷款智能决策系统 — 登录</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #0f1628;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh;
    }
    .login-box {
      background: #1a2238;
      border: 1px solid #2a3858;
      border-radius: 16px;
      padding: 48px 40px;
      width: 400px;
      box-shadow: 0 20px 60px rgba(0,0,0,.5);
    }
    .login-box h2 {
      color: #e8f0fe;
      text-align: center;
      margin-bottom: 8px;
      font-size: 22px; font-weight: 600;
    }
    .login-box p {
      color: #8a9cc2;
      text-align: center;
      margin-bottom: 32px;
      font-size: 13px;
    }
    .form-group { margin-bottom: 20px; }
    .form-group label {
      display: block;
      color: #8a9cc2;
      font-size: 13px;
      margin-bottom: 6px;
    }
    .form-group input {
      width: 100%;
      padding: 10px 14px;
      background: #0f1628;
      border: 1px solid #2a3858;
      border-radius: 8px;
      color: #e8f0fe;
      font-size: 14px;
      outline: none;
      transition: border-color .2s;
    }
    .form-group input:focus { border-color: #4a7dff; }
    .btn-login {
      width: 100%;
      padding: 12px;
      background: #4a7dff;
      border: none;
      border-radius: 8px;
      color: #fff;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: background .2s;
    }
    .btn-login:hover { background: #3a6cf0; }
    .error-msg {
      background: rgba(255,80,80,.15);
      border: 1px solid rgba(255,80,80,.4);
      border-radius: 8px;
      color: #ff7070;
      padding: 10px 14px;
      font-size: 13px;
      margin-bottom: 20px;
    }
    .hint {
      margin-top: 24px;
      text-align: center;
      font-size: 12px;
      color: #4a5880;
    }
    .hint span { color: #4a7dff; }
  </style>
</head>
<body>
  <div class="login-box">
    <h2>贷款智能决策系统</h2>
    <p>请输入账号密码登录</p>
    {% if error %}
    <div class="error-msg">{{ error }}</div>
    {% endif %}
    <form method="post" autocomplete="off">
      <div class="form-group">
        <label>用户名</label>
        <input type="text" name="username" placeholder="请输入用户名" required autofocus>
      </div>
      <div class="form-group">
        <label>密码</label>
        <input type="password" name="password" placeholder="请输入密码" required>
      </div>
      <button type="submit" class="btn-login">登 录</button>
    </form>
    <p class="hint">默认账号: <span>admin</span> / <span>admin123</span></p>
  </div>
</body>
</html>"""
