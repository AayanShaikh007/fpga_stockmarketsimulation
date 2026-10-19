# NanoQuant quote protocol v1

Proposed physical transport: UART 115200 baud, 8 data bits, no parity, 1 stop bit.
Physical UART receiver/transmitter and FPGA packet parsing are future work.
This slice tests Python serialization and feeds decoded fields directly into RTL.

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

`decode` requires one complete packet and rejects invalid length, header, flags,
or CRC. It is not a stream resynchronizer. A future UART adapter must buffer and
validate a whole frame before asserting `in_valid`. Corrupted kill packets are
rejected like other corrupted packets; this is not an independent emergency stop.

The kill flag latches only on an accepted quote. It blocks the same quote and all
subsequent quotes until reset. It does not liquidate an existing position.
There is no response packet format yet.
