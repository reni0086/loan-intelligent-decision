async function loadOverview() {
  const [healthResp, statsResp, riskResp] = await Promise.all([
    fetch("/health"),
    fetch("/stats/overview"),
    fetch("/stats/risk_daily"),
  ]);
  const health = await healthResp.json();
  const stats = await statsResp.json();
  const risk = await riskResp.json();
  document.getElementById("events").textContent = stats.realtime_events ?? 0;
  document.getElementById("decisions").textContent = stats.realtime_decisions ?? 0;
  document.getElementById("health").textContent = health.status ?? "unknown";
  window.__riskDaily = Array.isArray(risk) ? risk : [];
}

function renderCharts() {
  const pie = echarts.init(document.getElementById("riskPie"));
  pie.setOption({
    tooltip: { trigger: "item" },
    series: [
      {
        type: "pie",
        radius: "65%",
        data: [
          { value: 70, name: "低风险" },
          { value: 20, name: "中风险" },
          { value: 10, name: "高风险" },
        ],
      },
    ],
  });

  const line = echarts.init(document.getElementById("riskLine"));
  const fallbackX = ["1月", "2月", "3月", "4月", "5月", "6月"];
  const fallbackY = [6.8, 6.5, 6.2, 6.0, 5.9, 5.7];
  const riskDaily = window.__riskDaily || [];
  const xData = riskDaily.length ? riskDaily.map((x) => x.dt).reverse() : fallbackX;
  const yData = riskDaily.length ? riskDaily.map((x) => Number(x.default_rate || 0) * 100).reverse() : fallbackY;
  line.setOption({
    xAxis: { type: "category", data: xData },
    yAxis: { type: "value", name: "逾期率%" },
    series: [{ type: "line", data: yData, smooth: true }],
  });
}

async function boot() {
  await loadOverview();
  renderCharts();
}

boot().catch(console.error);
setInterval(() => boot().catch(console.error), 5000);

