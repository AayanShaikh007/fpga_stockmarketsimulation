import asyncio
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nanoquant.model import Quote
from backend.strategies import BUILTIN, Conflict, Strategy, StrategyEngine, StrategyStore, fpga_supported
from backend.research import BacktestRequest, backtest
from backend.research_api import research_router
from backend.service import Controller, StartConfig


def test_revision_conflicts_backups_restore_and_frozen_copy(tmp_path):
    store=StrategyStore(tmp_path)
    first=store.save(None,Strategy(hypothesis='A testable idea'),0)
    frozen=store.freeze(first['id'],1)
    second=store.save(first['id'],Strategy(threshold_ticks=10),1)
    assert second['revision']==2
    with pytest.raises(Conflict): store.save(first['id'],Strategy(),1)
    assert store.snapshot(frozen['id'])['spec']['threshold_ticks']==5
    restored=store.restore(first['id'],1,2)
    assert restored['revision']==3 and restored['spec']['hypothesis']=='A testable idea'
    assert len(store.backups(first['id']))==2


def test_atomic_write_failure_preserves_previous_file(tmp_path):
    store=StrategyStore(tmp_path)
    first=store.save(None,Strategy(name='Safe version'),0)
    with patch('backend.strategies.os.replace',side_effect=OSError('disk failure')):
        with pytest.raises(OSError):store.save(first['id'],Strategy(name='Unfinished'),1)
    assert store.get(first['id'])['spec']['name']=='Safe version'
    assert not list(tmp_path.rglob('*.tmp'))


def test_paths_json_validation_and_snapshot_tampering(tmp_path):
    store=StrategyStore(tmp_path)
    with pytest.raises(ValueError): store.get('../.env')
    with pytest.raises(ValueError): Strategy(kind='execute_python',code='bad')
    first=store.save(None,Strategy(),0)
    frozen=store.freeze(first['id'],1)
    path=store.path(frozen['id'],'snapshots')
    path.write_text(path.read_text().replace('"threshold_ticks": 5','"threshold_ticks": 6'))
    with pytest.raises(ValueError,match='checksum'):store.snapshot(frozen['id'])


def test_strategy_rules_use_prior_window_and_latch_kill():
    engine=StrategyEngine(Strategy(kind='sma_reversion',window=2,threshold_ticks=5,max_order=3,position_limit=4))
    assert engine.step(Quote(0,10000,20))==(0,0,0)
    assert engine.step(Quote(1,10000,20))==(0,0,0)
    assert engine.step(Quote(2,9990,20))==(3,3,0)
    assert engine.step(Quote(3,9980,20))==(1,4,0)
    assert engine.step(Quote(4,9980,20,True))==(0,4,1)
    assert engine.step(Quote(5,10100,20))==(0,4,1)
    assert fpga_supported(BUILTIN)
    assert not fpga_supported(Strategy(threshold_ticks=6))
    assert not fpga_supported(Strategy(kind='sma_reversion'))


def test_reproducible_backtest_and_disjoint_validation_period(tmp_path):
    store=StrategyStore(tmp_path)
    file=store.save(None,Strategy(max_order=5,position_limit=10),0)
    frozen=store.freeze(file['id'],1)
    request=BacktestRequest(snapshot_id=frozen['id'],dataset_id='demo')
    first=backtest(store,request)
    second=backtest(store,request)
    assert first['curve']==second['curve']
    assert first['summary']==second['summary']
    assert first['dataset']['source']=='synthetic_fixture'
    assert first['trades'][0]['sequence']==2 # first low signal at 1 fills at 2
    assert all(row['paper_position']<=10 for row in first['curve'])
    later=backtest(store,request.model_copy(update={'phase':'validation'}))
    assert later['dataset']['start']>first['dataset']['end']
    assert later['strategy_snapshot']['sha256']==first['strategy_snapshot']['sha256']
    assert len(list((tmp_path/'experiments').glob('*.json')))==3


def test_research_api_roundtrip_and_conflict(tmp_path):
    app=FastAPI();app.include_router(research_router(StrategyStore(tmp_path)))
    with TestClient(app) as client:
        file=client.post('/api/research/strategies',json={'spec':Strategy().model_dump()}).json()
        assert len(client.get('/api/research/strategies').json())==1
        assert client.post(f"/api/research/strategies/{file['id']}",json={'spec':Strategy().model_dump(),'expected_revision':0}).status_code==409
        frozen=client.post(f"/api/research/strategies/{file['id']}/freeze",json={'expected_revision':1}).json()
        response=client.post('/api/research/backtests',json={'snapshot_id':frozen['id'],'dataset_id':'demo'})
        assert response.status_code==200
        assert len(client.get('/api/research/experiments').json())==1
        assert client.get('/api/research/experiments/'+response.json()['id']).status_code==200


def test_custom_fpga_rule_rejected_before_serial_open(tmp_path):
    store=StrategyStore(tmp_path)
    file=store.save(None,Strategy(kind='sma_reversion'),0)
    frozen=store.freeze(file['id'],1)
    async def scenario():
        with patch('backend.service.StrategyStore',return_value=store):
            controller=Controller()
            with pytest.raises(ValueError,match='Python-only'):
                await controller.start('owner',StartConfig(mode='fpga',port='fake',reset_confirmed=True,strategy_snapshot_id=frozen['id']))
            assert controller.task is None
    asyncio.run(scenario())
