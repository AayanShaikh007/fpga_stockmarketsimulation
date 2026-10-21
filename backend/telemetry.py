"""Base wire schema, extended with market/accounting data by the controller."""
from datetime import datetime, timezone


def telemetry(quote, result, mode, run_id, *, host_us=None, python_us=None, cycles=None):
    order, position, killed = result
    return {
        'type': 'telemetry', 'run_id': run_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'mode': mode, 'sequence': quote.sequence, 'price': quote.price,
        'quantity': quote.quantity, 'order': order,
        'decision': 'KILL' if killed else ('BUY' if order > 0 else 'SELL' if order < 0 else 'HOLD'),
        'position': position, 'killed': bool(killed),
        'validation_status': 'matched' if mode == 'fpga' else 'reference',
        'host_round_trip_us': host_us, 'python_compute_us': python_us,
        'engine_cycles': cycles,
        'estimated_engine_ns': cycles * 1e9 / 27_000_000 if cycles is not None else None,
    }
