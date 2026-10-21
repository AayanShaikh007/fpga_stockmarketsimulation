import { useEffect, useState } from 'react'
import { Database, Download, RefreshCw } from 'lucide-react'
import type { DataSource, Replay } from './types'

interface Props {
  source: DataSource; setSource: (s: DataSource) => void
  symbol: string; setSymbol: (s: string) => void
  replayId: string; setReplayId: (s: string) => void
  feeBps: number; setFeeBps: (n: number) => void
  disabled: boolean; connected: boolean
}

export default function DataControls(props: Props) {
  const [configured, setConfigured] = useState(false)
  const [datasets, setDatasets] = useState<Replay[]>([])
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState(false)
  const day = (offset: number) => new Date(Date.now() - offset*86400000).toISOString().slice(0,10)
  const [start, setStart] = useState(day(7))
  const [end, setEnd] = useState(day(1))
  const [timeframe, setTimeframe] = useState('1Min')
  async function refresh() {
    try {
      const [provider, replays] = await Promise.all([fetch('/api/provider'),fetch('/api/replays')])
      if (!provider.ok || !replays.ok) throw new Error('Market-data service is unavailable')
      setConfigured((await provider.json()).configured)
      setDatasets(await replays.json()); setError('')
    } catch (e) { setError(e instanceof Error ? e.message : 'Source setup failed') }
  }
  useEffect(() => { if (props.connected) void refresh() }, [props.connected])
  async function download() {
    setDownloading(true); setError('')
    try {
      const response = await fetch('/api/replays/download', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ symbol: props.symbol, start:`${start}T00:00:00Z`,end:`${end}T23:59:59Z`,timeframe }) })
      const result = await response.json()
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Invalid date range or download request')
      await refresh(); props.setReplayId(result.id)
    } catch (e) { setError(e instanceof Error ? e.message : 'Download failed') }
    finally { setDownloading(false) }
  }
  const selected = datasets.find(d => d.id === props.replayId)
  return <section className="panel source-panel" aria-label="Market data source">
    <div className="source-heading"><span><Database size={16}/> Market data</span><span className={`pill ${configured ? 'green' : 'subtle'}`}>{configured ? 'Alpaca IEX configured' : 'API keys not configured'}</span><button className="icon-button" aria-label="Refresh market data configuration" onClick={() => void refresh()} disabled={!props.connected}><RefreshCw size={14}/></button></div>
    <div className="source-fields">
      <label>Data source<select value={props.source} disabled={props.disabled || downloading} onChange={e => props.setSource(e.target.value as DataSource)}><option value="generated">Generated demo prices</option><option value="live">Live stock trades · Alpaca IEX</option><option value="replay">Historical / offline replay</option></select></label>
      {props.source !== 'generated' && <label>Stock<select value={props.symbol} disabled={props.disabled || downloading} onChange={e => props.setSymbol(e.target.value)}>{['AAPL','NVDA','TSLA'].map(s => <option key={s}>{s}</option>)}</select></label>}
      {props.source === 'replay' && <label className="dataset-field">Replay dataset<select value={props.replayId} disabled={props.disabled || downloading} onChange={e => props.setReplayId(e.target.value)}>{datasets.map(d => <option key={d.id} value={d.id}>{d.symbol} · {d.source === 'synthetic_fixture' ? 'SYNTHETIC DEMO' : `Alpaca IEX ${d.timeframe}`} · {d.count} samples</option>)}</select></label>}
      <label>Paper fee (bps)<input type="number" aria-label="Paper trading fee basis points" min="0" max="100" step="0.1" value={props.feeBps} disabled={props.disabled} onChange={e => props.setFeeBps(Number(e.target.value))}/></label>
    </div>
    {props.source === 'live' && <p className="source-note">{configured ? 'Live IEX trade prints; coverage is one exchange. No new trades can mean the market is closed. No generated fallback.' : 'Add data-only Alpaca credentials to backend/.env and refresh. Keys never go to this browser.'} One stock per run; changing stocks starts a new portfolio and requires FPGA reset.</p>}
    {props.source === 'replay' && <><div className="download-controls"><label>From (UTC)<input type="date" value={start} disabled={downloading} onChange={e => setStart(e.target.value)}/></label><label>Through (UTC)<input type="date" value={end} disabled={downloading} onChange={e => setEnd(e.target.value)}/></label><label>Bars<select value={timeframe} onChange={e => setTimeframe(e.target.value)} disabled={downloading}><option>1Min</option><option>5Min</option><option>1Day</option></select></label><button className="button secondary" onClick={() => void download()} disabled={!configured || downloading || props.disabled}><Download size={14}/>{downloading ? 'Downloading…' : `Download ${props.symbol} history`}</button></div><p className="source-note">{selected?.source === 'synthetic_fixture' ? 'Selected DEMO is synthetic, not historical stock data.' : `Selected: ${selected?.symbol ?? 'none'} · ${selected?.start ?? ''} → ${selected?.end ?? ''}` } Replay uses bar close prices; volume is a requested-quantity proxy, capped for the wire protocol. Speed is samples per second.</p>{selected?.sha256 && <p className="dataset-hash">Dataset SHA256: {selected.sha256}</p>}</>}
    {props.source === 'generated' && <p className="source-note">Repeatable generated prices. USD demo marks = original integer ticks / 100. No stock API is used.</p>}
    {error && <p role="alert" className="source-error">{error}</p>}
  </section>
}
