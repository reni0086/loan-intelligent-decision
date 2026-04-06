# 模块 M：看板联调与验收自动化

## 模块目标
完成看板与后端接口联调，并固化全链路验收脚本。

## 已完成功能
- 看板联调：
  - `dashboard/main.js` 新增 `/stats/risk_daily` 数据联动。
- 验收脚本：
  - `scripts/acceptance/run_all_checks.sh`
- 验收清单：
  - `docs/ACCEPTANCE_CHECKLIST.md`

## 实现方式
- 看板只通过 Flask API 取数，避免前端直连数据库。
- 一键脚本覆盖组件版本、存储布局、接口可用性检查。

## 未完成项
- 客户验收现场需补截图与命令输出归档。
