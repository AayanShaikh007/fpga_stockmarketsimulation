# NanoQuant — Tang Nano 9K FPGA trading-engine project

A learning and portfolio project: deterministic simulated market data, a Python
reference engine, and a matching Verilog engine with UART packet transport.
All orders and fills are simulated; this does not connect to an exchange.

**Current milestone:** UART RX, packet validation, trading engine, UART reply TX,
board wrapper, pin/clock constraints, and build flow are implemented.
**15 tests pass**, including bit-level serial simulation and Python/RTL comparison.
The complete design synthesizes, places, routes at 27 MHz, and produces a bitstream.
**Physical UART validation passed:** 22 replies matched Python, including kill behavior.
LED appearance, power cycling, and long-duration operation still need checking.

## Start with Python

From the project directory, with Python 3.10+ (3.12.14 actually tested):

```powershell
python -m nanoquant --count 20 --seed 1
python -m unittest discover -s tests -v
```

The core has no third-party Python dependencies. HDL tests need Icarus Verilog
(`iverilog` and `vvp`) on PATH; otherwise they are explicitly skipped.

For this checkout on Windows, once OSS CAD Suite is extracted to
`C:\tools\oss-cad-suite`, prepare and activate a project environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-hardware.txt
. .\tools\activate.ps1
python -m nanoquant --count 20 --seed 1
python -m unittest discover -s tests -v
python tools/build.py
```

Run the activation line in each new PowerShell terminal. For a different suite
location, use `. .\tools\activate.ps1 -SuitePath 'D:\tools\oss-cad-suite'`.
The helper changes PATH only for the current terminal. The build produces
`build/nanoquant.fs`; programming and checking the physical board are separate
steps described below.

On the original development PC, Python uses this confirmed bundled executable:

```powershell
Set-Location 'C:\Users\shaik\Coding\nanoquant'
$pythonExe = 'C:\Users\shaik\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonExe -m nanoquant --count 20 --seed 1
& $pythonExe -m unittest discover -s tests -v
```

The market generator uses a portable 32-bit LCG:
`state = (1664525*state + 1013904223) mod 2^32`. Each quote advances twice:
price is `10000 + state%41 - 20`, then quantity is `state%41`. Seed 1 begins with
price 9999 and quantity 7. Same seed and count always reproduce the same inputs.

## Strategy and risk rules

- Fair price: 10000 integer ticks; inclusive trading threshold: 5 ticks.
- Buy at price <=9995; sell at price >=10005; otherwise hold.
- Maximum order: 20 units. Position must remain between -100 and +100.
- Quantity is clipped to the request, maximum order, and remaining position room.
- Positive orders buy, negative orders sell. Fills occur immediately in this model.
- Kill blocks the current quote and latches until reset; it does not liquidate.
- Reset clears simulated position, order, and kill state.

One tick is an application-defined fixed unit; prices never use floating point.
For example, at position +99, a requested buy of 20 becomes a buy of 1.
The configured fair price is a teaching assumption, not an estimated market value
or a claim of profitability.

## UART and hardware: next hands-on step

Read [the step-by-step board guide](docs/hardware.md) for explanations, tool setup,
Gowin project instructions, board pin sources, and the PC serial checker.
Read [the packet specification](docs/protocol.md) for exact input/reply formats.

```text
PC -> UART RX -> validated quote -> engine -> reply formatter -> UART TX -> PC
```

Transport is 115200 baud 8N1 with a 27 MHz clock. Send **one quote at a time**,
wait for its reply, then pause 2 ms. Malformed packets do not trade. Requests that
arrive while a previous transaction is active are dropped; there is no queue.
Sequence numbers are echoed but not deduplicated. Never retry automatically after
a timeout; reset before restarting the demo to synchronize simulated positions.

With an activated [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases)
environment (both bin and lib on PATH):

```powershell
python -m unittest discover -s tests -v
python tools/build.py
```

Output: `build/nanoquant.fs`. The script does not program hardware. Alternatively,
open `nanoquant.gprj` in Gowin IDE and set `nanoquant_top` as top. That IDE path is
provided but unverified here; the open-source build is the confirmed flow.

After programming the correct board and pressing/releasing reset, on the board PC:

```powershell
python -m pip install -r requirements-hardware.txt
python -m serial.tools.list_ports
python -m nanoquant.serial_demo --port COM5 --count 20 --seed 1 --kill-at-end
```

Replace COM5 with the actual serial port. This hardware demo requires pyserial;
its 22-response live check passed on COM6; see the validation record.

## Files and testing

| Path | Purpose |
|---|---|
| nanoquant/model.py | Python decision and risk reference |
| nanoquant/feed.py | Repeatable simulated quotes |
| nanoquant/protocol.py | Quote encoding/decoding and reply decoding |
| nanoquant/serial_demo.py | Stop-and-wait PC-to-board checker |
| rtl/engine.v | Synthesizable trading engine |
| rtl/uart_rx.v, rtl/uart_tx.v | Serial byte reception/transmission |
| rtl/packet_rx.v | Header, CRC, timeout and framing validation |
| rtl/nanoquant_core.v | Parser/engine/reply integration |
| rtl/nanoquant_top.v | Clock, startup reset and board ports |
| rtl/tb_engine.v | Original engine simulation testbench |
| tests/test_nanoquant.py | Python tests and 1,047-cycle engine equivalence |
| tests/tb_serial.v, tests/test_serial.py | Serial bit-level tests and response checks |
| constraints/ | Tang Nano 9K physical and clock constraints |
| nanoquant.gprj | Gowin project template |
| tools/build.py | Reproducible synthesis, routing and packing |

Tests cover exact thresholds, size/position limits, kill/reset, 10,000-quote risk
invariants, corrupted packets, invalid headers, partial timeout, dropped bytes,
framing errors, false starts, reset mid-packet, busy requests, baud mismatch, and
recovery. HDL equivalence uses the default strategy configuration.

The engine uses synchronous active-high reset, accepts a quote on a rising edge
with in_valid, and registers order/position/killed for that quote. Reset takes
priority; invalid cycles retain state and lower out_valid. It has one output
register stage and supports one quote per cycle in isolation; this stop-and-wait
UART wrapper intentionally accepts transactions much more slowly.

## Confirmed results versus remaining checks

[Validation record](docs/validation.md), October 20, 2026:

- Python 3.12.14 and OSS CAD Suite 20261019: **14 passed, zero skipped** (original validation; current suite: 15 passed).
- Synthesis structural check: zero problems. Bitstream packing: successful.
- Post-route estimated maximum: 29.81 MHz, passing the 27 MHz target.
- Resource estimate: 1,351/8,640 LUT4 sites (~15%), 490/6,480 DFF sites (~7%).
- Current checkout: 22 physical UART replies matched Python on COM6; Gowin
  synthesis passed with no warnings or errors.
- Unverified: physical LED appearance, power-cycle behavior, isolated engine
  timing, long-duration operation, and nondefault HDL strategy configurations.

The original first slice had 5 passing Python tests and one skipped HDL test.
The portable toolchain now enables all HDL checks locally; the default system
PATH was not changed. See the validation record for exact tool versions and known
setup issues. Build files and downloaded tools are not committed.

## Later stages and latency

Broader board acceptance remains; next development is React telemetry and equivalent
Python/C++/FPGA benchmarks. Measure engine latency separately from UART round-trip
latency. The reply's engine_cycles=1 is an architectural constant, not a timer.
One 27 MHz cycle is about 37.04 ns; that is not an observed end-to-end measurement.
The live host demo separately measures send-to-reply time, including UART, USB,
OS scheduling, and reply processing. The physical UART check measured host round trips of 4.19-4.66 ms; isolated
engine latency has not been measured.
