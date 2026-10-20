# NanoQuant quote protocol v1

Transport: UART 115200 baud, 8 data bits, no parity, 1 stop bit, LSB first,
idle high. The implemented 27 MHz divider is 234 clocks per bit (115384.6 baud,
about +0.16%). No hardware flow control. UART reception, parsing, engine, and
response transmission are implemented in Verilog and tested in simulation.
Physical board operation remains unverified.

Every packet is exactly 16 bytes. All multibyte fields are unsigned little-endian.

| Byte offset | Size | Field |
|---|---|---|
| 0 | 2 | ASCII `NQ` (hex `4e 51`) |
| 2 | 1 | Version, exactly 1 |
| 3 | 1 | Flags: bit 0 kill; bits 1–7 must be zero |
| 4 | 4 | Sequence number, 0 through 2^32−1 |
| 8 | 4 | Price in integer ticks, 0 through 2^32−1 |
| 12 | 2 | Requested order quantity, 0 through 65535 |
| 14 | 2 | CRC-16/CCITT-FALSE over bytes 0–13, little-endian |

CRC parameters: polynomial 0x1021, initial 0xffff, no reflection, xor-out 0.
Check value for ASCII `123456789`: 0x29b1.
One tick is an application-defined fixed price unit; no floating point or implicit
currency conversion is performed. One quantity unit is one simulated asset unit.
Sequence is metadata in this slice; duplicates and gaps are not rejected.

Python `decode` requires one complete packet. The hardware parser scans for `NQ`,
including overlapping `NNQ`, then consumes the remaining 14 bytes as one candidate.
It verifies version, reserved flags, and CRC before asserting quote_valid.
It does not restart on embedded `NQ` inside a candidate. Rejected candidates
produce no trade and no reply. A framing error aborts the candidate. A partial
candidate expires after 270000 cycles without a decoded byte (10 ms at 27 MHz).
After byte insertion/deletion, continuous traffic is not guaranteed to recover
immediately; leave at least 12 ms idle before starting a new candidate.

The kill flag latches only on an accepted quote. It blocks the same quote and all
subsequent quotes until reset. It does not liquidate an existing position.
Corrupted kill packets are rejected like other corrupted packets. Kill is an
in-band teaching control, not an independent emergency stop.

## Reply protocol v1

Every accepted quote generates exactly one 20-byte reply. The host must send one
quote, receive its entire reply, and leave 2 ms idle before sending the next quote.
There is no queue: a fully validated quote arriving while the prior transaction
is active is dropped, including a kill quote. This sets the internal error latch.
The supplied host demo follows stop-and-wait. Do not pipeline quotes.

| Byte offset | Size | Field |
|---|---|---|
| 0 | 2 | ASCII `NR` |
| 2 | 1 | Version, exactly 1 |
| 3 | 1 | Bit 0: kill latched; other bits zero |
| 4 | 4 | Echoed quote sequence, unsigned little-endian |
| 8 | 4 | Signed order, two's-complement little-endian |
| 12 | 4 | Signed resulting position, two's-complement little-endian |
| 16 | 2 | Engine register-stage count, unsigned little-endian, currently 1 |
| 18 | 2 | CRC-16/CCITT-FALSE over bytes 0–17, little-endian |

The engine-stage field is an architectural constant, not a hardware stopwatch or
measured benchmark. Parser, response generation, UART, USB, and host time are
excluded from it. At 27 MHz, one clock period is about 37.04 ns; this is not a
measured input-wire-to-output-wire latency.

Sequence numbers are echoed, not deduplicated: retransmitting a quote can execute
another simulated order. On a missing reply, the host demo stops; it never retries
automatically. Reset before restarting to synchronize the host reference position
and the FPGA position. There is no error-response packet or position-query command
yet. The internal error latch is visible in simulation, not in reply flags.
