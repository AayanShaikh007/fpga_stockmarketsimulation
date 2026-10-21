import asyncio
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .strategies import Strategy, StrategyStore, Conflict
from .research import BacktestRequest, backtest, experiments


class SaveRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    spec:Strategy
    expected_revision:int=Field(default=0,ge=0)


class RevisionRequest(BaseModel):
    expected_revision:int=Field(ge=1)


def research_router(store=None):
    store=store or StrategyStore()
    router=APIRouter(prefix='/api/research')
    test_lock=asyncio.Lock()

    async def work(function,*args):
        try: return await asyncio.to_thread(function,*args)
        except Conflict as exc: raise HTTPException(409,str(exc)) from exc
        except (ValueError,KeyError,OSError) as exc: raise HTTPException(400,str(exc)) from exc

    @router.get('/strategies')
    async def listing(): return await work(store.listing)

    @router.post('/strategies')
    async def create(body:SaveRequest): return await work(store.save,None,body.spec,0)

    @router.get('/strategies/{identifier}')
    async def get(identifier:str): return await work(store.get,identifier)

    @router.post('/strategies/{identifier}')
    async def save(identifier:str,body:SaveRequest): return await work(store.save,identifier,body.spec,body.expected_revision)

    @router.get('/strategies/{identifier}/backups')
    async def backups(identifier:str): return await work(store.backups,identifier)

    @router.post('/strategies/{identifier}/restore/{revision}')
    async def restore(identifier:str,revision:int,body:RevisionRequest): return await work(store.restore,identifier,revision,body.expected_revision)

    @router.post('/strategies/{identifier}/freeze')
    async def freeze(identifier:str,body:RevisionRequest): return await work(store.freeze,identifier,body.expected_revision)

    @router.get('/experiments')
    async def history(): return await work(experiments,store)

    @router.get('/experiments/{identifier}')
    async def experiment(identifier:str):
        return await work(lambda:json.loads(store.path(identifier,'experiments').read_text(encoding='utf-8')))

    @router.post('/backtests')
    async def test(body:BacktestRequest):
        if test_lock.locked(): raise HTTPException(409,'A backtest is already running')
        async with test_lock:
            return await work(backtest,store,body)

    return router
