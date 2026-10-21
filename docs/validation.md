# Validation — October 20, 2026

## October 21 - Optional Alpaca PAPER execution

- Added paper-host-only execution, live-data/consent gating, persistent account
  telemetry, bounded long-only sizing, one-submit client IDs, durable local intents,
  partial/terminal fill reconciliation, and owned-order cancellation on stop/kill.
- Verification: 59 backend tests passed across the prior 50 plus nine broker tests;
  15 existing Python/RTL tests passed, zero skips; six frontend tests passed;
  TypeScript/Vite production build passed.
- Verified actual paper account read access and cash/equity fields using GET only.
  No actual paper orders were submitted during implementation. Submission, fill,
  cancel, timeout, and controller integration tests use mocked HTTP responses.
- Real-money hosts are unavailable; no RTL/protocol changes. The strategy editor,
  hypothesis/backtest experiment workspace, and backend-to-FPGA strategy deployment
  remain future work. Browser visual QA retains its prior verification limit.

## Market data and paper research milestone

- Existing reference/RTL suite: **15 passed, zero skipped**; no RTL or constraint
  changes were made for stock integration.
- Backend suite: **50 passed**, covering paper accounting/fees/cash constraints,
  fixed-anchor price mapping, mocked Alpaca authentication/subscription and paginated
  history, dataset integrity, replay completion, normalized fake-UART responses,
  live-source cancellation/failure cleanup, classified UART counters, and the prior
  stream/ownership/reset tests.
- Frontend unit suite: **3 passed**. TypeScript/Vite build passed and npm audit
  reported zero vulnerabilities.
- Running-service acceptance through the actual Vite HTTP/WebSocket proxy:
  synthetic DEMO replay emitted all 12 samples, retained explicit provenance,
  completed with ownership released, and produced a nonnegative-cash/long-only
  paper ledger. No serial packets were sent in that check. A live start with absent
  credentials returned an explicit setup error with no generated-data fallback.
- Local raw smoke evidence: `build/research-replay-check.jsonl` and
  `build/research-replay-summary.json`, both ignored by Git.
- No Alpaca credentials are configured on this PC, so real authenticated market
  streaming and real historical downloads are **not independently verified**.
  Provider tests use mocks; the offline DEMO is synthetic. The physical FPGA path
  has prior acceptance evidence below, but the new replay/stock path was tested
  with fake serial sessions rather than a fresh physical run.
- Browser visual/interaction QA remains unverified due to the existing saved
  localhost browser-access denial. No alternate browser-control route was used.
- FPGA packet-drop counts remain unavailable because the current protocol does
  not report them. Only actual host error/feed counters are displayed. Architectural
  cycle estimates and measured CPU/host times are never presented as equivalent
  physical compute benchmarks or a measured speedup ratio.

## Local React dashboard milestone

### Subsequent physical dashboard-backend acceptance

After the operator confirmed pressing/releasing the board buttons, one bounded
FPGA Live run used the actual FastAPI `/ws` endpoint, shared `SerialSession`, and
COM6 at five quotes/second with seed 1. All **21 physical responses passed**:
20 generated quotes followed by a WebSocket kill command and a validated kill
reply. BUY, SELL, HOLD, sequence, price/quantity mapping, header/CRC, position,
reference equivalence, and reported one-cycle architecture checks passed.
The final position was -43, kill was acknowledged, ownership was released, and
the final status required physical reset. No requests were retried.

Measured host RTT: minimum **4.1874 ms**, maximum **4.3436 ms**, mean
**4.2561 ms**. These are UART/USB/host measurements, not isolated engine latency.
The earlier CLI's second post-kill quote was not repeated here: the dashboard
intentionally stops after its first acknowledged kill.

Local evidence: `build/dashboard-hardware-check.jsonl` and
`build/dashboard-hardware-summary.json` (Git-ignored). The test used a protocol
client, not browser automation; browser visual/interaction QA remains unverified.
Reset S2 before another physical run. The implementation-stage limitations below
describe the state before this subsequent physical test.

The dashboard service reuses the deterministic market feed and Python reference;
the CLI and backend now share `nanoquant.transport.SerialSession` for validated
stop-and-wait physical UART I/O. No RTL or constraints changed in this milestone.

- Existing Python/HDL suite: **15 passed, zero skipped**.
- Backend tests: **18 passed**, including simulated WebSocket streaming, packet
  mapping, partial reads, CRC/sequence/reference failures, timeout without retry,
  serial contention, USB disconnect, owner disconnect, in-flight stop, pending
  kill acknowledgment, and physical-reset confirmation requirements.
- Frontend tests: **3 passed** (bounded history, run separation, and timing provenance).
- TypeScript and Vite production build: passed. Recharts is loaded separately.
- `npm audit`: zero reported vulnerabilities after updating Vitest.
- Real local-network smoke check through the Vite WebSocket proxy: 20 simulation
  quotes matched the existing generator/reference, kill was acknowledged, run
  ownership was released, and `/api/ports` listed COM6.
- Backend tests emit a dependency deprecation warning about Starlette's current
  httpx compatibility path; this did not affect the passing results.

Browser visual/interaction QA could not be completed: the available browser
tool's local-origin approval was declined. No alternate browser route was used.
The new dashboard's physical UART integration is implemented and tested with
injected serial sessions, but a fresh physical run has not been performed pending
operator reset confirmation. The successful physical result below predates this
shared-transport refactor and is not claimed as new dashboard hardware evidence.

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
