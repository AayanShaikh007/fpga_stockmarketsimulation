"""Long-only cash paper ledger, entirely local. No broker/order endpoints."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal('.01')


def money(value):
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


class PaperPortfolio:
    def __init__(self, starting_cash='10000', fee_bps=1, position_limit=None):
        self.position_limit=position_limit
        self.initial = Decimal(str(starting_cash))
        self.cash = self.initial
        self.fee_rate = Decimal(str(fee_bps)) / 10000
        if not self.initial.is_finite() or self.initial <= 0 or not self.fee_rate.is_finite() or not 0 <= self.fee_rate <= Decimal('.01'):
            raise ValueError('Invalid starting cash or fee basis points')
        self.position = 0
        self.average_cost = Decimal(0)
        self.realized = Decimal(0)
        self.fees = Decimal(0)
        self.fills = 0

    def apply(self, order, price):
        price = Decimal(str(price))
        if not price.is_finite() or price <= 0:
            raise ValueError('Paper fill price must be positive and finite')
        quantity = abs(order)
        if order > 0:
            quantity = min(quantity, int(self.cash / (price * (1+self.fee_rate))))
            if self.position_limit is not None:
                quantity=min(quantity,max(0,self.position_limit-self.position))
        elif order < 0:
            quantity = min(quantity, self.position)
        fee = (price * quantity * self.fee_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        gross = (price * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
        # Rounding at cent precision must not permit a negative cash balance.
        while order > 0 and quantity > 0 and gross + fee > self.cash:
            quantity -= 1
            gross = (price * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
            fee = (gross*self.fee_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        filled = quantity if order > 0 else -quantity if order < 0 else 0
        if filled > 0:
            self.average_cost = (self.average_cost*self.position + gross)/(self.position+quantity)
            self.position += quantity
            self.cash -= gross + fee
        elif filled < 0:
            self.realized += gross - self.average_cost*quantity
            self.position -= quantity
            self.cash += gross - fee
            if not self.position:
                self.average_cost = Decimal(0)
        self.realized -= fee
        self.fees += fee
        self.fills += int(filled != 0)
        market_value = price*self.position
        equity = self.cash + market_value
        return {
            'starting_cash': money(self.initial), 'cash': money(self.cash),
            'position': self.position, 'average_cost': money(self.average_cost),
            'market_value': money(market_value), 'equity': money(equity),
            'realized_pnl': money(self.realized),
            'unrealized_pnl': money((price-self.average_cost)*self.position),
            'total_pnl': money(equity-self.initial), 'fees': money(self.fees),
            'filled_order': filled, 'unfilled_units': abs(order)-quantity,
            'fill_count': self.fills, 'policy': 'long-only cash; mark-price fills; no slippage',
        }
