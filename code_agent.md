# Code agent work log

This file records agent work for NanoQuant in
`C:\Coding\fpga_stockmarketsimulation`. Future work must be appended here as
required by `AGENTS.md`. Dates use America/Toronto. Earlier entries below were
reconstructed from this conversation on October 20, 2026; exact times were not
recorded. Existing project work predating this conversation is not agent work
from this session.

## 2026-10-20 - Restore the GitHub repository into the workspace root

- Request: bring files from `AayanShaikh007/fpga_stockmarketsimulation` directly
  into the current repository without creating a nested repository folder.
- Found the workspace already had the correct origin, but all tracked working
  files were missing. Local main was at `1f63b09`.
- Fetched origin, restored the missing tracked files, and fast-forwarded main
  to `d1db5c6`. Initial attempts encountered sandbox restrictions on Git metadata;
  approved commands completed the operations.
- Verified files were directly in the workspace root and the working tree was
  clean immediately after restoration. No commit or push was performed.

## 2026-10-20 - Prepare and run the project locally

- Read README, hardware instructions, validation notes, and build/test sources.
- Ran `python -m nanoquant --count 20 --seed 1` successfully with system Python
  at `C:\Python313\python.exe`.
- Initial test run: six passed and eight HDL tests skipped because Icarus Verilog
  was missing from PATH.
- Created `.venv` and installed the pinned hardware dependency, `pyserial==3.5`.
- Downloaded the official Windows x64 OSS CAD Suite 20261019 archive to
  `C:\tools\nanoquant-downloads` and extracted it to `C:\tools\oss-cad-suite`.
  Verified the published SHA256:
  `20dd77b47768318692ef657c481c567d6138ff6d16f1b292debdb9fba444ba43`.
- Added `tools/activate.ps1` to enable the project virtual environment and suite
  bin/lib paths for the current terminal. Documented setup commands in README.
  No persistent system PATH changes were made.
- With the toolchain enabled, all original 14 tests passed with zero skips.
- Ran `python tools/build.py`: synthesis, routing, and packing succeeded;
  generated `build/nanoquant.fs` (2,070,048 bytes). Initial post-route estimate
  was 29.81 MHz, passing the 27 MHz target. These are tool estimates.
- Build output is local and Git-ignored; logs include `build/build-run.log`.

## 2026-10-20 - Identify the board and troubleshoot programming access

- Initial USB inventory showed CircuitPython device COM28 and an unknown USB
  device with a port-reset failure. No FPGA programming probe was detected.
- Asked the user to reconnect with a data cable directly to the PC.
- After reconnection, detected FTDI VID:PID `0403:6010`, serial
  `FACTORYAIOT_PRO`, with UART on COM6. COM5/COM8 were Bluetooth ports.
- `openFPGALoader --scan-usb` and `-b tangnano9k --detect` could not access the
  probe using its installed FTDI drivers. No programming occurred through
  openFPGALoader.
- Explained the Zadig/WinUSB alternative for JTAG Interface 0 while retaining
  the UART driver on Interface 1. Did not replace any drivers.
- The user recalled an existing Gowin setup. Explained SRAM programming using
  Gowin Programmer and the generated bitstream, retaining the FTDI drivers.
- Subsequently found the installed programmer at
  `C:\Programs\Gowin\Gowin_V1.9.11.03_Education_x64\Programmer\bin\programmer.exe`
  and Gowin CLI at the corresponding `IDE\bin\gw_sh.exe`.
- Physical programming through the Gowin GUI was handled by the user; the agent
  did not operate that GUI or independently verify its programming steps.

## 2026-10-20 - Add onboard LED action indicators

- Request: show trades and actions on the board LEDs before further milestones.
- Checked Sipeed's official LED example for package pin mapping:
  LED indices 0-5 use pins 10, 11, 13, 14, 15, 16.
- Exposed engine result-valid and signed order signals from `nanoquant_core`.
- Added active-low LED logic and connected it in `nanoquant_top`:

  | LED index | Meaning |
  |---|---|
  | 0 | Any completed decision, including a killed quote |
  | 1 | Positive executed order / buy |
  | 2 | Negative executed order / sell |
  | 3 | Zero order while not killed / hold, including risk-blocked orders |
  | 4 | Kill latched until reset |
  | 5 | Protocol/framing error or busy dropped request, latched until reset |

- Decision/activity pulses last 5,400,000 clocks (200 ms at 27 MHz). Each event
  reloads its own timer; several LEDs can remain lit during rapid mixed actions.
- Added LED constraints and documented behavior in `docs/hardware.md`.
- The first LED build routed successfully but packing failed due to LVCMOS33
  LED outputs conflicting with the checkout's LVCMOS18 reset input in the shared
  bank. Matched LED outputs to LVCMOS18; packing then succeeded. Preserved the
  locally configured reset on pin 4 and its 1.8 V bank setting.
- Added `tests/tb_action_leds.v` and `tests/test_leds.py` to check buy/sell/hold
  patterns, pulse expiry, kill, error, and reset. All 15 tests passed.
- Updated LED design's post-route estimated maximum was 32.04 MHz, passing the
  27 MHz target; the updated bitstream was generated successfully.
- LED appearance on the physical board has not been verified by the agent.

## 2026-10-20 - First physical serial attempt

- Request: validate FPGA-to-Python communication, without building a dashboard.
- Ran the serial demo on COM6 with 20 quotes, seed 1, and kill-at-end.
- Port opened and data arrived, but decoding failed with
  `ValueError: response header`. Correct trading responses were not confirmed.
- Did not resend trading quotes automatically. A subsequent passive read returned
  no bytes. An initial passive-read command had a quoting error; corrected it.
- Asked the user to program the updated bitstream and reset before retrying.

## 2026-10-20 - Fix Gowin synthesis errors and width warnings

- User reported unknown module `action_leds` plus arithmetic truncation warnings.
- Found the generated `impl/gwsynthesis/nanoquant.prj` omitted the LED module,
  while the project file on disk included it. The loaded IDE source list was stale.
- Replaced unsized increment literals with explicit widths in `uart_rx.v`,
  `packet_rx.v`, `uart_tx.v`, and `nanoquant_core.v`.
- Made the engine's conversion of its 33-bit intermediate amount to the 32-bit
  signed order explicit. Amount is capped by the 16-bit maximum-order parameter.
- All 15 tests passed after the width fixes.
- Ran Gowin synthesis through a local Tcl script, `build/verify_gowin.tcl`:
  opened `nanoquant.gprj`, selected `nanoquant_top`, and ran `syn`.
  Synthesis succeeded with no WARN/ERROR entries; log: `build/gowin-verify.log`.
- When the user still received the unknown-module error in the IDE, moved the
  `action_leds` module definition directly into `rtl/nanoquant_top.v`, which was
  already in the loaded source list. Removed the separate `rtl/action_leds.v`
  file and its project/build entries; pointed the LED test at the top source.
- Reran all 15 tests and Gowin synthesis successfully, with no warnings/errors.
  This last verification ran synthesis; it did not itself run Gowin place-and-route
  or program hardware. User was instructed to reload the file and rebuild.

## 2026-10-20 - Successful physical FPGA-to-Python validation

- On the user's request to proceed to the communication milestone, detected COM6
  and ran:

  ```powershell
  . .\tools\activate.ps1
  python -m nanoquant.serial_demo --port COM6 --count 20 --seed 1 --kill-at-end
  ```

- Exit status 0. All 22 physical FPGA replies matched the Python reference.
  The checker validated response header, CRC, sequence, signed order, position,
  kill state, and architectural cycle count.
- Sequences 0-19 exercised buy, sell, and hold decisions. Sequence 20 latched kill;
  sequence 21 confirmed trading remained stopped. Final simulated position: -43.
- Measured host round trips ranged from 4.1930 to 4.6643 ms. These include USB,
  UART, OS, and host processing. `engine_cycles=1` is an architectural constant,
  not a measured FPGA latency result.
- Saved raw output in `build/hardware-serial-check.log` and added the physical
  result to `docs/validation.md`, distinguishing it from the historical record.
- This run left kill latched; reset is required before the next run. Current
  physical state may have changed since that observation.
- No React dashboard, WebSocket telemetry server, C++ benchmark, or isolated FPGA
  latency benchmark was built. LED visibility, power-cycle acceptance, and
  long-duration hardware reliability remain unverified.

## 2026-10-20 - Establish ongoing agent logging

- Request: log all work so far and future work in `code_agent.md`.
- Created this retrospective record and root `AGENTS.md` requiring future agents
  to read and update it for every task, including troubleshooting and read-only work.
- Inspected repository status and existing validation notes. Preserved unrelated
  local edits, including `.gitignore`; no commit or push was performed.
- Verification: checked that both new Markdown files exist and ran whitespace
  validation for them. No runtime tests were needed for these documentation changes.

## Current continuation notes

- Project root: `C:\Coding\fpga_stockmarketsimulation`.
- Activate tools: `. .\tools\activate.ps1` in PowerShell.
- Tests: `python -m unittest discover -s tests -v` (latest result: 15 passed).
- Open-source build: `python tools/build.py`.
- Gowin project: `nanoquant.gprj`; LED module is inside `rtl/nanoquant_top.v`.
- Last confirmed FPGA UART port: COM6; enumerate again before future hardware use.
- Reset before another serial demo. Avoid automatic retries after failed requests,
  since they might already have affected the simulated position.
- Hardware communication milestone passed. Dashboard is deferred until explicitly
  requested. Append future actions and results below rather than replacing history.

## 2026-10-20 - Commit and publish completed work before dashboard development

- Request: commit all completed work to GitHub in reasonably scoped commits before
  starting the dashboard. Use coherent commits for future development as well;
  do not manufacture changes, backdate commits, or split trivial edits for count.
- Reviewed all tracked and untracked changes, including the user-provided
  `development_journal.md`. Added a historical-status notice to that journal,
  refreshed stale README validation claims, and corrected the hardware guide's
  reset pin table to match the current pin 4 constraint.
- Removed an accidental whitespace-only `.gitignore` edit; no functional ignore
  rules changed. Kept virtual environments, binaries, build outputs, and local
  tool downloads excluded from Git.
- Reran the complete test suite: 15 passed, zero skips. `git diff --check` passed.
- Created six focused commits and successfully pushed them to `origin/main`:
  - `0161d03`: Windows activation and setup instructions.
  - `45c7c81`: explicit arithmetic widths in engine/parser/UART modules.
  - `09187af`: LED integration, core result outputs, core counter width fix,
    shared-bank constraints, and serial testbench port update.
  - `f0e2f21`: LED simulation coverage.
  - `9e26ff7`: hardware/LED guide and physical UART validation record.
  - `2442678`: historical development journal with a current-status notice.
- A partial staging patch for the core counter width failed to apply; the complete
  reviewed core change was included in the LED integration commit instead. No
  source changes were lost. Git Credential Manager briefly delayed the push,
  which then completed successfully.
- Added this log and `AGENTS.md` as the seventh commit group. The next action is
  to push that documentation commit and verify local/remote HEAD equality and a
  clean working tree. Dashboard source has not been created in this task.
