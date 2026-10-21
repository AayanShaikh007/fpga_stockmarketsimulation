"""Bounded, timestamp-ordered replay datasets with provenance and content hashes."""
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, model_validator
from typing import Literal

from .market import MarketSample
from .provider import download_bars

DATA_DIR = Path(__file__).parent / 'data'
FIXTURE = Path(__file__).parent / 'fixtures' / 'demo.json'


class DownloadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    symbol: Literal['AAPL','NVDA','TSLA']
    start: datetime
    end: datetime
    timeframe: Literal['1Min','5Min','1Day'] = '1Min'

    @model_validator(mode='after')
    def valid_range(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError('Dates must include a timezone')
        if not 0 < (self.end-self.start).total_seconds() <= 366*86400:
            raise ValueError('Choose an ordered range of at most 366 days')
        if self.end > datetime.now(timezone.utc):
            raise ValueError('Replay end date cannot be in the future')
        return self


def dataset_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def read_dataset(dataset_id):
    if dataset_id == 'demo':
        path = FIXTURE
    elif re.fullmatch(r'[a-f0-9]{32}', dataset_id):
        path = DATA_DIR / f'{dataset_id}.json'
    else:
        raise ValueError('Invalid replay ID')
    if not path.is_file():
        raise ValueError('Replay not found; download or select an existing dataset')
    dataset = json.loads(path.read_text(encoding='utf-8'))
    rows = dataset['rows']
    if not 1 <= len(rows) <= 20000:
        raise ValueError('Invalid replay size')
    if dataset_id != 'demo' and not dataset.get('sha256'):
        raise ValueError('Replay checksum missing')
    if dataset.get('sha256') and dataset_hash(rows) != dataset['sha256']:
        raise ValueError('Replay checksum mismatch')
    dataset.setdefault('sha256', dataset_hash(rows))
    last = None
    for row in rows:
        sample = MarketSample(dataset['symbol'], Decimal(str(row['price'])), row['quantity'],
                              row['timestamp'], dataset['source'])
        stamp = datetime.fromisoformat(sample.timestamp.replace('Z','+00:00'))
        if last is not None and stamp <= last:
            raise ValueError('Replay timestamps must be strictly increasing')
        last = stamp
    return dataset


def metadata(dataset):
    return {key: dataset.get(key) for key in ('id','symbol','source','timeframe','sha256','created_at')} | {
        'count':len(dataset['rows']), 'start':dataset['rows'][0]['timestamp'],
        'end':dataset['rows'][-1]['timestamp']}


def list_datasets():
    result = [metadata(read_dataset('demo'))]
    for path in sorted(DATA_DIR.glob('*.json')):
        try:
            result.append(metadata(read_dataset(path.stem)))
        except (ValueError, KeyError, TypeError):
            continue
    return result


async def download_dataset(request):
    bars = await download_bars(request.symbol, request.start, request.end, request.timeframe)
    rows = [{'timestamp':b['t'],'price':str(b['c']),'quantity':int(b['v'])} for b in bars]
    # Validate prices, volumes, ordering, and timestamps before persisting.
    last = None
    for row in rows:
        sample = MarketSample(request.symbol, Decimal(row['price']), row['quantity'], row['timestamp'], 'alpaca_iex_history')
        stamp = datetime.fromisoformat(sample.timestamp.replace('Z','+00:00'))
        if last is not None and stamp <= last:
            raise ValueError('Provider bars are duplicated or out of order')
        last = stamp
    dataset_id = uuid4().hex
    dataset = {'id':dataset_id,'symbol':request.symbol,'source':'alpaca_iex_history',
               'timeframe':request.timeframe,'sha256':dataset_hash(rows),'rows':rows,
               'created_at':datetime.now(timezone.utc).isoformat()}
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / f'{dataset_id}.json').write_text(json.dumps(dataset, indent=2),encoding='utf-8')
    return metadata(dataset)


async def replay_samples(dataset):
    for row in dataset['rows']:
        yield MarketSample(dataset['symbol'], Decimal(str(row['price'])), row['quantity'],
                           row['timestamp'], dataset['source'])
