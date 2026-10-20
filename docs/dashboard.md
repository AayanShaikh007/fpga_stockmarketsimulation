# Local dashboard architecture

The React terminal runs at `http://127.0.0.1:5173`. Vite proxies `/api` and `/ws`
to one FastAPI process at `127.0.0.1:8000`. Keep the backend single-worker:
its controller is the process-wide run owner. Windows also opens serial ports
exclusively, so a second process or Gowin serial terminal cannot share COM6.
Gowin Programmer's JTAG interface is separate; close any tool using the UART port.

## Modes and data

Both modes reuse `nanoquant.feed.generate` with seed 1 and integer prices. There
is no stock exchange connection and all orders/fills remain simulated.

- **Simulation:** decisions come from `nanoquant.model.Engine`. Host UART latency,
  engine cycles, and FPGA estimates are null. Python step duration is measured
  separately with the host's monotonic performance clock.
- **FPGA Live:** quotes go to physical hardware through `nanoquant.transport`.
  That transport is also used by the original `nanoquant.serial_demo` command.
  Every reply is decoded with the existing protocol, checked for header/CRC,
  sequence, cycle count, and order/position/kill equivalence against Python.

The chart shows quote sequence rather than a fabricated market timescale. Markers
reflect nonzero executed order quantities. HOLD includes orders blocked by risk
limits. The UI retains the last 240 quotes and shows the last 12 filtered rows;
session JSON export contains the retained window, not a persistent full-run archive.

## WebSocket contract

Connect to `/ws`. The server sends `hello` with a client ID and status snapshot.
Further events are `status`, `telemetry`, or `command_error`.

```json
{"command":"start","config":{"mode":"simulation","speed":5,"seed":1}}
```

For a physical run, select a detected port, reset the FPGA, then explicitly
confirm that reset in the UI:

```json
{"command":"start","config":{"mode":"fpga","port":"COM6","reset_confirmed":true,"speed":5,"seed":1}}
```

Other commands: `{"command":"stop"}`, `{"command":"kill"}`, and
`{"command":"speed","speed":10}`. Speed is constrained to 1-20 quotes/second;
the rate is a pacing target, not a guaranteed throughput measurement.

Only the owning socket can control a run. Other tabs can observe its stream;
their start/stop/kill attempts are rejected while it is active. Owner disconnect
stops generation and waits for the current UART transaction to finish or time out
before closing the port. Reconnecting a browser never restarts a run automatically.
Observer queues are bounded; a slow observer can miss samples. Telemetry sequences
identify gaps. This is a live monitor, not a lossless recording service.

Each telemetry event includes UTC timestamp, run ID, mode, sequence, price,
requested quantity, signed executed order, decision, position, killed flag,
validation status, measured host round-trip microseconds (FPGA only), measured
Python step microseconds (simulation only), reported architectural engine cycles,
and estimated engine nanoseconds (FPGA only).

## Stop, kill, errors, and reset

Stop ends feed generation; it does not liquidate or send a kill packet. A normal
live stop still requires a physical reset before the next run, because Python's
reference model restarts at position zero. No software reset command exists in
the current FPGA protocol.

Kill requests a kill-flagged quote after the current transaction. The UI says
pending until its validated reply confirms the latch. A pending kill is honored
even if stop is requested. If communication fails first, the UI cannot claim kill
was acknowledged; physically reset the board to restore a known state.

One transaction sends exactly one quote, waits up to two seconds for its reply,
then preserves the existing 2 ms pause before another request. That pause is
outside the reported host round-trip measurement. Serial I/O runs in a worker
thread so it cannot freeze the event loop. Stop waits for this work rather than
cancelling it and allowing another run to race the still-owned port.

Timeout, malformed packet, CRC failure, sequence mismatch, reference mismatch,
USB disconnect, or serial-port contention stops the run. No trade is resent.
Every fresh FPGA run requires the operator's physical-reset confirmation,
including after a backend restart. The checkbox is operator attestation; software
cannot independently detect a button press or guarantee hardware resynchronization.

Host RTT includes request/response UART transfer, USB buffering, OS scheduling,
and host processing. `engine_cycles=1` reports architecture, not a physical timer.
`1 / 27 MHz ≈ 37.04 ns` is an architectural estimate, not measured computation
latency or a benchmark against Python. The earlier 4.19-4.66 ms result is historical;
the dashboard displays only measurements from the current captured session.

The service is intended for localhost development, without authentication. Bind
to loopback, use the documented frontend origins/port, and do not expose it to a
LAN or public host without adding an appropriate authentication/access design.
