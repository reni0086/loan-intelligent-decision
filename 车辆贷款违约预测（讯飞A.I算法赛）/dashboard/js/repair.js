/* ================================================
   数据修复页面 - JS 逻辑
   ================================================ */

// 模拟修复规则数据
const MockFpRules = [
  { pattern: '信用评分=700→800, 年龄>35 → 职业类型', confidence: 0.92, support: 0.18, usages: 15420 },
  { pattern: '贷款金额>50000, 逾期次数>0 → 风险等级=高', confidence: 0.89, support: 0.12, usages: 12350 },
  { pattern: '地区=华东区, 信用评分>650 → 修复收入水平', confidence: 0.85, support: 0.15, usages: 11800 },
  { pattern: '贷款期限>24, 年龄<40 → 修复月供金额', confidence: 0.81, support: 0.09, usages: 8900 },
  { pattern: '征信查询次数<3, 信用评分>600 → 修复信用历史', confidence: 0.78, support: 0.11, usages: 7650 },
];

const MockAlsRules = [
  { field: '月收入', rmse: 0.23, mape: 12.5, coverage: 94 },
  { field: '职业类型', rmse: 0.18, mape: 8.2, coverage: 91 },
  { field: '月供金额', rmse: 0.31, mape: 15.8, coverage: 88 },
  { field: '信用历史', rmse: 0.15, mape: 6.3, coverage: 96 },
  { field: '负债比率', rmse: 0.28, mape: 11.2, coverage: 89 },
];

const MockHistory = [
  { time: '2026-04-08 14:23:15', title: '客户 #100001 信用评分修复', detail: 'FP-Growth规则填充，置信度92%', status: 'success' },
  { time: '2026-04-08 14:22:48', title: '客户 #100015 月收入修复', detail: 'ALS矩阵分解填充，RMSE=0.21', status: 'success' },
  { time: '2026-04-08 14:21:33', title: '客户 #100042 职业类型修复', detail: 'FP-Growth规则填充，置信度85%', status: 'success' },
  { time: '2026-04-08 14:20:05', title: '批量修复任务完成', detail: '处理 1,245 条记录，成功率 96.8%', status: 'success' },
  { time: '2026-04-08 14:15:22', title: '客户 #100089 收入水平修复', detail: 'ALS矩阵分解填充，置信度低于阈值(72%)，需审核', status: 'warning' },
  { time: '2026-04-08 14:10:11', title: '客户 #100156 修复失败', detail: '缺失字段过多，无法推算', status: 'error' },
  { time: '2026-04-08 13:58:44', title: '规则引擎更新', detail: '新增 FP-Growth 规则 12 条', status: 'success' },
  { time: '2026-04-08 13:45:30', title: '客户 #100234 信用历史修复', detail: 'FP-Growth规则填充，置信度91%', status: 'success' },
];

// 模拟客户修复前后数据
const MockRepairData = {
  before: {
    customer_id: 100001,
    credit_score: null,
    employment_type: null,
    monthly_income: null,
    credit_history: null,
    overdue_count: 0,
  },
  after: {
    customer_id: 100001,
    credit_score: 742,
    employment_type: '受薪员工',
    monthly_income: 8500,
    credit_history: 18,
    overdue_count: 0,
  }
};

/* ---------- 页面初始化 ---------- */
function boot() {
  // 检查登录状态
  const user = checkAuth();
  if (!user) {
    window.location.href = '/login';
    return;
  }

  // 更新用户UI
  updateUserUI();

  // 加载数据
  loadStats();
  loadFpRules();
  loadAlsRules();
  loadHistory();

  // 初始化图表
  initCharts();
}

window.boot = boot;

/* ---------- 标签页切换 ---------- */
function switchTab(tabId) {
  // 更新按钮状态
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.includes(
      tabId === 'rules' ? '修复规则' :
      tabId === 'query' ? '修复查询' :
      tabId === 'config' ? '修复配置' :
      tabId === 'history' ? '修复历史' : '修复统计'
    ));
  });

  // 更新内容显示
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.toggle('active', content.id === 'tab-' + tabId);
  });

  // 如果是统计标签，渲染图表
  if (tabId === 'stats') {
    setTimeout(() => {
      const qualityChart = echarts.getInstanceByDom(document.getElementById('chartQuality'));
      const typeChart = echarts.getInstanceByDom(document.getElementById('chartType'));
      if (qualityChart) qualityChart.resize();
      if (typeChart) typeChart.resize();
    }, 100);
  }
}

/* ---------- 加载统计数据 ---------- */
async function loadStats() {
  // 尝试从API加载
  const metrics = await API.repairMetrics();

  if (metrics) {
    document.getElementById('totalCustomers').textContent = fmtNum(metrics.total_customers || 150000);
    document.getElementById('repairedRecords').textContent = fmtNum(metrics.repaired_count || 874650);
    document.getElementById('repairCoverage').textContent = (metrics.repair_rate || 38.6) + '%';
    document.getElementById('repairAccuracy').textContent = (metrics.repair_success_rate || 89) + '%';
  } else {
    // 使用默认模拟数据
    document.getElementById('totalCustomers').textContent = '150,000';
    document.getElementById('repairedRecords').textContent = '874,650';
    document.getElementById('repairCoverage').textContent = '38.6%';
    document.getElementById('repairAccuracy').textContent = '89.0%';
  }
}

/* ---------- 加载 FP-Growth 规则 ---------- */
function loadFpRules() {
  const tbody = document.getElementById('fpRulesTable');
  document.getElementById('fpRuleCount').textContent = MockFpRules.length + ' 条规则';

  tbody.innerHTML = MockFpRules.map(rule => `
    <tr>
      <td><span class="rule-pattern">${rule.pattern}</span></td>
      <td>
        <div class="rule-confidence">
          <div class="confidence-bar"><div class="confidence-fill" style="width:${rule.confidence * 100}%"></div></div>
          <span>${(rule.confidence * 100).toFixed(0)}%</span>
        </div>
      </td>
      <td>${(rule.support * 100).toFixed(1)}%</td>
      <td>${rule.usages.toLocaleString()}</td>
    </tr>
  `).join('');
}

/* ---------- 加载 ALS 规则 ---------- */
function loadAlsRules() {
  const tbody = document.getElementById('alsRulesTable');
  document.getElementById('alsRuleCount').textContent = MockAlsRules.length + ' 条规则';

  tbody.innerHTML = MockAlsRules.map(rule => `
    <tr>
      <td><strong>${rule.field}</strong></td>
      <td><span style="color:${rule.rmse < 0.25 ? '#34a853' : rule.rmse < 0.3 ? '#f9ab00' : '#ea4335'}">${rule.rmse.toFixed(2)}</span></td>
      <td>${rule.mape.toFixed(1)}%</td>
      <td>
        <div class="rule-confidence">
          <div class="confidence-bar"><div class="confidence-fill" style="width:${rule.coverage}%;background:#1a73e8;"></div></div>
          <span>${rule.coverage}%</span>
        </div>
      </td>
    </tr>
  `).join('');
}

/* ---------- 加载修复历史 ---------- */
function loadHistory() {
  const container = document.getElementById('historyList');
  document.getElementById('historyCount').textContent = MockHistory.length;

  container.innerHTML = MockHistory.map(item => {
    const statusClass = item.status === 'success' ? 'badge-success' :
                       item.status === 'warning' ? 'badge-warning' : 'badge-danger';
    const statusText = item.status === 'success' ? '成功' :
                       item.status === 'warning' ? '待审核' : '失败';

    return `
      <div class="history-item">
        <div class="history-time">${item.time}</div>
        <div class="history-content">
          <div class="history-title">${item.title}</div>
          <div class="history-detail">${item.detail}</div>
        </div>
        <div class="history-status">
          <span class="badge ${statusClass}">${statusText}</span>
        </div>
      </div>
    `;
  }).join('');
}

/* ---------- 查询修复记录 ---------- */
function queryRepair() {
  const id = document.getElementById('queryCustomerId').value.trim();
  if (!id) {
    alert('请输入客户ID');
    return;
  }

  // 显示加载状态
  document.getElementById('queryEmpty').style.display = 'none';
  document.getElementById('repairCompareResult').style.display = 'none';

  // 模拟查询
  setTimeout(() => {
    renderRepairCompare(MockRepairData);
    document.getElementById('repairCompareResult').style.display = 'grid';
  }, 500);
}

function queryRandomRepair() {
  const randomId = Math.floor(Math.random() * 999999) + 100001;
  document.getElementById('queryCustomerId').value = randomId;
  queryRepair();
}

function renderRepairCompare(data) {
  const fields = [
    { name: '信用评分', key: 'credit_score' },
    { name: '职业类型', key: 'employment_type' },
    { name: '月收入', key: 'monthly_income' },
    { name: '信用历史', key: 'credit_history' },
  ];

  const beforeHtml = fields.map(f => {
    const val = data.before[f.key];
    return `
      <div class="compare-field">
        <span class="label">${f.name}</span>
        <span class="value error">${val === null ? '--' : val}</span>
      </div>
    `;
  }).join('');

  const afterHtml = fields.map(f => {
    const val = data.after[f.key];
    return `
      <div class="compare-field">
        <span class="label">${f.name}</span>
        <span class="value success">${val === null ? '--' : val}</span>
      </div>
    `;
  }).join('');

  document.getElementById('compareBefore').innerHTML = beforeHtml;
  document.getElementById('compareAfter').innerHTML = afterHtml;
}

/* ---------- 配置相关 ---------- */
function updateSliderValue(slider) {
  const id = slider.id + 'Val';
  const el = document.getElementById(id);
  if (!el) return;

  if (slider.id === 'fpMinSupport' || slider.id === 'fpMinConfidence' ||
      slider.id === 'confidenceThreshold') {
    el.textContent = (parseFloat(slider.value) * 100).toFixed(0) + '%';
  } else {
    el.textContent = slider.value;
  }
}

function saveFpConfig() {
  const config = {
    min_support: parseFloat(document.getElementById('fpMinSupport').value),
    min_confidence: parseFloat(document.getElementById('fpMinConfidence').value),
    max_length: parseInt(document.getElementById('fpMaxLength').value),
  };
  console.log('FP-Growth配置已保存:', config);
  alert('FP-Growth 配置已保存！');
}

function saveAlsConfig() {
  const config = {
    factors: parseInt(document.getElementById('alsFactors').value),
    regularization: parseFloat(document.getElementById('alsReg').value),
    iterations: parseInt(document.getElementById('alsIterations').value),
  };
  console.log('ALS配置已保存:', config);
  alert('ALS 配置已保存！');
}

/* ---------- 运行修复 ---------- */
function runRepair() {
  if (confirm('确定要运行数据修复任务吗？这将根据当前配置修复所有缺失数据。')) {
    const btn = document.querySelector('.btn-primary');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner" style="display:inline-block;margin-right:8px;"></div>修复中...';
    btn.disabled = true;

    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
      alert('数据修复任务完成！共处理 1,245 条记录，成功率 96.8%');
      loadStats();
      loadHistory();
    }, 2000);
  }
}

/* ---------- 刷新数据 ---------- */
function refreshData() {
  loadStats();
  loadFpRules();
  loadAlsRules();
  loadHistory();
}

/* ---------- 初始化图表 ---------- */
function initCharts() {
  // 修复质量趋势图
  const qualityChart = echarts.init(document.getElementById('chartQuality'));
  qualityChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { top: 10, right: 10, bottom: 40, left: 50 },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月'],
      axisLabel: { fontSize: 10, color: '#6b7785' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: v => (v * 100).toFixed(0) + '%', fontSize: 10, color: '#6b7785' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [
      { name: '准确率', type: 'line', data: [0.85, 0.87, 0.86, 0.88, 0.89, 0.89], smooth: true },
      { name: '覆盖率', type: 'line', data: [0.78, 0.82, 0.85, 0.87, 0.88, 0.89], smooth: true },
    ],
  });

  // 修复类型分布图
  const typeChart = echarts.init(document.getElementById('chartType'));
  typeChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: p => `${p.name}: ${p.value} (${p.percent}%)` },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      data: [
        { value: 35, name: '月收入' },
        { value: 25, name: '职业类型' },
        { value: 20, name: '月供金额' },
        { value: 12, name: '信用历史' },
        { value: 8, name: '其他字段' },
      ],
    }],
  });

  // 字段修复量柱状图
  const fieldChart = echarts.init(document.getElementById('chartField'));
  fieldChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 10, bottom: 30, left: 80 },
    xAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: '#6b7785' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    yAxis: {
      type: 'category',
      data: ['负债比率', '信用历史', '月供金额', '职业类型', '月收入', '信用评分'].reverse(),
      axisLabel: { fontSize: 11, color: '#5f6368' },
    },
    series: [{
      type: 'bar',
      data: [12500, 28900, 35600, 42100, 48500, 52300].reverse(),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#9334e6' },
          { offset: 1, color: '#1a73e8' },
        ]),
      },
      barWidth: 20,
    }],
  });

  // 响应式
  window.addEventListener('resize', () => {
    qualityChart.resize();
    typeChart.resize();
    fieldChart.resize();
  });
}

/* ---------- 辅助函数 ---------- */
function fmtNum(v) {
  return Number(v).toLocaleString('zh-CN');
}

/* ---------- 启动 ---------- */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
