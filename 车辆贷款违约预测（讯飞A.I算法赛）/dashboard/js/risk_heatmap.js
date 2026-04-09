/* ================================================
   风险热力图页面 - Leaflet.js 地图渲染逻辑
   ================================================ */

/* ---------- Mock 地区数据（经纬度） ---------- */
const MockAreaData = [
  // 地区名, 经度, 纬度, 违约率, 客户数, 金额
  { name: '华东区-A', lng: 121.47, lat: 31.23, rate: 0.038, customers: 280000, amount: 42.5 },
  { name: '华东区-B', lng: 118.78, lat: 32.06, rate: 0.052, customers: 195000, amount: 28.3 },
  { name: '华东区-C', lng: 120.15, lat: 30.27, rate: 0.045, customers: 220000, amount: 35.2 },
  { name: '华北区-A', lng: 116.40, lat: 39.90, rate: 0.055, customers: 310000, amount: 48.7 },
  { name: '华北区-B', lng: 117.20, lat: 39.12, rate: 0.063, customers: 175000, amount: 25.1 },
  { name: '华北区-C', lng: 114.48, lat: 38.03, rate: 0.072, customers: 145000, amount: 19.8 },
  { name: '华南区-A', lng: 113.26, lat: 23.13, rate: 0.042, customers: 265000, amount: 41.2 },
  { name: '华南区-B', lng: 110.35, lat: 20.02, rate: 0.048, customers: 130000, amount: 18.5 },
  { name: '华南区-C', lng: 114.06, lat: 22.54, rate: 0.051, customers: 240000, amount: 38.9 },
  { name: '华西区-A', lng: 104.06, lat: 30.67, rate: 0.068, customers: 155000, amount: 21.3 },
  { name: '华西区-B', lng: 106.23, lat: 29.53, rate: 0.123, customers: 95000, amount: 12.6 },
  { name: '华西区-C', lng: 108.93, lat: 35.48, rate: 0.085, customers: 78000, amount: 9.8 },
  { name: '华中区-A', lng: 112.98, lat: 28.20, rate: 0.058, customers: 185000, amount: 26.4 },
  { name: '华中区-B', lng: 114.89, lat: 30.59, rate: 0.062, customers: 165000, amount: 23.1 },
  { name: '华中区-C', lng: 113.65, lat: 34.76, rate: 0.071, customers: 142000, amount: 19.2 },
  { name: '东北区-A', lng: 123.43, lat: 41.80, rate: 0.065, customers: 120000, amount: 15.8 },
  { name: '东北区-B', lng: 125.32, lat: 43.82, rate: 0.058, customers: 98000, amount: 12.3 },
  { name: '西北区-A', lng: 108.94, lat: 34.34, rate: 0.078, customers: 85000, amount: 10.5 },
  { name: '西北区-B', lng: 87.57, lat: 43.83, rate: 0.055, customers: 62000, amount: 7.2 },
  { name: '西南区-A', lng: 101.71, lat: 26.58, rate: 0.095, customers: 72000, amount: 8.9 },
];

/* ---------- 风险颜色映射 ---------- */
function getRiskColor(rate) {
  if (rate >= 0.10) return '#ea4335';  // 红色 - 高风险
  if (rate >= 0.07) return '#f57c00';  // 橙色 - 中高风险
  if (rate >= 0.05) return '#f9ab00';  // 黄色 - 中等风险
  if (rate >= 0.04) return '#34a853';  // 绿色 - 低风险
  return '#1a73e8';                      // 蓝色 - 极低风险
}

function getRiskLevel(rate) {
  if (rate >= 0.10) return '高风险';
  if (rate >= 0.07) return '中高风险';
  if (rate >= 0.05) return '中等风险';
  if (rate >= 0.04) return '低风险';
  return '极低风险';
}

/* ---------- 创建热力图标记（Canvas圆圈代替真实热力图） ---------- */
function createHeatmapMarkers(map, data) {
  data.forEach(area => {
    const color = getRiskColor(area.rate);
    const size = Math.max(30, Math.min(80, area.customers / 5000));

    // 创建圆形标记模拟热力
    const circle = L.circle([area.lat, area.lng], {
      color: 'transparent',
      fillColor: color,
      fillOpacity: 0.35,
      radius: size * 100,
      weight: 0,
    }).addTo(map);

    // 绑定弹窗
    circle.bindPopup(`
      <div style="min-width:200px;">
        <h3 style="margin:0 0 8px 0;font-size:15px;">${area.name}</h3>
        <table style="width:100%;font-size:13px;line-height:1.8;">
          <tr><td>违约率:</td><td><b style="color:${color}">${(area.rate * 100).toFixed(2)}%</b></td></tr>
          <tr><td>风险等级:</td><td><b>${getRiskLevel(area.rate)}</b></td></tr>
          <tr><td>客户数:</td><td>${area.customers.toLocaleString()}</td></tr>
          <tr><td>贷款总额:</td><td>${area.amount.toFixed(1)}亿</td></tr>
        </table>
      </div>
    `, { className: 'leaflet-popup-custom' });

    // 添加小圆点标记
    const marker = L.circleMarker([area.lat, area.lng], {
      radius: 6,
      fillColor: color,
      color: 'white',
      weight: 2,
      fillOpacity: 0.9,
    }).addTo(map);

    marker.bindTooltip(area.name, { permanent: false, direction: 'top' });
  });
}

/* ---------- 初始化地图 ---------- */
let riskMap = null;
let currentFilter = 'all';

function initRiskMap() {
  if (riskMap) return;

  riskMap = L.map('riskMap', {
    center: [35.0, 105.0],
    zoom: 4,
    zoomControl: true,
    scrollWheelZoom: true,
  });

  // 深色地图瓦片
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    maxZoom: 18,
  }).addTo(riskMap);

  // 渲染标记
  createHeatmapMarkers(riskMap, MockAreaData);

  // 地图点击显示详情
  riskMap.on('click', (e) => {
    const { lat, lng } = e.latlng;
    // 找到最近的地区
    let nearest = null;
    let minDist = Infinity;
    MockAreaData.forEach(area => {
      const d = Math.sqrt((area.lat - lat) ** 2 + (area.lng - lng) ** 2);
      if (d < minDist) { minDist = d; nearest = area; }
    });
    if (nearest && minDist < 3) {
      const color = getRiskColor(nearest.rate);
      L.popup()
        .setLatLng([nearest.lat, nearest.lng])
        .setContent(`
          <div>
            <strong>${nearest.name}</strong><br/>
            违约率: <span style="color:${color}"><b>${(nearest.rate * 100).toFixed(2)}%</b></span><br/>
            ${getRiskLevel(nearest.rate)} · ${nearest.customers.toLocaleString()}客户
          </div>
        `)
        .openOn(riskMap);
    }
  });
}

/* ---------- 过滤热力点 ---------- */
function setHeatmapFilter(filter) {
  currentFilter = filter;

  // 更新tab状态
  document.querySelectorAll('.filter-tab').forEach(btn => {
    btn.classList.remove('active');
  });
  event?.target?.classList?.add('active') ||
    document.querySelector(`.filter-tab[onclick*="${filter}"]`)?.classList?.add('active');

  // 重新过滤渲染
  if (!riskMap) return;

  // 移除所有图层重新渲染
  riskMap.eachLayer(layer => {
    if (!(layer instanceof L.TileLayer)) {
      riskMap.removeLayer(layer);
    }
  });

  const filtered = MockAreaData.filter(area => {
    if (filter === 'all') return true;
    if (filter === 'high') return area.rate >= 0.07;
    if (filter === 'medium') return area.rate >= 0.05 && area.rate < 0.07;
    if (filter === 'low') return area.rate < 0.05;
    return true;
  });

  createHeatmapMarkers(riskMap, filtered);
}

/* ---------- 页面初始化 ---------- */
function boot() {
  // 检查登录状态
  const user = checkAuth();
  if (!user) {
    window.location.href = '/login';
    return;
  }

  // 延迟初始化地图，等待DOM就绪
  setTimeout(initRiskMap, 300);

  // 模拟加载数据
  updateAreaStats();
}

/* ---------- 更新地区统计 ---------- */
function updateAreaStats() {
  const high = MockAreaData.filter(a => a.rate >= 0.07).length;
  const med = MockAreaData.filter(a => a.rate >= 0.05 && a.rate < 0.07).length;
  const low = MockAreaData.filter(a => a.rate < 0.05).length;
  const avg = MockAreaData.reduce((sum, a) => sum + a.rate, 0) / MockAreaData.length;

  const elHigh = document.getElementById('statHighRisk');
  const elMed = document.getElementById('statMedRisk');
  const elLow = document.getElementById('statLowRisk');
  const elAvg = document.getElementById('statAvgRate');

  if (elHigh) elHigh.textContent = high;
  if (elMed) elMed.textContent = med;
  if (elLow) elLow.textContent = low;
  if (elAvg) elAvg.textContent = (avg * 100).toFixed(1) + '%';
}

/* ---------- 加载API数据（备用） ---------- */
async function loadHeatmapData() {
  const [areaRisk] = await Promise.all([
    API.statsAreaRisk(),
  ]);

  if (areaRisk && areaRisk.length > 0) {
    // 如果API返回真实数据，使用它
    // 当前使用Mock数据
  }
}

/* ---------- 启动 ---------- */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
