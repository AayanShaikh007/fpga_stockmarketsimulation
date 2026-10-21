# Market sources, paper trading, replay, and engineering metrics

Everything in NanoQuant remains local paper trading. There are no brokerage order
API calls, account transactions, or real-money execution in this application.

## Setup and data access

From the repository root, update Python dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

If `backend/.env` already exists, edit it rather than overwriting it. Put your own
Alpaca market-data key and secret in that ignored file, using a local editor:

```dotenv
ALPACA_API_KEY=your_key_id
ALPACA_SECRET_KEY=your_secret
```

Never paste keys into chat or put them in frontend code. Only the Python backend
reads them. `/api/provider` exposes a configured flag, never credentials. If you
prefer OS environment variables, they take precedence over the `.env` file.

Restart the backend to load changed Python code, then use the existing two-terminal
startup commands in README. The refresh icon in Market data rechecks credentials
and datasets without starting a run. Keys are necessary for real live data and
historical downloads; generated data and the synthetic DEMO replay work offline.
There is no silent fallback from a failed live API to generated prices.

The integration uses only these fixed, data-only Alpaca endpoints:

- `wss://stream.data.alpaca.markets/v2/iex`: authenticate, subscribe to trades for
  one of AAPL/NVDA/TSLA, then consume actual trade prints.
- `https://data.alpaca.markets/v2/stocks/bars`: download historical bars using GET,
  with `feed=iex`, `adjustment=raw`, ascending timestamps, and pagination.

Alpaca IEX is a single exchange, not consolidated market-wide coverage. Access
depends on your provider account/entitlements. Live prints may stop outside market
hours. Network, authentication, entitlement, or rate-limit errors are surfaced;
live streams do not reconnect automatically.

Official references: [stock streaming](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data),
[historical bars](https://docs.alpaca.markets/us/reference/stockbars), and
[coverage FAQ](https://docs.alpaca.markets/us/docs/market-data-faq).

## Choose data source independently from execution engine

| Data source | Python engine | FPGA Live |
|---|---|---|
| Generated | Existing repeatable generator/reference | Generated quotes sent to physical UART |
| Live stock trades | Real IEX prints, Python decisions | Real IEX prints transformed and sent to physical UART |
| Replay | Stored samples, Python decisions | Stored samples transformed and sent to physical UART |

Only one stock runs at a time. The physical design has one position register, so
interleaving symbols would wrongly combine their positions. Stock/source changes
require a fresh run, reset the paper portfolio, and require physical FPGA reset
when using hardware. Prices and market timestamps are distinct from host receipt
timestamps. Stock prices are displayed in USD; inspectors also show exact wire ticks.

## Transforming USD prices for the unchanged FPGA

The existing FPGA fair price remains 10,000 ticks, threshold 5, maximum order 20,
and position limit +/-100. We preserve the RTL and packet format by mapping:

```text
anchor = first accepted stock/replay price in the run
wire ticks = round-half-up(USD price / anchor * 10000)
```

The anchor never changes within a run. One tick is approximately one basis point
of the anchor; the signal threshold is approximately +/-5 bps from that fixed
anchor. This is a fixed-anchor demonstration strategy, not an estimated fair value
or a claim of profitability. Quantization can round boundary prices to a signal.
Generated demo data preserves its original exact wire ticks and uses a fixed $100
anchor, with synthetic USD marks equal to original ticks / 100.

Live requested quantity comes from a provider trade's size; replay requested
quantity comes from historical bar volume. Both are proxies for strategy order
requests, not evidence of executable liquidity. Wire quantity is capped at 65,535;
the engine then applies its own 20-unit and position-room limits.

Live trade bursts are sampled using a latest-event queue of size one. Superseded
events are counted separately from UART failures. Duplicate event IDs, events
older than 60 seconds, timestamps over five seconds in the future, and out-of-order
events are skipped and counted. This trades market-event completeness for bounded
memory and safe stop-and-wait hardware pacing. Speed is a processing cap, not a
promise of every exchange print or a guaranteed effective throughput.

## Replay workflow

1. Select Historical / offline replay in Market data.
2. Select AAPL, NVDA, or TSLA as the stock to download.
3. Choose UTC date bounds and 1Min, 5Min, or 1Day bars; click Download history.
4. Select the resulting dataset. Its symbol is authoritative for that run.
5. Choose Python engine or FPGA Live. Hardware still needs reset confirmation.
6. Adjust samples/second and start. Replay ends automatically at dataset exhaustion.

Downloads support up to 366 days and 20,000 bars, rejecting oversized ranges/results
rather than silently truncating them. Pagination tokens are checked for repetition.
Datasets retain symbol, source, timestamps, timeframe, raw prices, volumes, and a
SHA256 over canonical rows. Downloads and hashes are stored in ignored
`backend/data/`; dataset IDs cannot be filesystem paths. Timestamps must increase
strictly and content hashes are checked before replay. Credentials are not stored
in datasets. The selected dataset's hash is displayed in the UI.

The included 12-sample DEMO dataset is explicitly **synthetic**, not historical
AAPL/NVDA/TSLA data. It exists for repeatable offline acceptance tests. Downloaded
Alpaca bars use actual historical close prices. Raw bars are not split/dividend
adjusted; corporate actions, intrabar paths, and execution realism are not modeled.
There is no hidden interpolation or generated continuation when replay ends.

## Paper accounting

Each run starts with $10,000 cash and zero paper shares. The local Decimal ledger
tracks average cost, cash, market value, equity, realized/unrealized P&L, fees,
and fill count. Fees are configurable from 0 to 100 basis points; default is 1 bp.
Amounts settle to cents. No portfolio or trade is submitted to an exchange.

The portfolio is long-only and cash-funded. Buy fills are clipped to available
cash including fees; sells are clipped to paper holdings. Engine position and
paper position are shown separately because the engine can signal shorts or
orders that the cash ledger cannot fill. Inspectors show engine order, paper fill,
and risk checks; the paper panel shows unfilled units.

```text
equity = cash + paper shares * latest mark price
unrealized P&L = (latest price - average cost) * paper shares
realized P&L = closed-position gross gains/losses - all incurred fees
total P&L = equity - starting cash
```

This assumes immediate fills at the observed print/bar close, without bid/ask
spread, slippage, queue priority, taxes, or market impact. Results are strategy
simulation output, not evidence of attainable returns. Portfolio state resets
between runs and is not persisted to a database.

## Trade markers and metrics

Chart BUY/SELL markers represent nonzero engine decisions, including Python
decisions when that engine is selected. Click a marker (or keyboard-focus it and
press Enter/Space), or use its recent-marker button, to inspect source timestamp,
USD price, normalized wire price, quantities, sequence, engine/paper orders,
position checks, validation status, and host RTT.

The engineering panel distinguishes:

- **Measured:** host request-to-response RTT; cumulative mean/min/max; p95 over
  the latest up to 2,048 replies; isolated host Python reference step duration.
- **Architectural:** reported FPGA cycles and cycles / 27 MHz estimate. There
  is no independently measured FPGA computation timer or claimed speedup ratio.
- **Host UART counters:** attempted/sent requests, complete/validated replies,
  CRC/header errors, timeouts, sequence/reference failures, transport failures.
- **Feed/observer counters:** received/superseded market samples, stale/duplicate
  market events, and slow-browser queue discards. These are not FPGA packet drops.
- **Unavailable:** FPGA-side dropped packets. The existing reply protocol does
  not export that counter. A timeout does not identify where a packet was lost.

The shared transport still sends exactly once and waits for each response before
the next request, preserving the 2 ms post-transaction pause outside measured RTT.
Timeout/CRC/reference errors stop the run without resending a quote. Kill remains
responsive while a live market is idle; if no print has arrived, a clearly labeled
control-only kill has null market price/timestamp rather than a fabricated stock
quote. All new physical runs require S2 reset and explicit operator confirmation.

## Additional local endpoints

- `GET /api/provider`: safe provider setup/coverage metadata.
- `GET /api/replays`: stored dataset metadata and the synthetic demo.
- `POST /api/replays/download`: `{symbol,start,end,timeframe}` with timezone-aware
  ISO timestamps. Only one download runs at a time.
- WebSocket start config adds `source`, `symbol`, `replay_id`, and `fee_bps`.
  Existing clients omitting these fields keep generated-data behavior.

The entire terminal remains a localhost development application. Its existing
ownership, origin checks, reset requirements, and bounded browser-history limits
continue to apply. Session exports retain the last 240 samples, not every event.
