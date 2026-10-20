"""Stop-and-wait hardware check; install pyserial on the board-connected PC."""
import argparse

from .feed import generate
from .model import Quote


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='e.g. COM5 or /dev/ttyUSB1')
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--kill-at-end', action='store_true')
    args = parser.parse_args()
    try:
        from .transport import SerialSession
    except ImportError:
        parser.error('Install the hardware-only dependency: python -m pip install pyserial')
    quotes = list(generate(args.count, args.seed))
    if args.kill_at_end:
        quotes += [Quote(args.count, 0, 20, True), Quote(args.count + 1, 0, 20)]
    print('Reset the FPGA before each run; reference position starts at zero.')
    session = SerialSession(args.port)
    try:
        for quote in quotes:
            reply = session.transact(quote)
            print(f'seq={reply.sequence} order={reply.order} position={reply.position} '
                  f'killed={reply.killed} engine_cycles={reply.engine_cycles} '
                  f'host_round_trip_us={reply.host_round_trip_us:.1f}')
    finally:
        session.close()


if __name__ == '__main__':
    main()
