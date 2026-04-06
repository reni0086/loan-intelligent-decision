from __future__ import annotations

from pyhive import hive

from service.flask.config import Settings


def _connect():
    return hive.Connection(
        host=Settings.HIVE_HOST,
        port=Settings.HIVE_PORT,
        username=Settings.HIVE_USERNAME,
        database=Settings.HIVE_DATABASE,
    )


def fetch_risk_daily_summary(limit: int = 30) -> list[dict]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT dt, total_customers, avg_credit_score, default_rate, avg_disbursed_amount
            FROM risk_daily_summary
            ORDER BY dt DESC
            LIMIT {int(limit)}
            """
        )
        cols = [x[0] for x in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()
