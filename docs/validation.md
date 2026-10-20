# Validation — October 20, 2026

## Physical UART check in the current checkout

On October 20, 2026, the Tang Nano 9K connected on COM6 completed:

```powershell
. .\tools\activate.ps1
python -m nanoquant.serial_demo --port COM6 --count 20 --seed 1 --kill-at-end
```

Run directory: `C:\Coding\fpga_stockmarketsimulation`. Exit status: 0.
All 22 replies passed response header, CRC, sequence, order, position, kill-state,
and architectural cycle-count checks against the Python reference. Sequences
0–19 exercised buy, sell, and hold decisions; sequence 20 latched kill and
sequence 21 confirmed it persisted. Final simulated position: -43.
Host round-trip times ranged from 4.1930 to 4.6643 ms, including UART, USB,
OS scheduling, and host processing; these are not isolated FPGA engine latency.
The reported `engine_cycles=1` is an architectural constant, not a measured timer.
Raw output is saved locally in `build/hardware-serial-check.log` (Git-ignored).
Reset the board before running again because this check leaves kill latched.
LED appearance, power cycling, and long-duration hardware operation were not
checked by this run. The original development record below is historical and
predates this successful physical UART check.

All work and checks ran in `C:\Users\shaik\Coding\nanoquant`.

## Confirmed

- Python 3.12.14: `python -m unittest discover -s tests -v` equivalent using the
  bundled absolute interpreter path: **14 tests passed, zero skipped**.
- Original engine equivalence: 1,047 cycles compared to Python, including risk
  boundaries, idle cycles, resets, kill, and 1,000 seeded quotes.
- Python invariants: 10,000 deterministic quotes; order and position constraints.
- Serial integration: full bit-level 8N1 input, independently sampled output,
  reply CRC and fields compared with Python. Includes positive/negative position
  saturation, order clipping, kill/reset, noise, overlapping markers, corrupt CRC,
  invalid version/flags with valid CRC, partial timeout, deleted byte, bad stop bit,
  false start, reset mid-packet, busy quote dropping, and recovery.
- Production divider tested at 234 clocks/bit and incoming periods 230/238 clocks
  per bit (about ±1.7% period mismatch); this is simulation evidence only.
- Yosys synthesis and structural check: zero reported problems.
- nextpnr place-and-route: PASS at 27 MHz; post-route estimated maximum 29.81 MHz.
- Resource report: 1,351/8,640 LUT4 sites (~15%), 490/6,480 DFF sites (~7%).
- `gowin_pack` generated `build/nanoquant.fs` successfully.
- `python tools/build.py` executed the complete build successfully.

Tools: OSS CAD Suite 20261019, Icarus Verilog 14.0 development build
`s20260301-617-geed9291c8-dirty`, Yosys `0.70+157` (`af9f71e51`),
nextpnr `0.11.1-65-ge677d5c3`. These tools were run from a portable suite under
the chat workspace's `work/` directory, not installed system-wide. Both suite
`bin` and `lib` must be on PATH. An installer attempt was blocked by automatic
approval review; the portable distribution was used successfully.

The packer warned that optional NumPy, msgspec, and fastcrc accelerators were
missing; it completed using fallback implementations. Initial simulator runs
failed because the suite's lib directory was absent from PATH; after correcting
the environment, the full suite passed. RTL timescale warnings were resolved.

## Not verified

- Gowin IDE project loading, Gowin-specific synthesis, and Gowin timing results.
- Physical board revision, USB drivers, COM port, reset behavior, startup behavior,
  power-cycle behavior, actual UART exchange, or programming success.
- Physical latency or maximum frequency. Timing figures above are tool estimates.
- The live `serial_demo` against hardware or pyserial behavior on that PC.
- Nondefault engine parameters through HDL equivalence, formal verification,
  exhaustive error recovery, and continuous/pipelined traffic.

No physical FPGA was connected. A generated bitstream is available locally but
is not a hardware acceptance result. Build outputs and downloaded tool binaries
are intentionally excluded from source control.
