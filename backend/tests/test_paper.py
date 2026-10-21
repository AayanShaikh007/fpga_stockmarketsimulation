from decimal import Decimal
import pytest
from backend.paper import PaperPortfolio


def test_round_trip_profit_and_fees():
    portfolio = PaperPortfolio(fee_bps=10)
    buy = portfolio.apply(10, '100')
    assert buy['cash'] == 8999
    sell = portfolio.apply(-10, '110')
    assert sell['position'] == 0
    assert sell['fees'] == 2.1
    assert sell['realized_pnl'] == 97.9
    assert sell['total_pnl'] == 97.9


def test_average_cost_partial_sell_and_mark():
    portfolio = PaperPortfolio(fee_bps=0)
    portfolio.apply(10, 100)
    portfolio.apply(10, 120)
    result = portfolio.apply(-5, 130)
    assert result['average_cost'] == 110
    assert result['realized_pnl'] == 100
    assert result['unrealized_pnl'] == 300
    assert result['total_pnl'] == 400


def test_no_shorting_or_negative_cash():
    portfolio = PaperPortfolio(fee_bps=1)
    assert portfolio.apply(-20, 100)['filled_order'] == 0
    result = portfolio.apply(20, 1000)
    assert result['filled_order'] == 9
    assert result['unfilled_units'] == 11
    assert result['cash'] >= 0


def test_ledger_identity_across_many_fills():
    portfolio = PaperPortfolio(fee_bps=7)
    for order, price in [(20, '125.13'), (20, '128.17'), (-11, '129.08'), (0, '120.57'), (-100, '115.71')]:
        result = portfolio.apply(order, price)
        assert abs(result['realized_pnl']+result['unrealized_pnl']-result['total_pnl']) <= .011
        assert result['cash'] >= 0 and result['position'] >= 0


@pytest.mark.parametrize('price', ['NaN', 'Infinity', 0, -2])
def test_invalid_mark_prices(price):
    with pytest.raises(ValueError):
        PaperPortfolio().apply(1, price)
