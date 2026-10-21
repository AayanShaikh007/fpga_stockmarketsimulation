"""Validated market samples and fixed-anchor conversion for the unchanged FPGA."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from nanoquant.model import Quote

SYMBOLS = ('AAPL', 'NVDA', 'TSLA')


@dataclass(frozen=True)
class MarketSample:
    symbol: str
    price: Decimal
    quantity: int
    timestamp: str
    source: str
    event_id: str = ''

    def __post_init__(self):
        if not self.price.is_finite() or self.price <= 0:
            raise ValueError('Invalid market price')
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) or self.quantity < 0:
            raise ValueError('Invalid market quantity')
        stamp = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Market timestamp must include timezone')


class Normalizer:
    def __init__(self):
        self.anchor = None

    def quote(self, sample, sequence, kill=False):
        if self.anchor is None:
            self.anchor = sample.price
        ticks = int((sample.price/self.anchor*10000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        if not 0 <= ticks <= 0xffffffff:
            raise ValueError('Normalized price exceeds FPGA packet range')
        return Quote(sequence, ticks, min(sample.quantity, 65535), kill)


def alpaca_trade(record, symbol):
    if record.get('T') != 't' or record.get('S') != symbol:
        raise ValueError('Unexpected trade symbol or event type')
    return MarketSample(symbol, Decimal(str(record['p'])), record['s'], record['t'],
                        'alpaca_iex_live', str(record['i']))


def is_stale(sample, seconds=60):
    stamp = datetime.fromisoformat(sample.timestamp.replace('Z', '+00:00'))
    age = (datetime.now(timezone.utc)-stamp).total_seconds()
    return age > seconds or age < -5
