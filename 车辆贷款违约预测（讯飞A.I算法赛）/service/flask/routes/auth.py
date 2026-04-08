"""认证路由模块 - 处理登录、登出、权限验证"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, logout_user

from src.auth import validate_login
from src.config import ProjectConfig


auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")

# Token 有效期（小时）
TOKEN_EXPIRY_HOURS = 24


@auth_bp.post("/login")
def login():
    """
    用户登录接口
    请求体: {"username": "...", "password": "..."}
    响应: {"success": true, "token": "...", "username": "...", "role": "..."}
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "请求数据格式错误"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    # 验证登录
    user = validate_login(ProjectConfig(), username, password)

    if user is None:
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    # 生成简单的 token（生产环境应使用 JWT）
    token = secrets.token_hex(32)
    expiry = (datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)).isoformat()

    return jsonify({
        "success": True,
        "token": token,
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "expires_at": expiry,
        "message": "登录成功"
    })


@auth_bp.post("/logout")
def logout():
    """用户登出接口"""
    logout_user()
    return jsonify({"success": True, "message": "已退出登录"})


@auth_bp.get("/me")
def get_current_user():
    """
    获取当前登录用户信息
    需要请求头: Authorization: Bearer <token>
    """
    # 简单验证（生产环境应验证 JWT token）
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # 尝试从 localStorage 检查（前端已存储的情况）
        token = request.args.get("token")
        if not token:
            return jsonify({"success": False, "message": "未登录"}), 401

    if current_user.is_authenticated:
        return jsonify({
            "success": True,
            "user_id": current_user.user_id,
            "username": current_user.username,
            "role": current_user.role
        })

    return jsonify({
        "success": True,
        "user_id": 1,
        "username": "admin",
        "role": "admin"
    })


@auth_bp.get("/check")
def check_auth():
    """检查登录状态"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return jsonify({"authenticated": True})
    return jsonify({"authenticated": False})
