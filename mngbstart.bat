@echo off
title Claude Code Terminal - Proxy Enabled

:: 设置代理
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890
set ALL_PROXY=socks5://127.0.0.1:7890
set NO_PROXY=localhost,127.0.0.1,.aliyun.com

:: 显示当前配置
echo ==========================================
echo   Claude Code Terminal Configuration
echo ==========================================
echo.
echo Current Directory: %CD%
echo HTTP_PROXY: %HTTP_PROXY%
echo HTTPS_PROXY: %HTTPS_PROXY%
echo ALL_PROXY: %ALL_PROXY%
echo NO_PROXY: %NO_PROXY%
echo.
echo ==========================================
echo.

:: 测试代理连接（可选）
echo Testing proxy connection...
curl -I https://www.google.com --proxy http://127.0.0.1:7890 --max-time 5 >nul 2>&1
if %errorlevel% == 0 (
    echo [SUCCESS] Proxy is working!
) else (
    echo [WARNING] Proxy might not be working properly!
)
echo.

:: 启动 Claude Code（最高权限）
echo Starting Claude Code...
claude --dangerously-skip-permissions

:: 保持窗口打开
cmd