# NanoQuant — FPGA Development Journal

> Historical journal: the sections below describe an earlier session. The later
> October 20 UART check passed all 22 replies on COM6, and Gowin synthesis passed
> after the LED module and width fixes. See `docs/validation.md` and `code_agent.md`
> for the current verified state. Persistent flash programming remains unverified.

**Date:** October 20, 2026  
**Project:** NanoQuant — FPGA Stock Market Simulation  
**Hardware:** Sipeed Tang Nano 9K  
**Software:** Gowin EDA Education Edition, Verilog, Python, PySerial  
**Repository:** https://github.com/AayanShaikh007/fpga_stockmarketsimulation  
**Local directory:** `C:\Coding\fpga_stockmarketsimulation`

## 1. Project Objective

NanoQuant is an FPGA-accelerated stock market simulation and trading-signal engine built around the Sipeed Tang Nano 9K.

The goal is to create a hardware-software system that:

- Generates simulated stock-market price data in Python.
- Transmits market data to an FPGA over UART.
- Processes prices using a Verilog-based trading engine with risk checks.
- Returns trading decisions to Python.
- Visualizes price movements, positions, and trading activity through a React dashboard.
- Benchmarks FPGA processing latency against equivalent Python and C++ implementations.

The long-term objective is to explore hardware acceleration, deterministic processing, and low-latency trading-system architecture.

---

## 2. Gowin EDA Setup

**Status: Completed**

Installed and configured Gowin EDA Education Edition for developing and programming the Tang Nano 9K.

### Hardware configuration

| Property | Value |
|---|---|
| FPGA board | Sipeed Tang Nano 9K |
| FPGA family | GW1NR |
| Device | GW1NR-9C |
| Package | QN88P |
| Speed grade | C6/I5 |
| Part designation | GW1NR-LV9QN88PC6/I5 |
| Onboard clock | 27 MHz |
| Programming interface | USB-JTAG |

Learned the responsibilities of the main Gowin development files:

| Extension | Purpose |
|---|---|
| `.v` | Verilog hardware description |
| `.cst` | Physical pin assignments and I/O constraints |
| `.sdc` | Timing constraints |
| `.gprj` | Gowin FPGA project |
| `.fs` | Generated FPGA programming bitstream |

### Gowin compilation process

Successfully used the primary development workflow:

1. Create or open an FPGA project.
2. Add Verilog source files.
3. Configure physical pin constraints.
4. Run synthesis.
5. Run placement and routing.
6. Generate the FPGA bitstream.
7. Program the physical board using Gowin Programmer.

In the installed Gowin version, bitstream generation is integrated into the Place & Route workflow rather than exposed as a separate process item.

---

## 3. First Successful Hardware Test — LED Blinker

**Status: Completed and physically verified**

Created a basic Verilog LED-blinking design to validate the development environment before attempting NanoQuant.

### Files

- `blink.v` — Counter-based LED control.
- `blink.cst` — Clock and LED pin assignments.

The test used the onboard 27 MHz clock and targeted the Tang Nano 9K's LEDs.

### Results

Successfully:

- Synthesized the Verilog design.
- Completed placement and routing.
- Generated the programming bitstream.
- Connected to the FPGA using Gowin Programmer.
- Uploaded the bitstream.
- Observed the design working on the physical board.

**Milestone achieved:** First successful custom FPGA design running on the Tang Nano 9K.

This established that the board, USB connection, programming interface, Gowin installation, and basic compilation workflow were functioning.

---

## 4. Timing Constraint Warning

**Warning encountered:**

```text
WARN (TA1132): 'clk' was determined to be a clock but was not created.
```

### Explanation

Gowin recognized the Verilog `clk` signal as a clock but did not have an explicit timing definition for it.

The Tang Nano 9K uses a 27 MHz oscillator, corresponding to approximately 37.037 ns per clock cycle.

### Suggested solution

Define the clock in an `.sdc` file:

```tcl
create_clock -name clk -period 37.037 -waveform {0 18.518} [get_ports {clk}]
```

This allows the timing analyzer to evaluate the design against the intended clock frequency.

**Status:** Constraint identified and fix provided. The conversation did not separately confirm whether this specific warning was eliminated.

---

## 5. Transition to NanoQuant Hardware

**Status: Compilation progressed; physical communication not yet validated**

After successfully programming the LED blinker, moved toward deploying the NanoQuant trading engine.

The existing GitHub project was used rather than starting a new implementation.

The intended FPGA integration includes:

- UART receiver and transmitter.
- Market-data packet handling.
- Trading-signal processing.
- Risk-management logic.
- Response packet generation.
- Gowin constraints and timing configuration.

The intended top-level module is `nanoquant_top`.

### Compilation issue — Bank voltage conflict

During Place & Route, Gowin produced:

```text
ERROR (CT1136) : Bank 3 vccio(1.8) is locked by other constraint or embedded port, conflicting BANK_VCCIO set by 'rst_n_ibuf' : IO_TYPE = LVCMOS33 in the same bank
```

### Cause

The reset input was configured using a 3.3 V logic standard, conflicting with a bank constrained to 1.8 V.

### Suggested correction

Change the affected reset pin's I/O standard from:

```text
IO_TYPE=LVCMOS33
```

to:

```text
IO_TYPE=LVCMOS18
```

For the proposed reset constraint:

```text
IO_LOC "rst_n" 4;
IO_PORT "rst_n" IO_TYPE=LVCMOS18 PULL_MODE=UP BANK_VCCIO=1.8;
```

The correction should remain consistent with the actual physical bank voltage and board schematic.

### Result

After addressing the issue, reported that the design was running.

**Important:** Subsequent messages suggest compilation and/or programming succeeded, but a verified NanoQuant hardware transaction has not yet been demonstrated.

---

## 6. Python Environment and Serial Port Discovery

**Status: Completed**

Opened PowerShell in the NanoQuant repository and confirmed that the Python hardware dependencies were available.

Command:

```powershell
python -m pip install -r requirements-hardware.txt
```

Result:

```text
Requirement already satisfied: pyserial==3.5
```

The environment used the repository's Python virtual environment:

```text
C:\Coding\fpga_stockmarketsimulation\.venv
```

### Serial port discovery

Executed:

```powershell
python -m serial.tools.list_ports
```

Output:

```text
COM5
COM6
COM8
COM28
4 ports found
```

Windows detected four serial ports.

For initial testing, selected `COM6`.

**Note:** COM6 was not definitively confirmed as the Tang Nano 9K UART interface. Further identification using verbose port information or an unplug/replug comparison was recommended.

---

## 7. First NanoQuant FPGA Communication Attempt

**Status: Failed — debugging required**

Ran the existing NanoQuant hardware test:

```powershell
python -m nanoquant.serial_demo --port COM6 --count 20 --seed 1 --kill-at-end
```

The command was intended to transmit 20 simulated market-data inputs to the FPGA, read trading decisions, and compare the results against the Python reference implementation.

### Actual terminal output

```text
Reset the FPGA before each run; reference position starts at zero.

Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Coding\fpga_stockmarketsimulation\nanoquant\serial_demo.py", line 53, in <module>
    main()
  File "C:\Coding\fpga_stockmarketsimulation\nanoquant\serial_demo.py", line 42, in main
    sequence, order, position, killed, cycles = decode_response(packet)
  File "C:\Coding\fpga_stockmarketsimulation\nanoquant\protocol.py", line 42, in decode_response
    raise ValueError('response header')
ValueError: response header
```

### Interpretation

Python successfully opened the serial interface and reached the response-decoding stage, but the received data failed the expected protocol-header validation.

This does not establish that the FPGA successfully processed the transmitted packet.

Potential causes identified:

1. Incorrect serial port.
2. Incorrect or stale bitstream running on the FPGA.
3. UART TX/RX configuration or baud-rate mismatch.
4. Unexpected bytes, packet framing, or protocol mismatch.

No root cause has been conclusively established.

---

## 8. Investigation — SRAM vs Embedded Flash Programming

**Status: Identified as a potential cause; fix not yet confirmed**

During troubleshooting, realized that the FPGA had been unplugged and reconnected after an earlier programming session.

This matters because Gowin supports different configuration modes.

### SRAM programming

- Loads the design into volatile configuration memory.
- Starts the design immediately.
- Loses the configuration when power is removed.
- May require reprogramming after reconnecting the board.

### Embedded Flash programming

- Stores the FPGA configuration persistently.
- Allows the configuration to reload on power-up.
- Is better suited for repeated standalone hardware testing.

A possible explanation for the invalid UART response is that NanoQuant had previously been programmed only into SRAM and the board lost that configuration when unplugged.

After reconnecting, the FPGA may have loaded an older design or an unrelated configuration from flash.

### Recommended action

In Gowin Programmer:

1. Load the NanoQuant `.fs` bitstream.
2. Select Embedded Flash Mode.
3. Choose `embFlash Erase, Program`.
4. Program the board.
5. Confirm the successful completion message.
6. Reset the FPGA.
7. Confirm the COM port.
8. Rerun the Python hardware test.

**Status at end of session:** The embedded-flash programming result and subsequent UART test have not yet been reported.

---

## 9. Planned React Dashboard

**Status: Design planned; implementation not yet confirmed**

Discussed the eventual dashboard design and its integration with the FPGA hardware.

### Proposed interface

A dark-themed NanoQuant trading terminal including:

- Live simulated market-price chart.
- Latest FPGA-generated BUY / SELL / HOLD signal.
- Current position and risk indicators.
- Recent trades and decision history.
- FPGA connection status.
- Processing and communication latency.
- Comparison between FPGA, Python, and C++ performance.

### Proposed architecture

```text
Python Market Simulator
         |
         v
   USB / UART Link
         |
         v
   Tang Nano 9K FPGA
   -----------------
   Trading Engine
   Risk Management
   Response Encoder
         |
         v
   UART Response
         |
         v
 Python Backend Server
         |
      WebSocket
         |
         v
  React Dashboard
```

The frontend will be able to run against simulated data before physical FPGA communication is fully stable.

Once UART communication is verified, the Python backend can stream physical FPGA responses to the React interface.

---

## 10. Development Progress Summary

| Milestone | Status |
|---|---|
| Gowin EDA configuration | Complete |
| First Verilog project | Complete |
| LED-blinker synthesis | Complete |
| LED-blinker FPGA programming | Verified |
| NanoQuant project compilation | Progressed |
| Bank voltage conflict | Reported resolved |
| Python dependencies | Complete |
| Serial-port enumeration | Complete |
| NanoQuant UART protocol test | Failed |
| Persistent NanoQuant flash programming | Not yet verified |
| FPGA trading decision validation | Pending |
| React dashboard implementation | Pending |
| Python/C++/FPGA benchmarks | Pending |

---

## 11. Next Development Session

### Priority 1 — Restore and verify FPGA configuration

- [ ] Open Gowin Programmer.
- [ ] Select the correct NanoQuant bitstream.
- [ ] Program Embedded Flash.
- [ ] Confirm successful programming.
- [ ] Reset the Tang Nano 9K.

### Priority 2 — Debug serial communication

- [ ] Identify the board's correct COM port.
- [ ] Check the UART baud rate and TX/RX pin assignments.
- [ ] Flush stale serial data before running tests.
- [ ] Capture raw response bytes if header validation still fails.
- [ ] Verify response packet framing.
- [ ] Confirm FPGA-generated decisions match the Python reference.

### Priority 3 — Begin dashboard development

- [ ] Initialize or extend the React/Vite frontend.
- [ ] Implement the main trading dashboard layout.
- [ ] Add simulated price charts and signal history.
- [ ] Create a Python backend for streaming results.
- [ ] Integrate FPGA UART responses through WebSocket.

### Priority 4 — Performance measurement

- [ ] Measure the FPGA trading-engine cycle count.
- [ ] Separate compute latency from UART transfer latency.
- [ ] Build equivalent Python and C++ implementations.
- [ ] Run repeatable performance comparisons.
- [ ] Display measured results in the React dashboard.

---

## 12. Session Reflection

Today marked the transition from learning basic FPGA programming to attempting a complete hardware-software application.

The most significant accomplishment was successfully compiling and running a custom Verilog LED design on a physical Tang Nano 9K.

The session also introduced practical FPGA engineering concepts, including physical pin constraints, timing constraints, voltage-bank compatibility, volatile versus persistent configuration, and serial communication debugging.

NanoQuant's first physical UART integration attempt revealed a protocol validation error. This remains an active issue rather than a completed integration.

The next major milestone is to demonstrate one verified market-data transaction from Python to the Tang Nano 9K and back, with the result matching the software reference implementation.

**End-of-session status:** FPGA development environment operational; first hardware design successfully verified; NanoQuant hardware communication debugging in progress.