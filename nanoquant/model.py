from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    sequence: int
    price: int
    quantity: int
    kill: bool = False

    def __post_init__(self):
        for name, bits in (("sequence", 32), ("price", 32), ("quantity", 16)):
            value = getattr(self, name)
            if not isinstance(value, int) or not 0 <= value < (1 << bits):
                raise ValueError(name)
        if not isinstance(self.kill, bool):
            raise ValueError("kill")


class Engine:
    """Immediate simulated fills; kill latches until reset. No real orders."""
    def __init__(self, fair=10000, threshold=5, max_order=20, limit=100):
        if not (0 <= fair <= 0xffffffff and 0 <= threshold <= 0xffffffff
                and 1 <= max_order <= 65535 and 1 <= limit <= 0x7fffffff):
            raise ValueError("invalid configuration")
        self.fair, self.threshold = fair, threshold
        self.max_order, self.limit = max_order, limit
        self.reset()

    def reset(self):
        self.position = 0
        self.killed = False

    def step(self, quote):
        self.killed |= quote.kill
        order = 0
        if not self.killed:
            delta = self.fair - quote.price
            direction = 1 if delta >= self.threshold else (-1 if delta <= -self.threshold else 0)
            # Buy wins if threshold=0 and price equals fair, also in RTL.
            room = self.limit - self.position if direction == 1 else self.limit + self.position
            order = direction * min(quote.quantity, self.max_order, room)
        self.position += order
        return order, self.position, int(self.killed)
