@echo off
chcp 65001 >nul 2>&1
title 贷款智能决策系统 - 一键启动
color 0A

echo ==========================================
echo   贷款客户信息修复与智能决策系统
echo   一键启动脚本
echo ==========================================
echo.

:: 进入项目目录（脚本所在目录）
cd /d "%~dp0"
echo [信息] 工作目录: %CD%
echo.

:: ============================================
:: 第 0 步：检查 Python 环境
:: ============================================
echo [1/6] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 以上版本。
    echo        下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo        Python 版本: %%v
echo.

:: ============================================
:: 第 1 步：安装依赖
:: ============================================
echo [2/6] 安装 Python 依赖（首次运行需要等待）...
pip install pandas numpy scikit-learn joblib xgboost flask --quiet 2>&1
if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装失败，尝试继续运行...
)
echo        依赖安装完成。
echo.

:: ============================================
:: 第 2 步：检查数据文件
:: ============================================
echo [3/6] 检查数据文件...
if not exist "car_loan_train.csv" (
    echo [错误] 缺少 car_loan_train.csv 训练数据文件！
    echo        请将数据文件放到当前目录: %CD%
    pause
    exit /b 1
)
if not exist "test.csv" (
    echo [错误] 缺少 test.csv 测试数据文件！
    echo        请将数据文件放到当前目录: %CD%
    pause
    exit /b 1
)
echo        数据文件检查通过。
echo.

:: ============================================
:: 第 3 步：运行数据处理流水线
:: ============================================
echo [4/6] 运行数据摄入与存储流水线...
python run_ingest_storage.py
if %errorlevel% neq 0 (
    echo [错误] 数据摄入失败！
    pause
    exit /b 1
)
echo.

echo [4/6] 运行数据修复流水线...
python run_repair_pipeline.py
if %errorlevel% neq 0 (
    echo [错误] 数据修复失败！
    pause
    exit /b 1
)
echo.

:: ============================================
:: 第 4 步：训练决策模型
:: ============================================
echo [5/6] 训练决策模型（违约/欺诈/额度）...
python run_decision_suite.py
if %errorlevel% neq 0 (
    echo [错误] 模型训练失败！
    pause
    exit /b 1
)
echo.

echo [5/6] 运行实时微批处理...
python run_realtime_worker.py
if %errorlevel% neq 0 (
    echo [错误] 实时处理失败！
    pause
    exit /b 1
)
echo.

:: ============================================
:: 第 5 步：启动 Web 服务
:: ============================================
echo [6/6] 启动 Flask Web 服务...
echo.
echo ==========================================
echo   系统启动成功！
echo ==========================================
echo.
echo   看板地址:  http://127.0.0.1:5000
echo   健康检查:  http://127.0.0.1:5000/health
echo   统计概览:  http://127.0.0.1:5000/stats/overview
echo.
echo   关闭此窗口即可停止服务。
echo ==========================================
echo.

:: 自动打开浏览器
start http://127.0.0.1:5000

:: 前台运行 Flask（关闭窗口即停止）
python app.py
pause
