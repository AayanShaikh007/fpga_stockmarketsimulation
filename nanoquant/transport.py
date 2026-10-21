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
    def __init__(self, message, *, code='transport'):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Reply:
    sequence: int
    order: int
    position: int
    killed: bool
    engine_cycles: int
    host_round_trip_us: float
    python_compute_us: float | None = None


class SerialSession:
    def __init__(self, port, *, serial_factory=serial.Serial):
        self.reference = Engine()
        self.failed = False
        self.metrics = dict(requests_attempted=0, requests_sent=0, replies_received=0,
                            validated_replies=0, crc_errors=0, header_errors=0,
                            timeouts=0, sequence_errors=0, reference_errors=0, transport_errors=0)
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
            self.metrics['requests_attempted'] += 1
            if self.port.write(request) != len(request):
                raise CommunicationError('Incomplete UART write.')
            self.metrics['requests_sent'] += 1
            packet = bytearray()
            deadline = time.monotonic() + 2
            while len(packet) < RESPONSE_SIZE and time.monotonic() < deadline:
                block = self.port.read(RESPONSE_SIZE-len(packet))
                if not block:
                    break
                packet.extend(block)
            elapsed = (time.perf_counter_ns()-start)/1000
            if len(packet) != RESPONSE_SIZE:
                raise CommunicationError('Response timeout. No retry was sent.', code='timeout')
            self.metrics['replies_received'] += 1
            try:
                sequence, order, position, killed, cycles = decode_response(packet)
            except ValueError as exc:
                raise CommunicationError(str(exc), code='crc' if 'CRC' in str(exc) else 'header') from exc
            before = time.perf_counter_ns()
            expected = self.reference.step(quote)
            python_us = (time.perf_counter_ns()-before)/1000
            if sequence != quote.sequence or (order, position, int(killed)) != expected or cycles != 1:
                raise CommunicationError(f'FPGA/reference mismatch at sequence {quote.sequence}.',
                                         code='sequence' if sequence != quote.sequence else 'reference')
            self.metrics['validated_replies'] += 1
            return Reply(sequence, order, position, killed, cycles, elapsed, python_us)
        except Exception as exc:
            self.failed = True
            code = exc.code if isinstance(exc, CommunicationError) else 'transport'
            counter = {'timeout':'timeouts','crc':'crc_errors','header':'header_errors',
                       'sequence':'sequence_errors','reference':'reference_errors'}.get(code,'transport_errors')
            self.metrics[counter] += 1
            raise CommunicationError(f'{exc} Reset the FPGA before restarting.', code=code) from exc
        finally:
            # Preserve the existing post-reply pause, outside the RTT measurement.
            time.sleep(.002)

    def close(self):
        self.port.close()
