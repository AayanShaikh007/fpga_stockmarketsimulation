"""Reproducible local backtests. Signals fill on the following sample, never the same close."""
from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from .market import MarketSample, Normalizer
from .paper import PaperPortfolio
from .replay import read_dataset
from .strategies import Strategy, StrategyEngine, digest


class BacktestRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    snapshot_id:str=Field(pattern='^[a-f0-9]{32}$')
    dataset_id:str=Field(min_length=1,max_length=64)
    phase:Literal['development','validation']='development'
    fee_bps:float=Field(default=1,ge=0,le=100)
    slippage_bps:float=Field(default=2,ge=0,le=100)


def backtest(store,request):
    frozen=store.snapshot(request.snapshot_id)
    dataset=read_dataset(request.dataset_id)
    rows=dataset['rows']
    if len(rows)<4: raise ValueError('Need at least four samples for a chronological development/validation split')
    split=max(2,min(len(rows)-2,math.floor(len(rows)*.7)))
    selected=rows[:split] if request.phase=='development' else rows[split:]
    spec=Strategy(**frozen['spec'])
    engine=StrategyEngine(spec)
    mapper=Normalizer()
    ledger=PaperPortfolio(fee_bps=request.fee_bps,position_limit=spec.position_limit)
    pending=0
    curve=[]
    trades=[]
    high=10000
    max_drawdown=0
    for sequence,row in enumerate(selected):
        sample=MarketSample(dataset['symbol'],Decimal(str(row['price'])),row['quantity'],row['timestamp'],dataset['source'])
        fill=None
        if pending:
            execution_price=sample.price*(1+Decimal(str(request.slippage_bps))/10000*(1 if pending>0 else -1))
            fill=ledger.apply(pending,execution_price)
            if fill['filled_order']:
                trades.append({'sequence':sequence,'timestamp':sample.timestamp,
                               'order':fill['filled_order'],'price_usd':float(execution_price)})
        marked=ledger.apply(0,sample.price)
        high=max(high,marked['equity'])
        max_drawdown=max(max_drawdown,(high-marked['equity'])/high*100)
        order,position,killed=engine.step(mapper.quote(sample,sequence))
        pending=order
        curve.append({'sequence':sequence,'timestamp':sample.timestamp,'price_usd':float(sample.price),
                      'equity':marked['equity'],'signal':order,'paper_position':marked['position'],
                      'engine_position':position})
    benchmark=PaperPortfolio(fee_bps=request.fee_bps)
    first=Decimal(str(selected[0]['price']))*(1+Decimal(str(request.slippage_bps))/10000)
    benchmark.apply(int(Decimal(10000)/first),first)
    hold=benchmark.apply(0,Decimal(str(selected[-1]['price'])))
    result={'id':uuid4().hex,'created_at':datetime.now(timezone.utc).isoformat(),
            'request':request.model_dump(),'strategy_snapshot':frozen,
            'dataset':{'id':request.dataset_id,'sha256':dataset['sha256'],'symbol':dataset['symbol'],
                       'source':dataset['source'],'start':selected[0]['timestamp'],'end':selected[-1]['timestamp'],
                       'split_index':split,'full_count':len(rows),'selected_count':len(selected)},
            'fill_model':'signal on sample N, fill on sample N+1 with configured slippage; no fill for final pending signal',
            'summary':{'final_equity':marked['equity'],'total_pnl':marked['total_pnl'],
                       'realized_pnl':marked['realized_pnl'],'unrealized_pnl':marked['unrealized_pnl'],
                       'fees':marked['fees'],'fill_count':len(trades),'max_drawdown_pct':max_drawdown,
                       'buy_hold_equity':hold['equity'],'unfilled_final_signal':pending},
            'curve':curve,'trades':trades}
    result['result_sha256']=digest(result)
    store.atomic(store.path(result['id'],'experiments'),result)
    return result


def experiments(store):
    import json
    result=[]
    for path in sorted((store.root/'experiments').glob('*.json')):
        value=json.loads(path.read_text(encoding='utf-8'))
        result.append({key:value[key] for key in ('id','created_at','request','summary','dataset')})
    return result
