"""Shared stop-and-wait UART transport for the CLI and local dashboard.

Each transaction is attempted exactly once. Any error makes the session unusable
until closed and the physical FPGA reset by the operator.
"""
import time
from dataclasses import dataclass

import serial

from .model import Engine
from .protocol import RESPONSE_SIZE, decode_response, encode


class CommunicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Reply:
    sequence: int
    order: int
    position: int
    killed: bool
    engine_cycles: int
    host_round_trip_us: float


class SerialSession:
    def __init__(self, port, *, serial_factory=serial.Serial):
        self.reference = Engine()
        self.failed = False
        self.port = serial_factory(port, 115200, timeout=2, write_timeout=2, exclusive=True)
        try:
            time.sleep(.1)
            self.port.reset_input_buffer()
        except Exception:
            self.port.close()
            raise

    def transact(self, quote):
        if self.failed:
            raise CommunicationError('Session invalid. Physically reset the FPGA before a new run.')
        try:
            start = time.perf_counter_ns()
            request = encode(quote)
            if self.port.write(request) != len(request):
                raise CommunicationError('Incomplete UART write.')
            packet = bytearray()
            deadline = time.monotonic() + 2
            while len(packet) < RESPONSE_SIZE and time.monotonic() < deadline:
                block = self.port.read(RESPONSE_SIZE-len(packet))
                if not block:
                    break
                packet.extend(block)
            elapsed = (time.perf_counter_ns()-start)/1000
            if len(packet) != RESPONSE_SIZE:
                raise CommunicationError('Response timeout. No retry was sent.')
            sequence, order, position, killed, cycles = decode_response(packet)
            expected = self.reference.step(quote)
            if sequence != quote.sequence or (order, position, int(killed)) != expected or cycles != 1:
                raise CommunicationError(f'FPGA/reference mismatch at sequence {quote.sequence}.')
            return Reply(sequence, order, position, killed, cycles, elapsed)
        except Exception as exc:
            self.failed = True
            raise CommunicationError(f'{exc} Reset the FPGA before restarting.') from exc
        finally:
            # Preserve the existing post-reply pause, outside the RTT measurement.
            time.sleep(.002)

    def close(self):
        self.port.close()
