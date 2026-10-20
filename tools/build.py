"""Reproducible open-source Tang Nano 9K build; does not program hardware."""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['engine', 'uart_rx', 'uart_tx', 'packet_rx', 'nanoquant_core', 'nanoquant_top']


def main():
    for executable in ('yosys', 'nextpnr-himbaechel', 'gowin_pack'):
        if not shutil.which(executable):
            raise SystemExit(f'Missing {executable}; activate the OSS CAD Suite environment first.')
    (ROOT / 'build').mkdir(exist_ok=True)
    commands = [
        ['yosys', '-Q', '-T', '-l', 'build/synthesis.log', '-p',
         'read_verilog ' + ' '.join(f'rtl/{name}.v' for name in SOURCES)
         + '; synth_gowin -top nanoquant_top -json build/nanoquant.json; check'],
        ['nextpnr-himbaechel', '--device', 'GW1NR-LV9QN88PC6/I5',
         '--json', 'build/nanoquant.json', '--write', 'build/nanoquant_pnr.json',
         '--freq', '27', '-o', 'cst=constraints/tang_nano9k.cst', '-o', 'family=GW1N-9C',
         '--report', 'build/timing.json', '--log', 'build/route.log'],
        ['gowin_pack', '-d', 'GW1N-9C', '-o', 'build/nanoquant.fs', 'build/nanoquant_pnr.json'],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True, timeout=300)
    print('Built build/nanoquant.fs. No hardware was programmed.')


if __name__ == '__main__':
    main()
