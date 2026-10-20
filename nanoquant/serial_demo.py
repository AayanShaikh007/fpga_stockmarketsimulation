"""Stop-and-wait hardware check; install pyserial on the board-connected PC."""
import argparse
import time

from .feed import generate
from .model import Engine, Quote
from .protocol import encode, decode_response, RESPONSE_SIZE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='e.g. COM5 or /dev/ttyUSB1')
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--kill-at-end', action='store_true')
    args = parser.parse_args()
    try:
        import serial
    except ImportError:
        parser.error('Install the hardware-only dependency: python -m pip install pyserial')
    engine = Engine()
    quotes = list(generate(args.count, args.seed))
    if args.kill_at_end:
        quotes += [Quote(args.count, 0, 20, True), Quote(args.count + 1, 0, 20)]
    print('Reset the FPGA before each run; reference position starts at zero.')
    with serial.Serial(args.port, 115200, timeout=2, write_timeout=2) as port:
        time.sleep(0.1)
        port.reset_input_buffer()
        for quote in quotes:
            start = time.perf_counter_ns()
            port.write(encode(quote))
            packet = bytearray()
            deadline = time.monotonic() + 2
            while len(packet) < RESPONSE_SIZE and time.monotonic() < deadline:
                block = port.read(RESPONSE_SIZE - len(packet))
                if not block:
                    break
                packet.extend(block)
            elapsed_us = (time.perf_counter_ns() - start) / 1000
            if len(packet) != RESPONSE_SIZE:
                raise RuntimeError('Response timeout: reset board and check port, baud, bitstream')
            sequence, order, position, killed, cycles = decode_response(packet)
            expected = engine.step(quote)
            if sequence != quote.sequence or (order, position, int(killed)) != expected or cycles != 1:
                raise RuntimeError(f'Hardware mismatch: {bytes(packet).hex()}, expected {expected}')
            print(f'seq={sequence} order={order} position={position} killed={killed} '
                  f'engine_cycles={cycles} host_round_trip_us={elapsed_us:.1f}')
            # Allow the transmitter to finish its final stop bit before the next request.
            time.sleep(0.002)


if __name__ == '__main__':
    main()
