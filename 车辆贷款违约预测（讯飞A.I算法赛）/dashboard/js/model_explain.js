/* ================================================
   模型解释页面 - SHAP可视化与模型性能分析
   ================================================ */

const CHART_COLORS = {
  primary: '#1a73e8',
  success: '#34a853',
  warning: '#fbbc04',
  danger: '#ea4335',
  purple: '#9334e6',
};

/* ---------- Mock SHAP 数据 ---------- */
const MockShapData = [
  { name: 'credit_score', display: '信用评分', mean_abs_shap: 4.52, impact: '负向', description: '信用评分越高，违约风险越低。750分以上客户违约率低于2%。' },
  { name: 'total_overdue_no', display: '总逾期次数', mean_abs_shap: 3.87, impact: '正向', description: '逾期次数越多，违约风险显著上升。逾期3次以上是高危信号。' },
  { name: 'outstanding_disburse_ratio', display: '未偿发放比', mean_abs_shap: 3.21, impact: '正向', description: '未偿金额占发放金额比例越高，说明还款压力越大。' },
  { name: 'ltv_ratio', display: '贷款资产比', mean_abs_shap: 2.95, impact: '正向', description: 'LTV>0.9表示抵押物价值不足以覆盖贷款，高风险。' },
  { name: 'overdue_rate_total', display: '总逾期率', mean_abs_shap: 2.68, impact: '正向', description: '历史逾期率超过10%的客户，违约概率显著增加。' },
  { name: 'credit_history', display: '信用记录时长', mean_abs_shap: 2.34, impact: '负向', description: '信用历史越长（3年以上），违约风险越低，体现稳定性。' },
  { name: 'enquirie_no', display: '征信查询次数', mean_abs_shap: 2.01, impact: '正向', description: '近3个月查询超过5次，可能存在多头借贷，信用紧张。' },
  { name: 'disbursed_amount', display: '贷款金额', mean_abs_shap: 1.87, impact: '正向', description: '大额贷款违约成本高，但绝对值不是主要风险因子。' },
  { name: 'age', display: '年龄', mean_abs_shap: 1.65, impact: '负向', description: '35-50岁客户违约率最低，过于年轻（<25）或年长（>60）风险略高。' },
  { name: 'total_monthly_payment', display: '月供金额', mean_abs_shap: 1.43, impact: '正向', description: '月供占收入比超过40%时，还款压力显著增加。' },
  { name: 'employment_type', display: '工作类型', mean_abs_shap: 1.28, impact: '负向', description: '受薪员工（salaried）比自雇人士（self-employed）违约率低约15%。' },
  { name: 'area_id', display: '地区', mean_abs_shap: 1.15, impact: '正向', description: '部分地区（如华西区）违约率偏高，与当地经济环境相关。' },
];

/* ---------- Mock 单客户 Waterfall 数据 ---------- */
const MockWaterfallData = [
  { name: '信用评分(高)', value: -0.22, base: false },
  { name: '逾期次数(多)', value: 0.18, base: false },
  { name: '月供压力(中等)', value: 0.08, base: false },
  { name: '信用历史(长)', value: -0.06, base: false },
  { name: '贷款金额(大)', value: 0.05, base: false },
  { name: '年龄(适中)', value: -0.03, base: false },
  { name: '其他因素', value: 0.01, base: false },
  { name: 'Base Rate', value: 0.5, base: true },
];

/* ---------- Mock 模型对比数据 ---------- */
const MockModelCompare = {
  models: [
    { name: 'XGBoost', auc: 0.873, precision: 0.820, recall: 0.790, f1: 0.800, speed: 'Fast', color: '#1a73e8' },
    { name: 'LightGBM', auc: 0.869, precision: 0.815, recall: 0.785, f1: 0.795, speed: 'Fastest', color: '#34a853' },
    { name: 'CatBoost', auc: 0.862, precision: 0.808, recall: 0.780, f1: 0.788, speed: 'Medium', color: '#9334e6' },
    { name: 'RandomForest', auc: 0.841, precision: 0.790, recall: 0.760, f1: 0.770, speed: 'Medium', color: '#f9ab00' },
    { name: 'LogisticReg', auc: 0.795, precision: 0.740, recall: 0.710, f1: 0.720, speed: 'Fastest', color: '#5f6368' },
  ],
};

/* ---------- Mock 决策案例 ---------- */
const MockDecisionCases = [
  {
    caseId: 1,
    result: 'approve',
    label: '建议批准',
    customerId: 100021,
    defaultProb: 0.08,
    creditScore: 768,
    disbursedAmount: 35000,
    totalOverdue: 0,
    reason: '客户信用评分768分，历史上无逾期记录，贷款金额在合理范围内。相似客户群体中92%正常还款。建议批准，可提供优惠利率。',
  },
  {
    caseId: 2,
    result: 'caution',
    label: '审慎批准',
    customerId: 100045,
    defaultProb: 0.35,
    creditScore: 625,
    disbursedAmount: 18000,
    totalOverdue: 1,
    reason: '客户信用评分625分处于中等水平，有1次轻微逾期记录。近期有2次贷款申请查询。建议审慎批准，降低额度或要求增加担保。',
  },
  {
    caseId: 3,
    result: 'reject',
    label: '建议拒绝',
    customerId: 100078,
    defaultProb: 0.72,
    creditScore: 480,
    disbursedAmount: 25000,
    totalOverdue: 4,
    reason: '客户信用评分仅480分，历史逾期4次（含1次严重逾期），近6个月新增2笔贷款。相似客户中75%发生违约。建议拒绝。',
  },
];

/* ---------- SHAP 特征重要性条形图 ---------- */
function renderShapBarChart(data) {
  const chart = echarts.init(document.getElementById('chartShapBar'));
  if (!chart) return;

  const d = (data || MockShapData).slice(0, 12).reverse();

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: (p) => `${p[0].name}<br/>SHAP: <b>${p[0].value.toFixed(3)}</b>`,
    },
    grid: { top: 10, right: 80, bottom: 10, left: 120 },
    xAxis: { type: 'value', axisLabel: { fontSize: 10, color: '#6b7785' }, splitLine: { lineStyle: { color: '#f0f0f0' } } },
    yAxis: {
      type: 'category',
      data: d.map(x => x.display || x.name),
      axisLabel: { fontSize: 11, color: '#5f6368' },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      data: d.map((x, i) => ({
        value: x.mean_abs_shap,
        itemStyle: {
          color: x.impact === '负向' ? '#34a853' : '#ea4335',
        },
      })),
      barMaxWidth: 22,
      label: {
        show: true,
        position: 'right',
        formatter: (p) => p.value.toFixed(2),
        fontSize: 10,
        color: '#6b7785',
      },
    }],
  });
}

/* ---------- 模型对比图表 ---------- */
function renderModelCompareChart(data) {
  const chart = echarts.init(document.getElementById('chartModelCompare'));
  if (!chart) return;

  const models = (data || MockModelCompare).models;

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const m = models[params[0].dataIndex];
        return `<b>${m.name}</b><br/>
          AUC: ${m.auc.toFixed(3)}<br/>
          精确率: ${m.precision.toFixed(3)}<br/>
          召回率: ${m.recall.toFixed(3)}<br/>
          F1: ${m.f1.toFixed(3)}`;
      },
    },
    legend: {
      bottom: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 10 },
    },
    grid: { top: 10, right: 10, bottom: 40, left: 10 },
    xAxis: {
      type: 'category',
      data: models.map(m => m.name),
      axisLabel: { fontSize: 10, color: '#6b7785' },
      axisLine: { lineStyle: { color: '#e0e4e8' } },
    },
    yAxis: {
      type: 'value',
      max: 1,
      axisLabel: { fontSize: 10, formatter: (v) => v.toFixed(1), color: '#6b7785' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [
      { name: 'AUC', type: 'bar', data: models.map(m => m.auc), itemStyle: { color: '#1a73e8' }, barMaxWidth: 25 },
      { name: '精确率', type: 'bar', data: models.map(m => m.precision), itemStyle: { color: '#34a853' }, barMaxWidth: 25 },
      { name: '召回率', type: 'bar', data: models.map(m => m.recall), itemStyle: { color: '#f9ab00' }, barMaxWidth: 25 },
    ],
  });
}

/* ---------- 模型对比表格 ---------- */
function renderModelCompareTable(data) {
  const tbody = document.getElementById('modelCompareTable');
  if (!tbody) return;

  const models = (data || MockModelCompare).models;
  tbody.innerHTML = models.map((m, i) => `
    <tr class="${i === 0 ? 'best-cell' : ''}">
      <td>${i === 0 ? '<b>' + m.name + ' &#x2605;</b>' : m.name}</td>
      <td>${m.auc.toFixed(3)}</td>
      <td>${m.precision.toFixed(3)}</td>
      <td>${m.recall.toFixed(3)}</td>
      <td>${m.f1.toFixed(3)}</td>
      <td><span class="badge badge-info">${m.speed}</span></td>
    </tr>
  `).join('');
}

/* ---------- SHAP Waterfall Chart ---------- */
function renderShapWaterfall(data) {
  const chart = echarts.init(document.getElementById('chartShapWaterfall'));
  if (!chart) return;

  const d = data || MockWaterfallData;

  let cumValue = 0;
  const waterfallData = [];
  const labels = [];

  // Build waterfall bars
  d.forEach((item, i) => {
    if (item.base) {
      waterfallData.push({ value: [i, 0, item.value, item.value], itemStyle: { color: '#6b7785' } });
      cumValue = item.value;
    } else {
      if (item.value >= 0) {
        waterfallData.push({ value: [i, cumValue, cumValue + item.value, item.value], itemStyle: { color: '#ea4335' } });
      } else {
        waterfallData.push({ value: [i, cumValue + item.value, cumValue, item.value], itemStyle: { color: '#34a853' } });
      }
      cumValue += item.value;
    }
    labels.push(item.name);
  });

  // Final prediction
  waterfallData.push({ value: [d.length, 0, cumValue, cumValue], itemStyle: { color: cumValue > 0.5 ? '#ea4335' : '#34a853' } });
  labels.push('预测');

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      formatter: (p) => {
        const item = d[p.dataIndex < d.length ? p.dataIndex : d.length - 1];
        if (!item) return '';
        const sign = item.value >= 0 ? '+' : '';
        return `<b>${item.name}</b><br/>贡献: <b style="color:${item.value >= 0 ? '#ea4335' : '#34a853'}">${sign}${item.value.toFixed(3)}</b>`;
      },
    },
    grid: { top: 10, right: 60, bottom: 30, left: 60 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { fontSize: 9, color: '#6b7785', rotate: 30 },
      axisLine: { lineStyle: { color: '#e0e4e8' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, formatter: (v) => v.toFixed(1), color: '#6b7785' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [{
      type: 'custom',
      renderItem: (params, api) => {
        const val = api.value();
        const i = val[0];
        const start = api.coord([i, val[1]]);
        const end = api.coord([i, val[2]]);
        const height = Math.abs(end[1] - start[1]);
        const y = Math.min(start[1], end[1]);
        return {
          type: 'rect',
          shape: { x: start[0] - 18, y, width: 36, height: Math.max(2, height) },
          style: api.style(),
        };
      },
      data: waterfallData,
      encode: { x: 0, y: [1, 2] },
    }],
  });
}

/* ---------- SHAP Waterfall Detail ---------- */
function renderShapWaterfallDetail(data) {
  const el = document.getElementById('shapWaterfallDetail');
  if (!el) return;

  const d = (data || MockWaterfallData).filter(x => !x.base);

  el.innerHTML = d.map(item => {
    const isPos = item.value > 0;
    return `<div class="shap-bar-row">
      <span class="shap-bar-label">${item.name}</span>
      <div class="shap-bar-track">
        <div class="shap-bar-fill ${isPos ? 'positive' : 'negative'}"
             style="width:${Math.min(50, Math.abs(item.value) * 100)}%;${isPos ? 'right:auto;left:50%;' : 'left:auto;right:50%;'}"></div>
      </div>
      <span class="shap-bar-value" style="color:${isPos ? '#ea4335' : '#34a853'};">${isPos ? '+' : ''}${item.value.toFixed(2)}</span>
    </div>`;
  }).join('');
}

/* ---------- 特征影响详情列表 ---------- */
function renderShapDetailList(data) {
  const el = document.getElementById('shapDetailList');
  if (!el) return;

  const d = (data || MockShapData).slice(0, 8);

  el.innerHTML = d.map(item => `
    <div class="shap-detail-item">
      <div class="shap-detail-header">
        <div class="shap-detail-icon" style="background:${item.impact === '负向' ? '#e6f4ea' : '#fce8e6'};color:${item.impact === '负向' ? '#34a853' : '#ea4335'};">
          ${item.impact === '负向' ? '&#x2193;' : '&#x2191;'}
        </div>
        <div class="shap-detail-name">${item.display || item.name}</div>
        <div class="shap-detail-effect ${item.impact === '负向' ? 'negative' : 'positive'}">
          ${item.impact === '负向' ? '降低风险' : '增加风险'}
        </div>
      </div>
      <div class="shap-detail-desc">${item.description}</div>
    </div>
  `).join('');
}

/* ---------- 决策案例卡片 ---------- */
function renderDecisionCases(data) {
  const el = document.getElementById('decisionCases');
  if (!el) return;

  const d = data || MockDecisionCases;

  el.innerHTML = d.map(c => {
    const resultClass = c.result === 'approve' ? 'approve' : c.result === 'reject' ? 'reject' : 'caution';
    const resultBadge = c.result === 'approve'
      ? '<span class="badge badge-success">建议批准</span>'
      : c.result === 'reject'
        ? '<span class="badge badge-danger">建议拒绝</span>'
        : '<span class="badge badge-warning">审慎批准</span>';

    return `<div class="decision-case ${resultClass}">
      <div class="case-header">
        <div class="case-title">案例 #${c.caseId} - 客户 ${c.customerId}</div>
        ${resultBadge}
      </div>
      <div class="case-features">
        <div class="case-feature">
          <div class="cf-label">违约概率</div>
          <div class="cf-value" style="color:${c.defaultProb > 0.5 ? '#ea4335' : c.defaultProb > 0.3 ? '#f9ab00' : '#34a853'};">${(c.defaultProb * 100).toFixed(1)}%</div>
        </div>
        <div class="case-feature">
          <div class="cf-label">信用评分</div>
          <div class="cf-value">${c.creditScore}</div>
        </div>
        <div class="case-feature">
          <div class="cf-label">逾期次数</div>
          <div class="cf-value" style="color:${c.totalOverdue > 2 ? '#ea4335' : '#34a853'};">${c.totalOverdue}</div>
        </div>
      </div>
      <div class="case-reason">${c.reason}</div>
    </div>`;
  }).join('');
}

/* ---------- 阈值调整 ---------- */
function updateThreshold(value) {
  document.getElementById('thresholdDisplay').textContent = parseFloat(value).toFixed(2);
  // 可扩展：重新计算所有预测的分类结果
}

/* ---------- 页面初始化 ---------- */
let resizeTimer;

function boot() {
  // 加载所有图表
  renderShapBarChart(MockShapData);
  renderModelCompareChart(MockModelCompare);
  renderModelCompareTable(MockModelCompare);
  renderShapWaterfall(MockWaterfallData);
  renderShapWaterfallDetail(MockWaterfallData);
  renderShapDetailList(MockShapData);
  renderDecisionCases(MockDecisionCases);

  // 窗口调整
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const ids = ['chartShapBar', 'chartModelCompare', 'chartShapWaterfall'];
      ids.forEach(id => {
        const inst = echarts.getInstanceByDom(document.getElementById(id));
        if (inst) inst.resize();
      });
    }, 300);
  });
}

/* ---------- 启动 ---------- */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
