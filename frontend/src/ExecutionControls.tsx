import { useState } from 'react'
import type { BrokerAccount, Execution } from './types'
export default function ExecutionControls({execution,setExecution,confirmed,setConfirmed,symbol,disabled}: {
  execution:Execution;setExecution:(value:Execution)=>void;confirmed:boolean;setConfirmed:(value:boolean)=>void;symbol:string;disabled:boolean
}) {
  const [account,setAccount]=useState<BrokerAccount | null>(null)
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(false)
  async function refresh() {
    setLoading(true);setError('')
    try {
      const response=await fetch(`/api/paper-account?symbol=${encodeURIComponent(symbol)}`)
      const data=await response.json()
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Paper account lookup failed')
      setAccount(data)
    } catch(e){setError(e instanceof Error?e.message:'Paper account unavailable')}
    finally{setLoading(false)}
  }
  return <section className="panel source-panel"><div className="source-fields"><label>Portfolio / order destination<select value={execution} disabled={disabled} onChange={e=>{setExecution(e.target.value as Execution);setConfirmed(false)}}><option value="local">Local $10,000 simulator</option><option value="alpaca_paper">Alpaca PAPER account · virtual funds</option></select></label>{execution==='alpaca_paper'&&<><button className="button secondary" onClick={()=>void refresh()} disabled={loading}>{loading?'Reading account…':'Read paper balance'}</button><label className="reset-check"><input type="checkbox" checked={confirmed} disabled={disabled} onChange={e=>setConfirmed(e.target.checked)}/> I authorize simulated orders in my Alpaca PAPER account</label></>}</div>{execution==='alpaca_paper'?<><p className="source-note">Uses live data only. Account cash and holdings persist between runs; no $100,000 reset. Orders appear on Alpaca’s paper website. Regular US session only, up to 20 shares/order and 100 held shares. Local fee settings do not apply. Processing is capped at one sample per 5 seconds plus fill reconciliation.</p><p className="source-note">Stop/kill cancels this run’s pending order when possible; it does not liquidate holdings or cancel unrelated orders. An unresolved submission stops the run and requires checking Alpaca before restarting. Real-money execution is unavailable.</p>{account&&<p className="source-note">Account equity: ${account.equity.toFixed(2)} · Cash: ${account.cash.toFixed(2)} · {account.symbol}: {account.position} shares · read {new Date(account.timestamp).toLocaleTimeString()}</p>}{error&&<p className="source-error" role="alert">{error}</p>}</>:<p className="source-note">Fresh local virtual cash each run. Generated, replay, or live data. No broker orders are submitted.</p>}</section>
}
