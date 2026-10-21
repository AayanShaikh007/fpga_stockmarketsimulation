from decimal import Decimal
import pytest
from backend.market import MarketSample, Normalizer, alpaca_trade


def sample(price, quantity=100):
    return MarketSample('AAPL', Decimal(str(price)), quantity, '2026-10-20T14:00:00Z', 'test')


def test_fixed_anchor_basis_point_mapping():
    mapper = Normalizer()
    assert mapper.quote(sample(200), 0).price == 10000
    assert mapper.quote(sample('199.90'), 1).price == 9995
    assert mapper.quote(sample('200.10'), 2).price == 10005
    assert mapper.anchor == 200
    assert mapper.quote(sample(200, 100000), 3).quantity == 65535


def test_provider_trade_mapping():
    record = {'T':'t','S':'NVDA','p':123.45,'s':10,'i':42,'t':'2026-10-20T14:00:00Z'}
    value = alpaca_trade(record, 'NVDA')
    assert value.price == Decimal('123.45') and value.event_id == '42'
    with pytest.raises(ValueError):
        alpaca_trade(record, 'AAPL')


@pytest.mark.parametrize('price', ['NaN','Infinity','-1','0'])
def test_invalid_market_price(price):
    with pytest.raises(ValueError):
        sample(price)
