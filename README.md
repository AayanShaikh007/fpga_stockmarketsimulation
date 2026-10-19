# NanoQuant — Tang Nano 9K trading-engine portfolio project

First slice: a deterministic simulated feed, binary quote protocol, Python
reference engine, and synthesizable Verilog engine with a comparison testbench.
All fills are simulated immediately. This project does not place real orders.

## Step 1: Understand and run the Python model

Run commands from this project directory (`C:\Users\shaik\Coding\nanoquant`).
There are no third-party Python packages. Python 3.10+ is intended; Python 3.12.14
is the version actually tested here.

Standard Python installation, PowerShell or a Unix shell:

```text
python --version
python -m nanoquant --count 20 --seed 1
python -m unittest discover -s tests -v
```

On the current Windows machine `python` resolves to a Store shortcut. The
following exact PowerShell commands use the confirmed bundled runtime:

```powershell
Set-Location 'C:\Users\shaik\Coding\nanoquant'
$pythonExe = 'C:\Users\shaik\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonExe -m nanoquant --count 20 --seed 1
& $pythonExe -m unittest discover -s tests -v
```

The feed uses a 32-bit LCG: `state = (1664525*state + 1013904223) mod 2^32`.
Each quote advances twice: price is `10000 + state%41 - 20`, then quantity is
`state%41`. Same seed and count produce identical quotes. Seed 1 starts with
price 9999 and quantity 7. No wall clock or network data is involved.

The CSV demo prints the quote, signed order, resulting position, kill state,
and encoded packet. See [the wire specification](docs/protocol.md).

## Step 2: Understand the strategy and risk rules

Default fair price is 10000 ticks; threshold is 5 ticks. Buy when price is at
or below 9995, sell when at or above 10005, otherwise hold. Boundaries are
inclusive. Quantity is clipped to the requested quantity, maximum order size
(20), and remaining position capacity (position must stay between −100 and +100).
Positive orders buy; negative orders sell. A position of 99 permits a buy of
only 1. At +100 another buy is zero, while selling is permitted.

Kill blocks the current order and latches until reset. It preserves position.
Reset clears position, order, and kill state. This is a teaching signal model,
not a claim of profitability or a complete exchange execution/risk system.

## Step 3: Compare the FPGA logic

`rtl/engine.v` implements the same rules. Parameters must satisfy the Python
configuration bounds: unsigned 32-bit fair and threshold, max order 1–65535,
positive signed 32-bit position limit. Both models start at position zero.
The comparison currently tests the default configuration.

Interface: synchronous active-high reset; no backpressure. Each rising edge
with `in_valid=1` accepts the decoded fields. After that edge, `out_valid=1`
and order/position/killed represent that input. Reset takes priority. Invalid
cycles lower `out_valid` and retain the other outputs; kill is ignored on them.
The combinational decision path feeds one output register stage and supports
one accepted quote per cycle. This is an architectural latency description;
clock frequency and physical timing have not been measured.

Install Icarus Verilog using its official distribution for your OS, then ensure
both `iverilog` and `vvp` are on PATH. These version checks and simulation commands
are provided but could not be executed on the supplied machine:

```text
iverilog -V
vvp -V
python -m unittest discover -s tests -v
```

The comparison test generates 1,047 input cycles, compiles the RTL, runs it, and
compares every output cycle to Python, including reset, idle cycles, zero/max
quantities, threshold boundaries, full positions, price extremes, kill, and
1,000 seeded quotes. With the confirmed bundled Python, run it directly via:

```powershell
& $pythonExe -m unittest discover -s tests -p test_nanoquant.py -v
```

Equivalent manual simulator invocation (the vector file must have five decimal
fields per line: `reset valid price quantity kill`; the Python test creates it
automatically in a temporary directory):

```text
iverilog -g2012 -Wall -s tb_engine -o sim.vvp rtl/engine.v rtl/tb_engine.v
vvp sim.vvp +VECTORS=vectors.txt
```

## Confirmed results and dependency status

Validation on October 18, 2026: **5 tests passed, 1 skipped**. Python tests cover
determinism, CRC known answer, packet round trips and corruption, explicit risk
boundaries, kill/reset, validation, and invariants across 10,000 quotes. The CLI
demo was also executed successfully. An initial incorrect golden-test quantity
was corrected from 33 to 7 using the documented LCG states.

Confirmed: bundled Python 3.12.14, Python standard library, Git.
Missing from PATH: Icarus Verilog (`iverilog`, `vvp`), Verilator, Yosys.
Unverified: RTL compilation/simulation, synthesis, Tang Nano 9K resource fit,
pin assignments, clock constraints, programming tools, board behavior, and
physical timing. No board-specific build or timing claim is made in this slice.

## Next learning milestones

1. Run the Verilog comparison with Icarus; inspect waveforms and learn the
   difference between combinational calculations and registered state.
2. Add a UART receiver, full-frame validation, and board clock/reset integration.
   Define recovery from lost bytes and duplicate sequences before hardware use.
3. Add a React telemetry dashboard and a defined outbound telemetry protocol.
4. Implement equivalent C++ logic and benchmark Python/C++/FPGA under identical
   inputs and semantics. Measure **engine latency separately** from serialization,
   UART round-trip latency, and host scheduling. At 115200 baud, an 8N1 16-byte
   input alone consumes about 1.389 ms on the wire; this is arithmetic, not a
   measured benchmark. Report clock rate, sample counts, distributions, and
   measurement method; do not compare UART time with an in-process function call.
