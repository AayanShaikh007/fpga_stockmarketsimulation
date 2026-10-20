import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from nanoquant.model import Engine, Quote
from nanoquant.protocol import crc16, decode_response, encode, RESPONSE_BODY

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['engine.v', 'uart_rx.v', 'uart_tx.v', 'packet_rx.v', 'nanoquant_core.v']


class ResponseTests(unittest.TestCase):
    def test_response_decoder(self):
        body = RESPONSE_BODY.pack(b'NR', 1, 1, 42, -20, -100, 1)
        packet = body + struct.pack('<H', crc16(body))
        self.assertEqual(decode_response(packet), (42, -20, -100, True, 1))
        for i in range(20):
            damaged = bytearray(packet)
            damaged[i] ^= 1
            with self.assertRaises(ValueError): decode_response(damaged)
        with self.assertRaises(ValueError): decode_response(packet[:-1])


@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus Verilog missing')
class SerialTests(unittest.TestCase):
    def simulate(self, commands, cpb=16, host_cpb=None):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'input.txt'
            source.write_text(''.join(f'{cmd} {value}\n' for cmd, value in commands), encoding='ascii')
            executable = directory / 'sim.vvp'
            subprocess.run(['iverilog', '-g2012', '-Wall', '-s', 'tb_serial',
                            f'-Ptb_serial.CPB={cpb}', f'-Ptb_serial.HOST_CPB={host_cpb or cpb}',
                            '-o', str(executable),
                            *[str(ROOT / 'rtl' / f) for f in SOURCES],
                            str(ROOT / 'tests/tb_serial.v')], check=True, timeout=30)
            result = subprocess.run(['vvp', str(executable), f'+INPUT={source.as_posix()}'],
                                    check=True, capture_output=True, text=True, timeout=60)
        raw = bytes(int(line.split()[1], 16) for line in result.stdout.splitlines()
                    if line.startswith('BYTE '))
        self.assertEqual(len(raw) % 20, 0, result.stdout)
        replies = [decode_response(raw[i:i+20]) for i in range(0, len(raw), 20)]
        engine = [tuple(map(int, line.split()[1:])) for line in result.stdout.splitlines()
                  if line.startswith('ENGINE ')]
        return replies, engine, result.stdout

    def test_serial_risk_and_kill(self):
        quotes = [Quote(i, 9995, 65535) for i in range(7)]
        quotes += [Quote(7+i, 10005, 65535) for i in range(12)]
        quotes += [Quote(19, 0, 20, True), Quote(20, 0, 20)]
        commands = []
        expected = []
        model = Engine()
        for q in quotes:
            commands += [(0, b) for b in encode(q)] + [(1, 16*230)]
            order, position, killed = model.step(q)
            expected.append((q.sequence, order, position, bool(killed), 1))
        replies, engine, _ = self.simulate(commands)
        self.assertEqual(replies, expected)
        self.assertEqual(engine, [(r[1], r[2], int(r[3])) for r in expected])

    def test_corruption_timeout_framing_and_recovery(self):
        q = Quote(42, 9993, 28)
        packet = encode(q)
        commands = [(0, 0x12), (0, 0x4e)]  # noise then overlapping N N Q
        commands += [(0, b) for b in packet] + [(1, 16*230)]
        # Invalid header with a correct CRC still must be rejected.
        for offset in (2, 3):
            body = bytearray(packet[:-2]); body[offset] = 2
            damaged = body + struct.pack('<H', crc16(body))
            commands += [(0, b) for b in damaged]
        damaged = bytearray(packet); damaged[8] ^= 1
        commands += [(0, b) for b in damaged]
        # Partial frame times out, then framing error aborts another frame.
        commands += [(0, b) for b in packet[:7]] + [(1, 16*50)]
        commands += [(0, b) for b in packet[:5]] + [(3, 0x55), (1, 16*50)]
        commands += [(0, b) for b in packet] + [(1, 16*230)]
        replies, engine, stdout = self.simulate(commands)
        self.assertEqual(replies, [(42, 20, 20, False, 1), (42, 20, 40, False, 1)])
        self.assertEqual(len(engine), 2)
        self.assertIn('ERROR 1', stdout)

    def test_busy_drops_quote_and_reset_clears_kill(self):
        q = Quote(1, 0, 20, True)
        commands = [(0, b) for b in encode(q)]
        commands += [(0, b) for b in encode(Quote(2, 0, 20))]  # arrives during response
        commands += [(1, 16*250), (2, 0)]
        commands += [(0, b) for b in encode(Quote(3, 0, 20))]
        replies, _, _ = self.simulate(commands)
        self.assertEqual(replies, [(1, 0, 0, True, 1), (3, 20, 20, False, 1)])

    def test_production_baud_divider(self):
        commands = [(0, b) for b in encode(Quote(5, 10005, 21))]
        replies, _, _ = self.simulate(commands, cpb=234)
        self.assertEqual(replies, [(5, -20, -20, False, 1)])

    def test_baud_mismatch(self):
        commands = [(0, b) for b in encode(Quote(5, 9995, 21))]
        for host_cpb in (230, 238):
            with self.subTest(host_cpb=host_cpb):
                replies, _, _ = self.simulate(commands, cpb=234, host_cpb=host_cpb)
                self.assertEqual(replies, [(5, 20, 20, False, 1)])

    def test_false_start_and_reset_partial_packet(self):
        packet = encode(Quote(8, 9995, 21))
        commands = [(4, 0)] + [(0, b) for b in packet[:8]]
        commands += [(2, 0), (1, 16*3)] + [(0, b) for b in packet]
        replies, engine, stdout = self.simulate(commands)
        self.assertEqual(replies, [(8, 20, 20, False, 1)])
        self.assertEqual(engine, [(20, 20, 0)])
        self.assertIn('ERROR 0', stdout)

    def test_deleted_byte_then_idle_recovers(self):
        packet = encode(Quote(9, 10005, 20))
        commands = [(0, b) for b in packet[:8] + packet[9:]]
        commands += [(1, 16*50)] + [(0, b) for b in packet]
        replies, engine, _ = self.simulate(commands)
        self.assertEqual(replies, [(9, -20, -20, False, 1)])
        self.assertEqual(engine, [(-20, -20, 0)])
