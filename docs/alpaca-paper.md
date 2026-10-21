# Alpaca PAPER account execution

This is optional simulated broker execution. The only supported trading host is
hardcoded `https://paper-api.alpaca.markets`. Real-money hosts, configurable trading
URLs, account resets, and historical order submission are not implemented.

## Use it

1. Keep your existing paper credentials in ignored `backend/.env`.
2. Choose **Alpaca PAPER account · virtual funds** under Portfolio/order destination.
3. Choose **Live stock trades**, then AAPL, NVDA, or TSLA.
4. Use **Read paper balance** to view cash/equity without submitting orders.
5. Choose Python engine or FPGA Live. Hardware still requires S2 reset/confirmation.
6. Check the explicit paper-order authorization box, then Start run during the
   regular US trading session. Closed-market starts fail before opening UART.
7. View simulated orders and fills on Alpaca's paper dashboard. Stop when finished.

Alpaca's current virtual account cash/equity are read, not reset to $100,000.
Holdings persist after stopping and across new runs. Account equity includes
other holdings, so it is not strategy-specific P&L. The local $10,000 simulator
remains the default and supports generated/live/replay data without broker orders.
Local fee settings and invented local fills are not applied to broker mode.

## Order behavior

- One account-backed sample per at least five seconds, plus order reconciliation,
  to keep requests bounded. The speed slider does not exceed that broker cap.
- Selected stock must be tradable, account active, regular market session open,
  and no existing open order for that stock. Do not trade the same stock manually
  or from another bot while a run owns it: separate processes are not coordinated.
- At most 20 whole shares per order and 100 selected shares held. Buys are sized
  from cash, not margin buying power. Sells are limited to existing long shares.
- Orders are DAY limit orders bounded at approximately 0.2% either side of the
  input mark, rounded outward to a cent. They may partially fill or not fill.
- Each submission has a unique run/sequence client order ID. An intent is fsynced
  to ignored `backend/data/paper-orders.jsonl` before the single POST.
- Only one order can be unresolved in a run. Its actual filled quantity/price/status
  comes from Alpaca. Polling is read-only and never repeats an order submission.
- Stop/kill or an eight-second fill wait requests cancellation of that run's pending
  order and checks for a terminal status. A cancellation request can race a fill;
  only the reconciled provider status is treated as terminal.
- Uncertain submission/cancellation stops the run and surfaces its client order ID.
  Review Alpaca before restarting. A GET by client order ID is used for cleanup
  after uncertain POST outcomes; there is no automatic retry of POST.
- Stop and kill do not liquidate persistent holdings, reset account equity, or cancel
  unrelated orders. The bot cannot guarantee cancellation during network failure.

Engine position still starts at zero for a fresh strategy run. Broker holdings are
checked separately and may include earlier runs. The UI distinguishes the two.
No broker fees, realized account P&L, or fills are fabricated from local estimates.

## Strategy research and FPGA deployment scope

Current strategy remains hardcoded. Hypothesis notes, editable/saved strategies,
autosave, frozen backtest snapshots, and out-of-sample comparison were proposed
as a future research workspace and are not implemented by this broker milestone.

Backend-driven FPGA configuration is possible after adding a configuration protocol,
registers, validation, and Python equivalence tests. Sending parameters for supported
rules is different from loading arbitrary algorithms. New algorithms generally need
new RTL/bitstreams, or a deliberately designed programmable execution architecture.

References: [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading)
and [order workflow](https://docs.alpaca.markets/us/docs/working-with-orders).
