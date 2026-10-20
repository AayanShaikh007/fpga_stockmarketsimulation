import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus Verilog missing')
class LedTests(unittest.TestCase):
    def test_actions_pulse_expiry_kill_error_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / 'leds.vvp')
            subprocess.run(['iverilog', '-g2012', '-Wall', '-s', 'tb_action_leds',
                            '-o', output, str(ROOT / 'rtl/nanoquant_top.v'),
                            str(ROOT / 'tests/tb_action_leds.v')], check=True, timeout=30)
            result = subprocess.run(['vvp', output], check=True, capture_output=True,
                                    text=True, timeout=30)
            self.assertIn('LED checks passed', result.stdout)
