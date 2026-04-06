# API 接口规范文档

## 1. 接口基础规范

- **Base URL**: `http://localhost:5000`
- **Content-Type**: `application/json`
- **字符编码**: UTF-8
- **跨域**: 支持 CORS

---

## 2. 接口目录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/predict/default` | 违约预测 |
| POST | `/predict/fraud` | 欺诈检测 |
| POST | `/predict/limit` | 额度预测 |
| POST | `/predict/full` | 完整决策 (含信用评分) |
| POST | `/score/credit` | 信用评分计算 |
| GET | `/customer/<int:customer_id>/profile` | 客户画像 |
| GET | `/customer/<int:customer_id>/similar` | 相似客户列表 |
| GET | `/customer/<int:customer_id>/loan_history` | 贷款历史时间轴 |
| GET | `/stats/overview` | 业务概览 |
| GET | `/stats/risk_daily` | 每日逾期率趋势 |
| GET | `/stats/risk_distribution` | 风险等级分布 |
| GET | `/stats/model_metrics` | 模型性能指标 |
| GET | `/stats/area_risk` | 地区风险排行 |
| GET | `/stats/customer_cluster` | 客户聚类分布 |
| GET | `/stats/credit_score_dist` | 信用评分分布 |
| GET | `/model/shap_values` | SHAP 特征重要性 |
| POST | `/repair/record` | 信息修复 |

---

## 3. 接口详细规范

### 3.1 健康检查

**GET** `/health`

响应示例:

```json
{
  "status": "ok",
  "time": "2026-04-04T10:23:45"
}
```

---

### 3.2 违约预测

**POST** `/predict/default`

请求体 (单条):

```json
{
  "customer_id": 100001,
  "credit_score": 720,
  "disbursed_amount": 35000,
  "asset_cost": 45000,
  "total_overdue_no": 0,
  "total_account_loan_no": 2,
  "employment_type": 1,
  "age": 38,
  "area_id": 5,
  "credit_history": 5,
  "enquirie_no": 2,
  "total_monthly_payment": 1200,
  "total_disbursed_loan": 45000,
  "last_six_month_new_loan_no": 1,
  "last_six_month_defaulted_no": 0
}
```

响应 (单条):

```json
{
  "customer_id": 100001,
  "default_probability": 0.1234,
  "default_pred": 0,
  "credit_score": 715.5
}
```

响应 (批量, 数组):

```json
[
  {"customer_id": 100001, "default_probability": 0.1234, "default_pred": 0},
  {"customer_id": 100002, "default_probability": 0.7234, "default_pred": 1}
]
```

---

### 3.3 欺诈检测

**POST** `/predict/fraud`

请求体: 同 `/predict/default`

响应:

```json
{
  "customer_id": 100001,
  "fraud_probability": 0.0234,
  "fraud_pred": 0
}
```

---

### 3.4 额度预测

**POST** `/predict/limit`

请求体: 同 `/predict/default`

响应:

```json
{
  "customer_id": 100001,
  "predicted_limit": 45000.0
}
```

---

### 3.5 完整决策

**POST** `/predict/full`

请求体: 同 `/predict/default`

响应:

```json
[
  {
    "customer_id": 100001,
    "default_probability": 0.1234,
    "default_pred": 0,
    "fraud_probability": 0.0234,
    "fraud_pred": 0,
    "predicted_limit": 45000.0,
    "credit_score": 715.5
  }
]
```

---

### 3.6 信用评分

**POST** `/score/credit`

请求体:

```json
{
  "default_probability": [0.1, 0.5, 0.9]
}
```

响应:

```json
{
  "credit_score": [650.0, 600.0, 500.0]
}
```

---

### 3.7 客户画像

**GET** `/customer/<int:customer_id>/profile`

响应:

```json
{
  "customer_id": 100001,
  "profile": {
    "age": 38,
    "employment_type": 1,
    "area_id": 5,
    "credit_score": 720,
    "disbursed_amount": 35000,
    "total_overdue_no": 0,
    "total_account_loan_no": 2,
    "loan_default": 0
  },
  "radar_scores": {
    "credit": 84.71,
    "repay_ability": 92.5,
    "asset_status": 88.0,
    "history": 100.0,
    "stability": 87.0
  },
  "decision": {
    "default_probability": 0.1234,
    "default_pred": 0,
    "fraud_probability": 0.0234,
    "fraud_pred": 0,
    "predicted_limit": 45000.0,
    "credit_score": 715.5
  },
  "generated_at": "2026-04-04T10:23:45"
}
```

---

### 3.8 相似客户

**GET** `/customer/<int:customer_id>/similar`

响应:

```json
[
  {"customer_id": 100003, "credit_score": 718, "disbursed_amount": 34000, "total_overdue_no": 0, "actual_performance": "正常还款", "similarity": 0.96},
  {"customer_id": 100004, "credit_score": 725, "disbursed_amount": 36000, "total_overdue_no": 0, "actual_performance": "正常还款", "similarity": 0.94},
  {"customer_id": 100005, "credit_score": 715, "disbursed_amount": 33000, "total_overdue_no": 0, "actual_performance": "正常还款", "similarity": 0.91}
]
```

---

### 3.9 贷款历史

**GET** `/customer/<int:customer_id>/loan_history`

响应:

```json
{
  "customer_id": 100001,
  "events": [
    {"date": "2024-01-15", "type": "loan-apply", "title": "提交贷款申请", "detail": "申请金额: 35000元, 用途: 购车"},
    {"date": "2024-01-18", "type": "loan-disbursed", "title": "贷款发放", "detail": "实际发放: 35000元, 利率: 6.5%, 期限: 36期"},
    {"date": "2024-02-15", "type": "ontime-repay", "title": "按时还款", "detail": "本期还款: 1080元, 余额: 33920元"}
  ],
  "total_events": 38
}
```

事件类型 (type):

| type | 说明 | 颜色标识 |
|------|------|---------|
| loan-apply | 贷款申请 | 蓝色 |
| loan-disbursed | 贷款发放 | 绿色 |
| ontime-repay | 按时还款 | 绿色 |
| overdue | 逾期还款 | 黄色 |
| default | 严重违约 | 红色 |
| closed | 贷款结清 | 紫色 |

---

### 3.10 业务概览

**GET** `/stats/overview`

响应:

```json
{
  "total_customers": 2263847,
  "total_amount": 158.24,
  "overdue_rate": 0.0582,
  "new_customers": 12458,
  "realtime_events": 0,
  "realtime_decisions": 0
}
```

---

### 3.11 每日逾期率趋势

**GET** `/stats/risk_daily`

响应:

```json
[
  {"dt": "2025-01", "default_rate": 0.068, "total": 150000},
  {"dt": "2025-02", "default_rate": 0.065, "total": 155000}
]
```

---

### 3.12 风险等级分布

**GET** `/stats/risk_distribution`

响应:

```json
[
  {"name": "低风险", "value": 70},
  {"name": "中风险", "value": 20},
  {"name": "高风险", "value": 10}
]
```

---

### 3.13 模型性能指标

**GET** `/stats/model_metrics`

响应:

```json
{
  "auc": 0.873,
  "precision": 0.820,
  "recall": 0.790,
  "f1": 0.800,
  "accuracy": 0.815,
  "threshold": 0.50
}
```

---

### 3.14 地区风险排行

**GET** `/stats/area_risk`

响应:

```json
[
  {"area": "华西区-B", "rate": 0.123, "customers": 95000, "defaults": 11685},
  {"area": "华北区-C", "rate": 0.108, "customers": 145000, "defaults": 15660}
]
```

---

### 3.15 客户聚类分布

**GET** `/stats/customer_cluster`

响应:

```json
{
  "clusters": [
    {"name": "高信用高额度", "color": "#34a853", "count": 339577},
    {"name": "中信用中额度", "color": "#1a73e8", "count": 905535}
  ],
  "scatterData": []
}
```

---

### 3.16 信用评分分布

**GET** `/stats/credit_score_dist`

响应:

```json
{
  "buckets": ["300-400", "400-500", "500-600", "600-700", "700-800", "800-850"],
  "counts": [45000, 180000, 680000, 800000, 450000, 110000]
}
```

---

### 3.17 SHAP 特征重要性

**GET** `/model/shap_values`

响应:

```json
[
  {"name": "credit_score", "display": "信用评分", "mean_abs_shap": 4.52, "impact": "负向"},
  {"name": "total_overdue_no", "display": "总逾期次数", "mean_abs_shap": 3.87, "impact": "正向"}
]
```

---

### 3.18 信息修复

**POST** `/repair/record`

请求体:

```json
{
  "customer_id": 100001,
  "credit_score": null,
  "total_overdue_no": 0
}
```

响应:

```json
{
  "customer_id": 100001,
  "credit_score": 650,
  "total_overdue_no": 0,
  "_repair_info": {
    "credit_score_repaired": true,
    "confidence": 0.75,
    "method": "FP-Growth"
  }
}
```

---

## 4. 错误响应

所有接口在出错时返回标准错误格式:

```json
{
  "error": "Error description",
  "code": "ERROR_CODE",
  "detail": "Detailed error message"
}
```

常见 HTTP 状态码:

| 状态码 | 说明 |
|-------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 (模型未加载等) |

---

## 5. 看板前端 API 调用说明

看板页面 (`dashboard/index.html`) 按以下顺序调用接口:

1. `GET /health` - 检查服务可用性
2. `GET /stats/overview` - 获取 KPI 数据
3. `GET /stats/risk_daily` - 获取逾期率趋势
4. `GET /stats/risk_distribution` - 获取风险分布
5. `GET /stats/model_metrics` - 获取模型指标
6. `GET /stats/area_risk` - 获取地区风险
7. `GET /stats/customer_cluster` - 获取聚类分布
8. `GET /stats/credit_score_dist` - 获取评分分布
9. `GET /model/shap_values` - 获取特征重要性

看板默认每 5 分钟自动刷新一次。
