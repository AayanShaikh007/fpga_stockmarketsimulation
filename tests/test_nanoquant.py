import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from nanoquant.feed import generate
from nanoquant.model import Engine, Quote
from nanoquant.protocol import crc16, decode, encode

ROOT = Path(__file__).resolve().parents[1]


def vectors():
    yield 1, 0, Quote(0, 0, 0)
    # Exact threshold, just inside threshold, quantity and position boundaries.
    for i, (price, qty) in enumerate([(9996, 20), (10004, 20), (9995, 0),
                                    (9995, 19), (9995, 20), (9995, 21),
                                    (0, 65535), (0, 65535), (0, 65535),
                                    (0xffffffff, 65535)] * 4):
        yield 0, 1, Quote(i, price, qty)
    for q in generate(1000, 42):
        yield 0, 1, q
    yield 0, 0, Quote(0, 0, 20, True)  # ignored on invalid cycle
    yield 0, 1, Quote(0, 0, 20, True)
    yield 0, 1, Quote(0, 0xffffffff, 20)
    yield 1, 1, Quote(0, 0, 20)  # reset has priority
    yield 0, 1, Quote(0, 0, 20)
    yield 0, 0, Quote(0, 0xffffffff, 20)


class ReferenceTests(unittest.TestCase):
    def test_feed(self):
        self.assertEqual(list(generate(100, 42)), list(generate(100, 42)))
        self.assertNotEqual(list(generate(10, 42)), list(generate(10, 43)))
        # LCG states: 1015568748, then 1586005467; modulo 41 gives 19, 7.
        self.assertEqual(list(generate(1, 1)), [Quote(0, 9999, 7)])

    def test_protocol(self):
        self.assertEqual(crc16(b'123456789'), 0x29b1)
        for q in [Quote(0xffffffff, 0xffffffff, 65535, True), *generate(100)]:
            self.assertEqual(decode(encode(q)), q)
        packet = encode(Quote(0, 10000, 20))
        for i in range(16):
            bad = bytearray(packet)
            bad[i] ^= 1
            with self.assertRaises(ValueError):
                decode(bad)
        for bad in [b'', packet[:-1], packet + b'0']:
            with self.assertRaises(ValueError):
                decode(bad)

    def test_risk_boundaries(self):
        e = Engine()
        def step(price, qty=65535, kill=False):
            return e.step(Quote(0, price, qty, kill))
        self.assertEqual(step(9996), (0, 0, 0))
        self.assertEqual(step(10004), (0, 0, 0))
        self.assertEqual(step(9995, 19), (19, 19, 0))
        self.assertEqual(step(9995, 21), (20, 39, 0))
        for _ in range(3): step(0)
        self.assertEqual(step(0), (1, 100, 0))
        self.assertEqual(step(0), (0, 100, 0))
        for _ in range(10): step(10005)
        self.assertEqual(e.position, -100)
        self.assertEqual(step(10005), (0, -100, 0))
        self.assertEqual(step(0), (20, -80, 0))
        self.assertEqual(step(0, kill=True), (0, -80, 1))
        self.assertEqual(step(0), (0, -80, 1))
        e.reset()
        self.assertEqual(step(0, 0), (0, 0, 0))
        self.assertEqual(step(0xffffffff), (-20, -20, 0))

    def test_invariants(self):
        e = Engine()
        for q in generate(10000, 123):
            order, position, _ = e.step(q)
            self.assertLessEqual(abs(order), min(q.quantity, 20))
            self.assertLessEqual(abs(position), 100)

    def test_validation(self):
        for args in [(0, -1, 1), (0, 0, 65536), (-1, 0, 0)]:
            with self.assertRaises(ValueError): Quote(*args)
        with self.assertRaises(ValueError): Engine(limit=0)


@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),
                     'Icarus Verilog (iverilog and vvp) not available on PATH')
class EquivalenceTests(unittest.TestCase):
    def test_rtl_matches_python(self):
        e = Engine()
        expected = []
        last_order = 0
        rows = []
        for reset, valid, q in vectors():
            rows.append(f'{reset} {valid} {q.price} {q.quantity} {int(q.kill)}\n')
            if reset:
                e.reset()
                last_order = 0
            elif valid:
                last_order, _, _ = e.step(q)
            expected.append((0 if reset else valid, last_order, e.position, int(e.killed)))
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = tmp / 'vectors.txt'
            path.write_text(''.join(rows), encoding='ascii')
            executable = tmp / 'sim.vvp'
            subprocess.run(['iverilog', '-g2012', '-Wall', '-s', 'tb_engine', '-o', str(executable),
                            str(ROOT / 'rtl/engine.v'), str(ROOT / 'rtl/tb_engine.v')], check=True, timeout=30)
            run = subprocess.run(['vvp', str(executable), f'+VECTORS={path.as_posix()}'],
                                 check=True, capture_output=True, text=True, timeout=60)
            actual = [tuple(map(int, line.split()[1:])) for line in run.stdout.splitlines()
                      if line.startswith('RESULT ')]
            self.assertEqual(len(actual), len(expected))
            for index, (got, want) in enumerate(zip(actual, expected)):
                self.assertEqual(got, want, f'vector {index}: {rows[index].strip()}')


if __name__ == '__main__':
    unittest.main()
