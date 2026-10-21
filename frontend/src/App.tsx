import { lazy, Suspense, useEffect, useState } from 'react'
import { Activity, ArrowDownLeft, ArrowUpRight, Check, ChevronRight, CircleHelp, Cpu, Download, FlaskConical, Gauge, LayoutDashboard, Play, PlugZap, Radio, RefreshCw, ShieldCheck, Square, Terminal, Unplug, Zap } from 'lucide-react'
import { useTerminal } from './useTerminal'
import type { Mode, Port, DataSource, Execution } from './types'
import { averageHostMs } from './telemetry'
import DataControls from './DataControls'
import PaperPanel from './PaperPanel'
import ExecutionControls from './ExecutionControls'
import PerformancePanel from './PerformancePanel'
import Onboarding from './Onboarding'
import { rememberGuide, shouldShowGuide } from './onboardingContent'
const MarketChart = lazy(() => import('./MarketChart'))

const signed = (n: number) => `${n > 0 ? '+' : ''}${n}`
const number = (n: number) => n.toLocaleString('en-US')

export default function App() {
  const { status, rows, connected, error, clientId, send, clearHistory } = useTerminal()
  const [mode, setMode] = useState<Mode>('simulation')
  const [source,setSource] = useState<DataSource>('generated')
  const [symbol,setSymbol] = useState('AAPL')
  const [replayId,setReplayId] = useState('demo')
  const [execution,setExecution] = useState<Execution>('local')
  const [paperConfirmed,setPaperConfirmed] = useState(false)
  const [feeBps,setFeeBps] = useState(1)
  const [speed, setSpeed] = useState(5)
  const [port, setPort] = useState('')
  const [ports, setPorts] = useState<Port[]>([])
  const [portError, setPortError] = useState('')
  const [reset, setReset] = useState(false)
  const [filter, setFilter] = useState('ALL')
  const [help, setHelp] = useState(false)
  const [guideOpen,setGuideOpen] = useState(shouldShowGuide)
  function dismissGuide() { rememberGuide(); setGuideOpen(false) }
  const running = status.state === 'running' || status.state === 'stopping'
  const owned = status.owner === clientId
  const currentMode = running ? status.mode : mode
  const latest = rows.at(-1)
  const position = latest?.position ?? 0
  const risk = Math.abs(position)
  const trades = rows.filter(row => row.order !== 0)
  const buyCount = trades.filter(row => row.order > 0).length
  const sellCount = trades.length - buyCount
  const meanLatency = averageHostMs(rows)
  const visibleRows = rows.filter(row => filter === 'ALL' || row.decision === filter).slice(-12).reverse()
  async function refreshPorts() {
    try {
      const response = await fetch('/api/ports')
      if (!response.ok) throw new Error('Unable to enumerate serial ports.')
      const found: Port[] = await response.json()
      setPorts(found); setPortError('')
      setPort(previous => previous || found.find(p => p.hwid.includes('0403:6010'))?.device || found[0]?.device || '')
    } catch { setPortError('Could not load ports. Check the backend connection.') }
  }
  useEffect(() => { if (connected) void refreshPorts() }, [connected])
  useEffect(() => { setMode(status.mode); setExecution(status.execution ?? 'local'); if (status.source) setSource(status.source); if (status.symbol && status.symbol !== 'DEMO') setSymbol(status.symbol); if (status.replay_id) setReplayId(status.replay_id) }, [status.run_id])
  useEffect(() => { if (running) { setMode(status.mode); setSpeed(status.speed) } }, [running, status.mode, status.speed])
  useEffect(() => { setReset(false); setPaperConfirmed(false) }, [status.run_id, status.state])
  function start() { send({ command: 'start', config: { mode, speed, seed: 1, port: mode === 'fpga' ? port : '', reset_confirmed: reset, source, symbol, replay_id: replayId, fee_bps: feeBps, execution, paper_confirmed:paperConfirmed } }) }
  function exportData() {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `nanoquant-${latest?.run_id ?? 'session'}.json`; a.click(); URL.revokeObjectURL(url)
  }
  return <div className="app-shell">
    <Onboarding open={guideOpen} onDismiss={dismissGuide}/>
    <aside className="sidebar">
      <a href="#overview" className="brand"><span className="brand-mark">N</span><span>NanoQuant<span className="brand-tag">TRADING SYSTEMS</span></span></a>
      <div className="workspace-label">WORKSPACE <span>01</span></div>
      <a className="nav-item active" href="#overview"><LayoutDashboard size={17}/> Overview <span className="nav-key">⌘ 1</span></a>
      <a className="nav-item" href="#decisions"><Activity size={17}/> Decision feed</a>
      <a className="nav-item" href="#engine"><Cpu size={17}/> Engine & risk</a>
      <div className="sidebar-divider"/>
      <div className="workspace-label">CONNECTED HARDWARE</div>
      <div className="hardware-mini"><span className="chip-icon"><Cpu size={21}/></span><div>Tang Nano 9K<small>{running && status.mode === 'fpga' ? `${status.port} · UART active` : 'FPGA engine · 27 MHz'}</small></div></div>
      <div className="sidebar-bottom"><span className="pill subtle"><span className="dot"/> Local workspace</span><p>Deterministic by design.<br/>Observable at every step.</p><button className="nav-item" onClick={() => setHelp(!help)}><CircleHelp size={17}/> How it works <ArrowUpRight size={15}/></button><div className="version"><span className="avatar">NQ</span><div>Research environment<small>v0.1 · Simulated orders only</small></div></div></div>
    </aside>
    <div className="main-shell" id="overview">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={13}/><span>Trading terminal</span></div><div className="flex items-center gap-4"><span className={`connection ${connected ? 'online' : ''}`}><span className="dot"/>{connected ? 'Backend connected' : 'Backend offline'}</span><button className="button secondary intro-trigger" onClick={() => setGuideOpen(true)}><CircleHelp size={14}/> Introduction</button><button className="icon-button" aria-label="Show system help" onClick={() => setHelp(!help)}><CircleHelp size={18}/></button></div></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow">YOUR ENGINE. IN REAL TIME.</div><h1>Trading terminal<span className="title-dot">.</span></h1><p>A clear view of every quote, decision, and microsecond.</p></div><button className="button secondary" disabled={!rows.length} onClick={exportData}><Download size={15}/> Export session</button></div>
        {help && <div className="notice">Market data source and execution engine are independent. Choose generated prices, real Alpaca IEX trade prints, or a replay. Python engine computes locally; FPGA Live validates physical board decisions. Stock prices map to basis-point ticks around the first sample; one stock and portfolio per run. Stop pauses generation; kill latches trading off. Physical reset is required before every FPGA run. No exchange or real money is connected.</div>}
        <section className="control-bar" aria-label="Run controls"><div className="mode-switch"><button disabled={running} className={currentMode === 'simulation' ? 'selected' : ''} onClick={() => { setMode('simulation'); setReset(false); clearHistory() }}><FlaskConical size={15}/> Python engine</button><button disabled={running} className={currentMode === 'fpga' ? 'selected' : ''} onClick={() => { setMode('fpga'); setReset(false); clearHistory() }}><Cpu size={15}/> FPGA Live</button></div><div className="control-separator"/><span className="data-source"><span className="dot"/>{currentMode === 'simulation' ? 'Python reference · demo data' : 'Physical UART · simulated market'}</span><div className="run-controls"><label className="speed-label">Speed <input aria-label="Quotes per second" type="range" min="1" max="20" value={speed} disabled={running && !owned} onChange={e => { const value = +e.target.value; setSpeed(value); if (running) send({ command: 'speed', speed: value }) }}/><span>{speed}/s</span></label><button className={`button ${running ? 'secondary' : 'primary'}`} disabled={!connected || status.state === 'stopping' || (running && !owned) || (!running && execution === 'alpaca_paper' && (!paperConfirmed || source !== 'live')) || (!running && mode === 'fpga' && (!port || !reset))} onClick={() => running ? send({ command: 'stop' }) : start()}>{running ? <Square size={13}/> : <Play size={14}/>} {status.state === 'stopping' ? 'Stopping…' : running ? 'Stop run' : 'Start run'}</button></div></section>
        <ExecutionControls execution={execution} setExecution={value=>{setExecution(value);setPaperConfirmed(false);clearHistory();if(value==='alpaca_paper')setSource('live')}} confirmed={paperConfirmed} setConfirmed={setPaperConfirmed} symbol={symbol} disabled={running}/>
        <DataControls source={source} setSource={value => { setSource(value); clearHistory(); setReset(false) }} symbol={symbol} setSymbol={setSymbol} replayId={replayId} setReplayId={setReplayId} feeBps={feeBps} setFeeBps={setFeeBps} disabled={running} connected={connected}/>
        {source === 'live' && running && !latest && <div className="notice">Waiting for fresh Alpaca IEX trades. Closed markets may have no events; generated prices are never substituted.</div>}
        {currentMode === 'fpga' && <section className="hardware-controls"><PlugZap size={17}/><label>UART port <select aria-label="COM port" value={port} disabled={running} onChange={e => { setPort(e.target.value); setReset(false) }}><option value="">Select a port</option>{ports.map(p => <option key={p.device} value={p.device}>{p.device} · {p.description}</option>)}</select></label><button className="icon-button" disabled={running} aria-label="Refresh serial ports" onClick={() => void refreshPorts()}><RefreshCw size={15}/></button><label className="reset-check"><input type="checkbox" checked={reset} disabled={running} onChange={e => setReset(e.target.checked)}/> I physically reset the FPGA for this run</label><span>115200 · 8N1</span></section>}
        {(error || portError) && <div className="notice error" role="alert"><Unplug size={17}/><span>{error || portError} {currentMode === 'fpga' && 'No trade is retried. Reset the board before a fresh run.'}</span></div>}
        {status.reset_required && <div className="notice warning"><ShieldCheck size={17}/> FPGA state requires physical reset before the next live run. A browser action cannot clear the hardware latch.</div>}
        {running && !owned && <div className="notice">Another browser tab owns this run. This tab is a read-only observer.</div>}
        <section className="metric-grid">
          <article className="metric-card"><div className="metric-label">Market price <Activity size={15}/></div><div className="metric-value">{latest ? number(latest.price) : '—'}<span>ticks</span></div><div className="metric-foot"><span className="token-icon">N</span> NQ / TICK <span className="muted">· simulated market</span></div></article>
          <article className="metric-card"><div className="metric-label">Net position <Gauge size={15}/></div><div className="metric-value">{latest ? signed(position) : '—'}<span>units</span></div><div className="metric-foot"><span className={`mini-dot ${risk >= 80 ? 'amber' : ''}`}/>{risk >= 100 ? 'Position limit reached' : risk >= 80 ? 'Approaching position limit' : 'Within position limits'}<span className="muted">±100</span></div></article>
          <article className="metric-card"><div className="metric-label">Latest decision <Zap size={15}/></div><div className={`metric-value decision-text ${latest?.decision.toLowerCase() ?? ''}`}>{latest?.decision ?? 'READY'}{latest && <span>{signed(latest.order)} units</span>}</div><div className="metric-foot">{latest ? <><span className="mini-dot"/>{latest.validation_status === 'matched' ? 'FPGA matches Python' : 'Python reference result'}</> : <><span className="mini-dot neutral"/>Waiting for first quote</>}</div></article>
          <article className="metric-card"><div className="metric-label">Host round trip <Radio size={15}/></div><div className="metric-value">{meanLatency?.toFixed(2) ?? '—'}<span>ms</span></div><div className="metric-foot"><span className="latency-bars">▂▃▅▇</span>{meanLatency === null ? 'Available in FPGA Live' : 'Measured · UART + USB + host'}</div></article>
        </section>
        <div className="chart-layout"><Suspense fallback={<section className="panel chart-panel chart-loading">Loading chart?</section>}><MarketChart rows={rows} state={status.state} running={running}/></Suspense>
        <section className="panel engine-panel" id="engine"><div className="panel-heading"><h2>Engine & risk</h2><ShieldCheck size={17} className="muted"/></div><div className="engine-emblem"><Cpu size={27}/><div>{currentMode === 'fpga' ? 'Tang Nano 9K' : 'Python reference'}<span>{currentMode === 'fpga' ? 'Physical FPGA execution' : 'Deterministic simulation'}</span><span className={`engine-badge ${latest?.killed ? 'killed' : ''}`}>{latest?.killed ? 'KILL LATCHED' : running ? 'RUNNING' : 'STANDBY'}</span></div></div><div className="risk-header"><span>Position exposure</span><strong>{risk}<span> / 100</span></strong></div><div className="risk-track"><div style={{ width: `${risk}%`, background: risk >= 80 ? '#e9b66d' : '#42dba0' }}/></div><div className="risk-scale"><span>0</span><span>50</span><span>100 units</span></div><dl className="engine-details"><div><dt>Max order size</dt><dd>20 units</dd></div><div><dt>Position limit</dt><dd>±100 units</dd></div><div><dt>Signal threshold</dt><dd>±5 ticks</dd></div><div><dt>Decision validation</dt><dd className="green-text">{latest?.validation_status === 'matched' ? 'Matched' : latest ? 'Reference' : 'Awaiting data'}</dd></div><div><dt>Python step (measured)</dt><dd>{latest?.python_compute_us != null ? `${latest.python_compute_us.toFixed(1)} ?s` : '?'}</dd></div><div><dt>Engine architecture</dt><dd>{latest?.engine_cycles ?? '—'} cycle</dd></div></dl><div className="engine-estimate"><Zap size={14}/><span>{latest?.estimated_engine_ns ? `~${latest.estimated_engine_ns.toFixed(2)} ns architectural estimate` : 'FPGA estimate available in live mode'}<small>1 cycle at 27 MHz. Not measured physical latency.</small></span></div><button className="kill-button" disabled={!running || !owned || status.state === 'stopping' || status.kill_pending} onClick={() => send({ command: 'kill' })}><Square size={13}/> {status.kill_pending ? 'Awaiting kill reply?' : 'Latch kill switch'} <span>STOP TRADING</span></button><p className="kill-note">{currentMode === 'fpga' ? 'Clearing kill requires a physical board reset.' : 'Simulation kill clears on a new run.'}</p></section></div>
        <div className="research-grid"><PaperPanel latest={latest} accountMode={execution === 'alpaca_paper'} broker={running ? latest?.broker ?? status.broker : status.broker}/><PerformancePanel latest={latest} metrics={running ? latest?.performance ?? status.performance : status.performance}/></div>
        <section className="panel history-panel" id="decisions"><div className="panel-heading"><div className="flex items-center gap-3"><h2>Decision feed</h2><span className="pill subtle">{rows.length} captured</span></div><div className="segmented">{['ALL','BUY','SELL','HOLD'].map(value => <button key={value} className={filter === value ? 'selected' : ''} onClick={() => setFilter(value)}>{value === 'ALL' ? 'All decisions' : value}</button>)}</div></div><div className="table-scroll"><table><thead><tr><th>Sequence</th><th>Time</th><th>Market price</th><th>Decision</th><th>Order / requested</th><th>Position</th><th>Host round trip</th><th>Validation</th></tr></thead><tbody>{visibleRows.map(row => <tr key={`${row.run_id}-${row.sequence}`}><td className="mono muted">#{String(row.sequence).padStart(4,'0')}</td><td className="muted">{new Date(row.timestamp).toLocaleTimeString('en-US', { hour12: false })}</td><td className="mono">{row.price_usd != null ? `$${row.price_usd.toFixed(2)}` : '?'} <span className="muted tiny">({row.price} ticks)</span></td><td><span className={`signal ${row.decision.toLowerCase()}`}>{row.order > 0 ? <ArrowUpRight size={12}/> : row.order < 0 ? <ArrowDownLeft size={12}/> : null}{row.decision}</span></td><td className="mono">{signed(row.order)} <span className="muted">/ {row.quantity}</span></td><td className="mono">{signed(row.position)}</td><td className="mono muted">{row.host_round_trip_us === null ? '—' : `${(row.host_round_trip_us/1000).toFixed(2)} ms`}</td><td><span className="validation"><Check size={12}/>{row.validation_status === 'matched' ? 'Matched' : 'Reference'}</span></td></tr>)}</tbody></table>{!visibleRows.length && <div className="empty-table"><Terminal size={20}/><span>{rows.length ? 'No decisions match this filter.' : 'Decision history will appear when your run starts.'}</span></div>}</div><div className="history-footer"><span><span className="mini-dot"/> {currentMode === 'fpga' ? 'Physical responses verified against Python' : 'Simulation · Python reference decisions'}</span><span>{buyCount} buys <span className="muted">/</span> {sellCount} sells <span className="muted">·</span> last 240 quotes retained</span></div></section>
        <footer className="page-footer"><span><ShieldCheck size={13}/> Research terminal · all orders and fills are simulated</span><span>NANOQUANT <span className="muted">/</span> ENGINEERED FOR CLARITY</span></footer>
      </main>
    </div>
  </div>
}
