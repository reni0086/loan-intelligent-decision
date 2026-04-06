@echo off
chcp 65001 >nul 2>&1
title 贷款智能决策系统 - 快速启动
color 0B

echo ==========================================
echo   贷款智能决策系统 - 快速启动
echo   （跳过数据处理和模型训练）
echo ==========================================
echo.

cd /d "%~dp0"

:: 检查模型是否已存在
if not exist "artifacts\default_model.joblib" (
    echo [错误] 模型文件不存在，请先运行"一键启动.bat"完成训练。
    pause
    exit /b 1
)

echo [信息] 检测到已训练模型，直接启动 Web 服务...
echo.
echo ==========================================
echo   看板地址:  http://127.0.0.1:5000
echo   关闭此窗口即可停止服务。
echo ==========================================
echo.

start http://127.0.0.1:5000
python app.py
pause
