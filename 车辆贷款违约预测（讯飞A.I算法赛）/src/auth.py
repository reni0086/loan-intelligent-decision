"""
用户认证模块。
提供基于 Flask-Login 的会话认证，用户数据存储在 SQLite 中。
"""

import secrets
import sqlite3
from dataclasses import dataclass

from flask_login import LoginManager, UserMixin, current_user
from werkzeug.security import check_password_hash, generate_password_hash


@dataclass
class AuthUser(UserMixin):
    """Flask-Login 兼容的用户对象。"""
    user_id: int
    username: str
    role: str  # 'admin' | 'analyst' | 'viewer'

    def get_id(self) -> str:
        return str(self.user_id)


def _conn(cfg) -> sqlite3.Connection:
    return sqlite3.connect(cfg.sqlite_path)


def _ensure_user_table(cfg) -> None:
    """确保 users 表存在，不存在则自动创建。"""
    with _conn(cfg) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    UNIQUE NOT NULL,
                password_hash TEXT  NOT NULL,
                role       TEXT    NOT NULL DEFAULT 'viewer',
                created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                is_active  INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.commit()


def init_default_user(cfg, username: str = "admin", password: str = "admin123") -> None:
    """
    若数据库中没有用户，则创建默认管理员账号。
    已在 ingest_storage.py 的初始化流程中调用，无需单独运行。
    """
    _ensure_user_table(cfg)
    with _conn(cfg) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] > 0:
            return  # 已有用户，跳过

        pwd_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, pwd_hash, "admin"),
        )
        conn.commit()


def validate_login(cfg, username: str, password: str) -> AuthUser | None:
    """验证用户名和密码，返回 AuthUser 或 None。"""
    _ensure_user_table(cfg)
    with _conn(cfg) as conn:
        row = conn.execute(
            "SELECT user_id, username, password_hash, role, is_active FROM users WHERE username = ? AND is_active = 1",
            (username,),
        ).fetchone()

    if row is None:
        return None

    user_id, uname, pwd_hash, role, is_active = row
    if not check_password_hash(pwd_hash, password):
        return None

    return AuthUser(user_id=user_id, username=uname, role=role)


def setup_login_manager(app, cfg) -> LoginManager:
    """将 LoginManager 绑定到 Flask app，返回配置好的实例。"""
    login_mgr = LoginManager()
    login_mgr.login_view = "/login"          # 未登录重定向到登录页
    login_mgr.login_message = "请先登录"
    login_mgr.login_message_category = "warning"
    login_mgr.init_app(app)

    @login_mgr.user_loader
    def load_user(user_id: str):
        with _conn(cfg) as conn:
            row = conn.execute(
                "SELECT user_id, username, role, is_active FROM users WHERE user_id = ? AND is_active = 1",
                (int(user_id),),
            ).fetchone()
        if row is None:
            return None
        return AuthUser(user_id=row[0], username=row[1], role=row[2])

    return login_mgr
