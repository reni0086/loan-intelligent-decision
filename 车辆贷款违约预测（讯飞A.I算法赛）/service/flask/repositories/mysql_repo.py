from __future__ import annotations

import pymysql

from service.flask.config import Settings


def _connect(db_name: str):
    return pymysql.connect(
        host=Settings.MYSQL_HOST,
        port=Settings.MYSQL_PORT,
        user=Settings.MYSQL_USER,
        password=Settings.MYSQL_PASSWORD,
        database=db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def insert_realtime_decision(row: dict) -> None:
    conn = _connect(Settings.MYSQL_DB_RT)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO realtime_decisions
                (customer_id, default_probability, default_pred, fraud_probability, fraud_pred, predicted_limit, credit_score)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    row.get("customer_id"),
                    row.get("default_probability"),
                    row.get("default_pred"),
                    row.get("fraud_probability"),
                    row.get("fraud_pred"),
                    row.get("predicted_limit"),
                    row.get("credit_score"),
                ),
            )
    finally:
        conn.close()


def fetch_realtime_summary() -> dict:
    conn = _connect(Settings.MYSQL_DB_RT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM realtime_events")
            events = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM realtime_decisions")
            decisions = cur.fetchone()["c"]
            return {"realtime_events": int(events), "realtime_decisions": int(decisions)}
    finally:
        conn.close()


def fetch_customer_profile(customer_id: int) -> dict | None:
    """Fetch customer basic info from MySQL. Returns None if not found."""
    conn = _connect(Settings.MYSQL_DB_ODS)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.*, l.disbursed_amount, l.asset_cost, l.total_overdue_no,
                       l.total_disbursed_loan, l.total_monthly_payment
                FROM customer_profile c
                LEFT JOIN loan_fact l ON c.customer_id = l.customer_id
                WHERE c.customer_id = %s
                LIMIT 1
                """,
                (customer_id,),
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            return None
    finally:
        conn.close()


def fetch_customer_similar(customer_id: int, k: int = 5) -> list[dict] | None:
    """Fetch similar customers from MySQL. Returns None if table not available."""
    conn = _connect(Settings.MYSQL_DB_ODS)
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT customer_id, credit_score, disbursed_amount,
                       total_overdue_no, loan_default AS actual_default
                FROM customer_profile c
                LEFT JOIN loan_fact l ON c.customer_id = l.customer_id
                WHERE c.customer_id != %s
                ORDER BY ABS(credit_score - (
                    SELECT credit_score FROM customer_profile WHERE customer_id = %s
                )) ASC
                LIMIT {int(k)}
            """, (customer_id, customer_id))
            rows = cur.fetchall()
            if rows:
                result = []
                for r in rows:
                    rd = dict(r)
                    rd["actual_performance"] = "正常还款" if not rd.get("actual_default") else "部分违约"
                    rd["similarity"] = 0.90
                    result.append(rd)
                return result
            return None
    except Exception:
        return None
    finally:
        conn.close()


def fetch_area_risk_summary() -> list[dict]:
    """Fetch area-level risk summary."""
    conn = _connect(Settings.MYSQL_DB_ODS)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.area_id AS area_id,
                    COUNT(*) AS customer_count,
                    SUM(IF(l.loan_default=1,1,0)) AS default_count,
                    AVG(c.credit_score) AS avg_credit_score,
                    SUM(l.disbursed_amount) AS total_amount
                FROM customer_profile c
                LEFT JOIN loan_fact l ON c.customer_id = l.customer_id
                GROUP BY c.area_id
                ORDER BY default_count / COUNT(*) DESC
                LIMIT 20
            """)
            rows = cur.fetchall()
            area_names = {
                1: '华东区', 2: '华东区', 3: '华北区', 4: '华北区',
                5: '华南区', 6: '华南区', 7: '华中区', 8: '华中区',
                9: '华西区', 10: '西北区',
            }
            result = []
            for r in rows:
                rd = dict(r)
                rate = rd["default_count"] / rd["customer_count"] if rd["customer_count"] else 0
                area_label = area_names.get(rd["area_id"], f"地区{rd['area_id']}")
                result.append({
                    "area": area_label,
                    "rate": round(rate, 4),
                    "customers": int(rd["customer_count"]),
                    "defaults": int(rd["default_count"]),
                    "avg_score": round(float(rd["avg_credit_score"] or 0), 1),
                    "total_amount": round(float(rd["total_amount"] or 0), 2),
                })
            return result
    except Exception:
        return []
    finally:
        conn.close()
