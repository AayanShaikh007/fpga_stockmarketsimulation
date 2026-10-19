"""Portable deterministic LCG, independent of Python's random implementation."""
from .model import Quote


def generate(count=100, seed=1):
    if count < 0 or count > 2**32 or not 0 <= seed <= 0xffffffff:
        raise ValueError("count or seed out of range")
    state = seed
    for sequence in range(count):
        state = (1664525 * state + 1013904223) & 0xffffffff
        price = 10000 + state % 41 - 20
        state = (1664525 * state + 1013904223) & 0xffffffff
        yield Quote(sequence, price, state % 41)
