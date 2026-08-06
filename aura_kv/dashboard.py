from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .monitoring import build_state_snapshot, read_jsonl


DASHBOARD_HTML = r"""
<div id="aura-dashboard">
  <style>
    #aura-dashboard { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; background: #f7f9fc; min-height: 100vh; padding: 16px; }
    #aura-dashboard * { box-sizing: border-box; }
    .top { display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px; align-items: stretch; }
    .panel { background: #fff; border: 1px solid #d8dee9; border-radius: 8px; padding: 12px; box-shadow: 0 1px 2px rgba(15,23,42,.05); }
    .status-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
    .metric-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
    .metric { background: #f1f5f9; border: 1px solid #dbe3ef; border-radius: 6px; padding: 8px; min-height: 62px; }
    .metric b { display: block; font-size: 12px; font-weight: 500; color: #52606d; }
    .metric span { display: block; margin-top: 6px; font-size: 20px; font-weight: 500; }
    .flow { display: grid; grid-template-columns: repeat(10, minmax(70px, 1fr)); gap: 6px; margin-top: 12px; }
    .flow div { background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 6px; padding: 6px; font-size: 12px; text-align: center; }
    .main { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { border-bottom: 1px solid #e5eaf1; padding: 6px; text-align: left; vertical-align: top; }
    th { color: #52606d; font-weight: 500; background: #f8fafc; position: sticky; top: 0; }
    .table-wrap { max-height: 310px; overflow: auto; border: 1px solid #e5eaf1; border-radius: 6px; }
    .badge { display: inline-block; border-radius: 999px; padding: 2px 7px; background: #e5e7eb; font-size: 11px; }
    .ok { background: #dcfce7; color: #166534; }
    .warn { background: #fef3c7; color: #92400e; }
    .bad { background: #fee2e2; color: #991b1b; }
    .filters { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
    input, select, button { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 8px; background: #fff; }
    button { cursor: pointer; }
    .chart { width: 100%; height: 180px; display: block; background: #f8fafc; border: 1px solid #e5eaf1; border-radius: 6px; }
    .trace { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 6px; max-height: 260px; overflow: auto; font-size: 12px; }
    @media (max-width: 900px) { .top, .main { grid-template-columns: 1fr; } .metric-grid { grid-template-columns: repeat(2, 1fr); } .flow { grid-template-columns: repeat(2, 1fr); } }
  </style>

  <div class="top">
    <section class="panel">
      <div class="status-grid" id="status"></div>
      <div class="flow" id="flow"></div>
    </section>
    <section class="panel">
      <div class="filters">
        <input id="traceQuery" placeholder="request_id / task_id / cache_key">
        <button id="pauseBtn">暂停滚动</button>
        <select id="sourceFilter">
          <option value="">全部来源</option>
          <option value="LOCAL">LOCAL</option>
          <option value="PEER">PEER</option>
          <option value="REMOTE">REMOTE</option>
          <option value="RECOMPUTE">RECOMPUTE</option>
        </select>
      </div>
      <div class="trace" id="trace"></div>
    </section>
  </div>

  <div class="metric-grid" id="metrics"></div>

  <div class="main">
    <section class="panel">
      <h3>前台请求实时流</h3>
      <div class="table-wrap"><table><thead><tr><th>时间</th><th>请求</th><th>节点</th><th>Cache</th><th>来源</th><th>Latency Proxy</th></tr></thead><tbody id="requests"></tbody></table></div>
    </section>
    <section class="panel">
      <h3>控制器周期和候选</h3>
      <div class="table-wrap"><table><thead><tr><th>Cycle</th><th>Candidate</th><th>Action</th><th>Cache</th><th>Target</th><th>Decision</th><th>Reason</th></tr></thead><tbody id="candidates"></tbody></table></div>
    </section>
    <section class="panel">
      <h3>后台任务队列</h3>
      <div class="table-wrap"><table><thead><tr><th>Task</th><th>Action</th><th>Cache</th><th>Source</th><th>Target</th><th>State</th><th>Retry</th></tr></thead><tbody id="tasks"></tbody></table></div>
    </section>
    <section class="panel">
      <h3>Node × Cache 副本矩阵</h3>
      <div class="table-wrap"><table><thead><tr><th>Cache</th><th>Node</th><th>State</th><th>Bytes</th><th>Layout</th><th>Task</th></tr></thead><tbody id="layout"></tbody></table></div>
    </section>
    <section class="panel">
      <h3>指标时间序列</h3>
      <svg class="chart" id="chart" viewBox="0 0 900 180" preserveAspectRatio="none"></svg>
    </section>
    <section class="panel">
      <h3>最近事件</h3>
      <div class="table-wrap"><table><thead><tr><th>时间</th><th>组件</th><th>事件</th><th>ID</th><th>说明</th></tr></thead><tbody id="events"></tbody></table></div>
    </section>
  </div>
</div>
<script>
(function(){
  const root = document.getElementById('aura-dashboard');
  let paused = false;
  let lastState = null;
  const fmtTime = t => t ? new Date(t * 1000).toLocaleTimeString() : '';
  const mib = b => ((Number(b || 0) / 1048576).toFixed(1) + ' MiB');
  const safe = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function badge(value){
    const v = String(value || '');
    let cls = 'badge';
    if (['RUNNING','CONNECTED','READY','COMMITTED','LOCAL_HIT'].includes(v)) cls += ' ok';
    if (['IDLE','VERIFYING','PENDING','REMOTE_HIT'].includes(v)) cls += ' warn';
    if (['FAILED','CANCELED','DISCONNECTED','STALE'].includes(v)) cls += ' bad';
    return `<span class="${cls}">${safe(v)}</span>`;
  }
  function metric(label, value){ return `<div class="metric"><b>${safe(label)}</b><span>${safe(value)}</span></div>`; }
  function row(cells){ return '<tr>' + cells.map(x => `<td>${x}</td>`).join('') + '</tr>'; }
  function latestByType(events, types){
    return events.filter(e => types.includes(e.event_type)).slice(-80).reverse();
  }
  function render(state){
    lastState = state;
    const m = state.latest_metrics || {};
    const manifest = state.manifest || {};
    root.querySelector('#status').innerHTML = [
      metric('Status', badge(manifest.status)),
      metric('Mode', manifest.simulated ? 'SIMULATED' : 'REAL'),
      metric('Run ID', manifest.run_id || ''),
      metric('Policy', manifest.policy || ''),
      metric('Workload', manifest.workload || ''),
      metric('Layout', m.current_layout_version || 0),
      metric('Events', state.event_count || 0),
      metric('Connection', badge(manifest.connection))
    ].join('');
    root.querySelector('#metrics').innerHTML = [
      metric('Requests', m.request_count || 0),
      metric('RPS', Number(m.requests_per_second || 0).toFixed(2)),
      metric('P50 Proxy', Number(m.p50_proxy || 0).toFixed(3) + ' ms'),
      metric('P95 Proxy', Number(m.p95_proxy || 0).toFixed(3) + ' ms'),
      metric('P99 Proxy', Number(m.p99_proxy || 0).toFixed(3) + ' ms'),
      metric('Remote Bytes', mib(m.remote_bytes)),
      metric('Duplicate Bytes', mib(m.duplicate_bytes)),
      metric('Migration Bytes', mib(m.migration_bytes)),
      metric('Tasks', `${m.task_queue_length||0}/${m.running_task_count||0}/${m.committed_task_count||0}`),
      metric('Candidates', `${m.accepted_candidate_count||0}/${m.rejected_candidate_count||0}`),
      metric('ReplicaGain', Number(m.replica_gain_ms || 0).toFixed(2)),
      metric('EvictionLoss', Number(m.eviction_loss_ms || 0).toFixed(2))
    ].join('');
    const flow = [
      ['REQUEST', m.request_count], ['ACCESS EVENT', countEvents(state, 'ACCESS_EVENT_RECORDED')],
      ['DEMAND', countEvents(state, 'DEMAND_UPDATED')], ['CANDIDATE', m.candidate_count],
      ['DECISION', (m.accepted_candidate_count||0) + (m.rejected_candidate_count||0)],
      ['ACTION PLAN', countEvents(state, 'ACTION_PLAN_CREATED')], ['TASK', countEvents(state, 'TASK_CREATED')],
      ['EXECUTION', (m.running_task_count||0) + (m.verifying_task_count||0)],
      ['COMMIT', m.committed_task_count], ['NEW LAYOUT', m.current_layout_version]
    ];
    root.querySelector('#flow').innerHTML = flow.map(([a,b]) => `<div>${safe(a)}<br><b>${safe(b||0)}</b></div>`).join('');
    renderRequests(state); renderCandidates(state); renderTasks(state); renderLayout(state); renderEvents(state); renderChart(state);
    if (!paused) renderTrace(state);
  }
  function countEvents(state, type){ return (state.events || []).filter(e => e.event_type === type).length; }
  function renderRequests(state){
    const filter = root.querySelector('#sourceFilter').value;
    const rows = latestByType(state.events || [], ['REQUEST_COMPLETED','LOCAL_HIT','PEER_HIT','REMOTE_HIT','RECOMPUTE'])
      .filter(e => !filter || e.event_type.includes(filter))
      .slice(0, 80)
      .map(e => row([fmtTime(e.timestamp), safe(e.request_id), safe(e.node_id), safe(e.cache_key), badge(e.event_type), Number(e.latency_ms||0).toFixed(3)]));
    root.querySelector('#requests').innerHTML = rows.join('');
  }
  function renderCandidates(state){
    const rows = (state.candidates || []).slice(-80).reverse().map(e => row([
      safe(e.controller_cycle_id), safe(e.candidate_id), safe(e.decision || e.extra?.action_type || ''),
      safe(e.cache_key), safe(e.target), badge(e.event_type.replace('CANDIDATE_','')), safe(e.reason)
    ]));
    root.querySelector('#candidates').innerHTML = rows.join('');
  }
  function renderTasks(state){
    const rows = (state.tasks || []).slice(-80).reverse().map(t => row([
      safe(t.task_id), safe(t.action_type), safe(t.cache_key), safe(t.source), safe(t.target), badge(t.state), safe(t.retry_count || 0)
    ]));
    root.querySelector('#tasks').innerHTML = rows.join('');
  }
  function renderLayout(state){
    const rows = (state.layout || []).slice(-120).map(x => row([
      safe(x.cache_key), safe(x.node_id), badge(x.state), mib(x.object_bytes), safe(x.layout_version || ''), safe(x.task_id || '')
    ]));
    root.querySelector('#layout').innerHTML = rows.join('');
  }
  function renderEvents(state){
    const rows = (state.events || []).slice(-100).reverse().map(e => row([
      fmtTime(e.timestamp), safe(e.component), badge(e.event_type), safe(e.request_id || e.task_id || e.candidate_id || ''), safe(e.reason || e.error_message || '')
    ]));
    root.querySelector('#events').innerHTML = rows.join('');
  }
  function renderTrace(state){
    const q = root.querySelector('#traceQuery').value.trim();
    if (!q) { root.querySelector('#trace').textContent = '输入 request_id / task_id / cache_key 查看链路'; return; }
    const rows = (state.events || []).filter(e =>
      [e.request_id,e.task_id,e.cache_key,e.candidate_id,e.action_id].some(v => String(v || '').includes(q))
    ).sort((a,b) => a.timestamp - b.timestamp);
    root.querySelector('#trace').textContent = rows.map(e => `${fmtTime(e.timestamp)} ${e.component} ${e.event_type} req=${e.request_id||'-'} task=${e.task_id||'-'} cache=${e.cache_key||'-'} ${e.reason||e.error_message||''}`).join('\n') || '没有匹配事件';
  }
  function renderChart(state){
    const svg = root.querySelector('#chart');
    const series = (state.series || []).slice(-120);
    const w = 900, h = 180, pad = 22;
    svg.innerHTML = '';
    if (series.length < 2) { svg.innerHTML = '<text x="20" y="92" fill="#52606d">等待时间序列数据</text>'; return; }
    const keys = ['remote_bytes','duplicate_bytes','migration_bytes','p99_proxy'];
    const max = Math.max(1, ...series.flatMap(p => keys.map(k => Number(p[k] || 0))));
    const colors = ['#2563eb','#16a34a','#f59e0b','#dc2626'];
    keys.forEach((key, ki) => {
      const pts = series.map((p, i) => {
        const x = pad + i * (w - pad*2) / Math.max(1, series.length - 1);
        const y = h - pad - (Number(p[key] || 0) / max) * (h - pad*2);
        return `${x},${y}`;
      }).join(' ');
      const poly = document.createElementNS('http://www.w3.org/2000/svg','polyline');
      poly.setAttribute('points', pts); poly.setAttribute('fill','none'); poly.setAttribute('stroke', colors[ki]); poly.setAttribute('stroke-width','2');
      svg.appendChild(poly);
      const text = document.createElementNS('http://www.w3.org/2000/svg','text');
      text.setAttribute('x', pad + ki * 165); text.setAttribute('y', 16); text.setAttribute('fill', colors[ki]); text.textContent = key;
      svg.appendChild(text);
    });
  }
  async function tick(){
    try {
      const r = await fetch('/api/state');
      render(await r.json());
    } catch (err) {
      if (lastState) { lastState.manifest.connection = 'DISCONNECTED'; render(lastState); }
    }
  }
  root.querySelector('#pauseBtn').addEventListener('click', () => { paused = !paused; root.querySelector('#pauseBtn').textContent = paused ? '继续滚动' : '暂停滚动'; });
  root.querySelector('#traceQuery').addEventListener('input', () => lastState && renderTrace(lastState));
  root.querySelector('#sourceFilter').addEventListener('change', () => lastState && renderRequests(lastState));
  tick(); setInterval(tick, 1000);
})();
</script>
"""


class AuraDashboardHandler(BaseHTTPRequestHandler):
    run_dir: Path

    def log_message(self, format: str, *args: object) -> None:
        return None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_text(DASHBOARD_HTML, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/state":
            qs = parse_qs(parsed.query)
            event_limit = int(qs.get("event_limit", ["300"])[0])
            payload = build_state_snapshot(self.run_dir, event_limit=event_limit)
            self._send_json(payload)
            return
        if parsed.path == "/api/events":
            qs = parse_qs(parsed.query)
            query = qs.get("query", [""])[0]
            rows = read_jsonl(self.run_dir / "events.jsonl")
            if query:
                rows = [
                    row for row in rows
                    if any(query in str(row.get(key, "")) for key in ["request_id", "task_id", "cache_key", "candidate_id", "action_id"])
                ]
            self._send_json({"events": rows[-500:]})
            return
        if parsed.path.startswith("/files/"):
            self._send_file(self.run_dir / parsed.path.removeprefix("/files/"))
            return
        self.send_error(404)

    def _send_json(self, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        resolved = path.resolve()
        if not str(resolved).startswith(str(self.run_dir.resolve())) or not resolved.exists() or not resolved.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        body = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class DashboardServer:
    def __init__(self, run_dir: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.run_dir = Path(run_dir)
        self.host = host
        self.port = port
        handler_cls = type("BoundAuraDashboardHandler", (AuraDashboardHandler,), {"run_dir": self.run_dir})
        self.httpd = ThreadingHTTPServer((host, port), handler_cls)
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host = self.httpd.server_address[0]
        port = self.httpd.server_address[1]
        return f"http://{host}:{port}"

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def start_background(self) -> None:
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2.0)
