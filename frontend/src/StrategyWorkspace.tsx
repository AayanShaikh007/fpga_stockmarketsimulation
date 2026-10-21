import { useEffect, useRef, useState } from 'react'
import type { Replay } from './types'
interface Spec { schema_version:1; name:string; hypothesis:string; kind:'anchor'|'sma_reversion';threshold_ticks:number;window:number;max_order:number;position_limit:number }
interface Saved { id:string; revision:number; spec:Spec; fpga_supported:boolean }
interface Frozen extends Saved { sha256:string }
interface Result { id:string;created_at:string;request:{phase:string};summary:{final_equity:number;total_pnl:number;fees:number;fill_count:number;max_drawdown_pct:number;buy_hold_equity:number;unfilled_final_signal:number};dataset:{symbol:string;source:string;start:string;end:string;sha256:string;selected_count:number};curve?:{equity:number;sequence:number}[] }
const EMPTY:Spec={schema_version:1,name:'My strategy',hypothesis:'',kind:'anchor',threshold_ticks:5,window:20,max_order:20,position_limit:100}
const DRAFT='nanoquant.strategy.recovery.v1'
async function api(path:string,body?:unknown) {
  const response=await fetch(`/api/research/${path}`,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  const value=await response.json()
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:`Request failed (${response.status}); check fields and backend`)
  return value
}
export default function StrategyWorkspace({onUse,activeSnapshot,running}:{onUse:(id:string|null,name:string,supported:boolean)=>void;activeSnapshot:string|null;running:boolean}) {
  const [library,setLibrary]=useState<Saved[]>([])
  const [record,setRecord]=useState<Saved|null>(null)
  const [spec,setSpec]=useState<Spec>({...EMPTY})
  const [dirty,setDirty]=useState(false)
  const [saving,setSaving]=useState(false)
  const [blocked,setBlocked]=useState(false)
  const [message,setMessage]=useState('Create a strategy or open a saved file.')
  const [error,setError]=useState('')
  const [snapshot,setSnapshot]=useState<Frozen|null>(null)
  const [datasets,setDatasets]=useState<Replay[]>([])
  const [dataset,setDataset]=useState('demo')
  const [phase,setPhase]=useState('development')
  const [fees,setFees]=useState(1)
  const [slippage,setSlippage]=useState(2)
  const [busy,setBusy]=useState(false)
  const [history,setHistory]=useState<Result[]>([])
  const [result,setResult]=useState<Result|null>(null)
  const [backups,setBackups]=useState<Saved[]>([])
  const [recovery,setRecovery]=useState<{record:Saved|null;spec:Spec}|null>(null)
  const lock=useRef(false)
  const epoch=useRef(0)
  async function load() {
    try {
      const [files,tests,replays]=await Promise.all([api('strategies'),api('experiments'),fetch('/api/replays').then(r=>r.json())])
      setLibrary(files);setHistory(tests);setDatasets(replays);setError('')
    }catch(e){setError(e instanceof Error?e.message:'Research service unavailable')}
  }
  useEffect(()=>{void load();try{const value=localStorage.getItem(DRAFT);if(value)setRecovery(JSON.parse(value))}catch{/* Server files still work without browser storage. */}},[])
  function edit(change:Partial<Spec>) {epoch.current++;setSpec(old=>({...old,...change}));setDirty(true);setSnapshot(null);setBlocked(false);setMessage('Unsaved changes')}
  async function save(copy=false) {
    if(lock.current)return
    lock.current=true;setSaving(true);setError('')
    const version=epoch.current
    try {
      const saved:Saved=await api(copy||!record?'strategies':`strategies/${record.id}`,{spec,expected_revision:copy?0:record?.revision??0})
      setRecord(saved);setLibrary(old=>[saved,...old.filter(item=>item.id!==saved.id)])
      if(version===epoch.current){setDirty(false);setMessage(`Saved revision ${saved.revision}`);setRecovery(null);try{localStorage.removeItem(DRAFT)}catch{}}
      else setMessage('Saving newer edits next…')
      setBlocked(false)
    }catch(e){setError(e instanceof Error?e.message:'Save failed');setMessage('Save failed · recovery draft retained');setBlocked(true)}
    finally{lock.current=false;setSaving(false)}
  }
  useEffect(()=>{
    if(!dirty)return
    try{localStorage.setItem(DRAFT,JSON.stringify({record,spec}))}catch{setMessage('Browser recovery unavailable; save to disk to protect edits')}
    if(blocked)return
    const timer=setTimeout(()=>void save(),800)
    return()=>clearTimeout(timer)
  },[spec,dirty,record?.revision,blocked])
  useEffect(()=>{
    function warn(event:BeforeUnloadEvent){if(dirty){event.preventDefault();event.returnValue=''}}
    window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)
  },[dirty])
  function open(file:Saved|null) {
    if(dirty)setRecovery({record,spec})
    epoch.current++;setRecord(file);setSpec(file?{...file.spec}:{...EMPTY});setDirty(!file);setSnapshot(null);setBlocked(false);setBackups([]);setError('');setMessage(file?`Opened revision ${file.revision}`:'New file · autosave pending')
  }
  async function freeze() {
    if(!record||dirty||saving)return
    setBusy(true);setError('')
    try{setSnapshot(await api(`strategies/${record.id}/freeze`,{expected_revision:record.revision}));setMessage('Frozen snapshot saved. Future edits cannot change it.')}
    catch(e){setError(String(e))}finally{setBusy(false)}
  }
  async function test() {
    if(!snapshot)return
    setBusy(true);setError('')
    try{const value:Result=await api('backtests',{snapshot_id:snapshot.id,dataset_id:dataset,phase,fee_bps:fees,slippage_bps:slippage});setResult(value);setHistory(old=>[value,...old])}
    catch(e){setError(String(e))}finally{setBusy(false)}
  }
  function exportSpec() {
    const url=URL.createObjectURL(new Blob([JSON.stringify(spec,null,2)],{type:'application/json'}))
    const a=document.createElement('a');a.href=url;a.download=`${spec.name.replace(/[^a-z0-9_-]/gi,'_')}.strategy.json`;a.click();URL.revokeObjectURL(url)
  }
  async function importSpec(file?:File) {
    if(!file)return
    if(file.size>65536){setError('Strategy import exceeds 64 KB');return}
    setBusy(true)
    try{const value=JSON.parse(await file.text());const saved:Saved=await api('strategies',{spec:value.spec??value});setLibrary(old=>[saved,...old]);open(saved)}catch(e){setError(String(e))}finally{setBusy(false)}
  }
  async function restore(item:Saved) {
    if(!record)return
    setBusy(true)
    try{const saved:Saved=await api(`strategies/${record.id}/restore/${item.revision}`,{expected_revision:record.revision});open(saved);await load()}catch(e){setError(String(e))}finally{setBusy(false)}
  }
  const dollars=(value:number)=>value.toLocaleString('en-US',{style:'currency',currency:'USD'})
  const curve=result?.curve??[]
  const min=Math.min(10000,...curve.map(p=>p.equity)),max=Math.max(10000,...curve.map(p=>p.equity))
  const path=curve.map((p,i)=>`${i===0?'M':'L'}${curve.length>1?i/(curve.length-1)*600:0},${90-(p.equity-min)/(max-min||1)*75}`).join(' ')
  return <section className="panel strategy-workspace" id="strategies">
    <div className="panel-heading"><div><h2>Strategy research workspace</h2><p>Hypothesis → saved rules → frozen tests → live paper runs</p></div><button className="button secondary" onClick={()=>void load()}>Refresh library</button></div>
    <div className="strategy-layout"><aside><div className="strategy-tools"><button className="button secondary" disabled={saving||busy} onClick={()=>open(null)}>New strategy</button><label className="button secondary">Import JSON<input aria-label="Import strategy JSON" type="file" accept=".json" hidden disabled={saving||busy} onChange={e=>void importSpec(e.target.files?.[0])}/></label></div>{library.map(file=><button key={file.id} className={`strategy-file ${record?.id===file.id?'selected':''}`} disabled={saving||busy} onClick={()=>open(file)}><strong>{file.spec.name}</strong><small>r{file.revision} · {file.fpga_supported?'FPGA compatible':'Python only'}</small></button>)}{!library.length&&<p className="source-note">Your saved strategy files will appear here.</p>}</aside>
    <div className="strategy-editor">{recovery&&<div className="notice warning">An unsaved recovery draft is available.<button className="button secondary" disabled={saving||busy} onClick={()=>{epoch.current++;setRecord(recovery.record);setSpec(recovery.spec);setDirty(true);setBlocked(true);setSnapshot(null);setMessage('Recovery loaded. Save a copy if the server revision changed.')}}>Recover draft</button></div>}
    <fieldset disabled={busy} className="strategy-fields"><label>Name<input maxLength={100} value={spec.name} onChange={e=>edit({name:e.target.value})}/></label><label>Hypothesis: why should this rule work?<textarea rows={3} maxLength={5000} value={spec.hypothesis} onChange={e=>edit({hypothesis:e.target.value})} placeholder="Describe the idea before testing it…"/></label><div className="source-fields"><label>Rule template<select value={spec.kind} onChange={e=>edit({kind:e.target.value as Spec['kind']})}><option value="anchor">Fixed-anchor reversion</option><option value="sma_reversion">Moving-average reversion (Python)</option></select></label><label>Threshold (normalized ticks)<input type="number" min={1} max={500} value={spec.threshold_ticks} onChange={e=>edit({threshold_ticks:Number(e.target.value)})}/></label>{spec.kind==='sma_reversion'&&<label>Prior-sample average window<input type="number" min={2} max={500} value={spec.window} onChange={e=>edit({window:Number(e.target.value)})}/></label>}<label>Max order<input type="number" min={1} max={20} value={spec.max_order} onChange={e=>edit({max_order:Number(e.target.value)})}/></label><label>Position limit<input type="number" min={1} max={100} value={spec.position_limit} onChange={e=>edit({position_limit:Number(e.target.value)})}/></label></div></fieldset>
    <div className="strategy-tools"><span role="status" className="source-note">{saving?'Saving to disk…':message}</span><button className="button secondary" disabled={saving||busy} onClick={()=>void save()}>Save now</button><button className="button secondary" disabled={saving||busy} onClick={()=>void save(true)}>Save a copy</button><button className="button secondary" onClick={exportSpec}>Export .strategy.json</button><button className="button primary" disabled={!record||dirty||saving||busy} onClick={()=>void freeze()}>Freeze version</button></div>
    {record&&<div className="strategy-tools"><button className="guide-skip" disabled={busy||saving||dirty} onClick={()=>void api(`strategies/${record.id}/backups`).then(setBackups).catch(e=>setError(String(e)))}>Show saved revision backups</button>{backups.map(item=><button key={item.revision} className="pill subtle" disabled={busy||saving||dirty} onClick={()=>void restore(item)}>Restore r{item.revision}</button>)}</div>}
    {snapshot&&<div className="notice"><span>Frozen: {snapshot.spec.name} · r{snapshot.revision}<small className="dataset-hash">{snapshot.sha256}</small></span><button className="button secondary" disabled={running} onClick={()=>onUse(snapshot.id,snapshot.spec.name,snapshot.fpga_supported)}>Use for next paper run</button></div>}
    <div className="source-fields test-controls"><label>Dataset<select value={dataset} onChange={e=>setDataset(e.target.value)}>{datasets.map(item=><option key={item.id} value={item.id}>{item.symbol} · {item.source} · {item.count} samples</option>)}</select></label><label>Chronological phase<select value={phase} onChange={e=>setPhase(e.target.value)}><option value="development">Development · first 70%</option><option value="validation">Validation · final 30%</option></select></label><label>Fees (bps)<input type="number" min={0} max={100} value={fees} onChange={e=>setFees(Number(e.target.value))}/></label><label>Slippage (bps)<input type="number" min={0} max={100} value={slippage} onChange={e=>setSlippage(Number(e.target.value))}/></label><button className="button primary" disabled={!snapshot||busy||dirty||saving} onClick={()=>void test()}>{busy?'Working…':'Run frozen backtest'}</button></div>
    <p className="source-note">Local-only backtests: $10,000, next-sample fills, fees and slippage. Validation is a separate later period, not a guarantee against overfitting. Repeatedly tuning against it makes it no longer unseen. Small datasets or long warmup windows may yield no trades.</p>
    {error&&<div className="notice error" role="alert">{error}</div>}
    {result&&<div className="research-result"><h3>{result.request.phase.toUpperCase()} · {result.dataset.symbol} · {result.dataset.selected_count} samples</h3><div className="paper-summary"><div><span>Ending equity</span><strong>{dollars(result.summary.final_equity)}</strong><small>P&amp;L {dollars(result.summary.total_pnl)} · {result.summary.fill_count} fills</small></div><div><span>Buy &amp; hold benchmark</span><strong>{dollars(result.summary.buy_hold_equity)}</strong><small>Max drawdown {result.summary.max_drawdown_pct.toFixed(2)}% · fees {dollars(result.summary.fees)}</small></div></div>{curve.length>0&&<svg className="equity-spark" viewBox="0 0 600 100" role="img" aria-label="Backtest equity across selected samples"><path d={path} fill="none" stroke="#64d9a0" strokeWidth={2}/></svg>}<p className="dataset-hash">Dataset {result.dataset.sha256}</p><p className="source-note">{result.dataset.start} → {result.dataset.end}. Final pending signal is not filled without a following sample.</p></div>}
    <div className="experiment-list"><h3>Saved experiments</h3>{history.slice().reverse().map(item=><button key={item.id} className="strategy-file" onClick={()=>void api(`experiments/${item.id}`).then(setResult).catch(e=>setError(String(e)))}>{item.dataset.symbol} · {item.request.phase} · {dollars(item.summary.final_equity)}<small>{new Date(item.created_at).toLocaleString()} · {item.id.slice(0,8)}</small></button>)}</div>
    <div className="strategy-tools"><span className="source-note">{activeSnapshot?'A frozen strategy is selected for the next run.':'Next run uses the original built-in rule.'}</span><button className="button secondary" disabled={running} onClick={()=>onUse(null,'Original fixed-anchor strategy',true)}>Use original strategy</button></div>
    </div></div>
  </section>
}
