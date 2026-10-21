export type Mode = 'simulation' | 'fpga'
export type DataSource = 'generated' | 'live' | 'replay'
export interface Paper {
  starting_cash: number; cash: number; position: number; average_cost: number
  market_value: number; equity: number; realized_pnl: number; unrealized_pnl: number
  total_pnl: number; fees: number; filled_order: number; unfilled_units: number; fill_count: number; policy: string
}
export interface Performance {
  uart: Record<string,number> | null; fpga_dropped_packets: number | null; fpga_drop_note: string
  host_rtt_count: number; host_rtt_mean_us: number | null; host_rtt_min_us: number | null
  host_rtt_max_us: number | null; host_rtt_p95_us: number | null; p95_window_samples: number
  python_mean_us: number | null; engine_timing_kind: string
  feed_samples_received: number; feed_samples_skipped: number; duplicate_feed_events: number
  stale_feed_events: number; observer_events_dropped: number
}
export interface Replay { id: string; symbol: string; source: string; timeframe: string; sha256: string | null; count: number; start: string; end: string }
export interface Telemetry {
  type: 'telemetry'; run_id: string; timestamp: string; mode: Mode
  sequence: number; price: number; quantity: number; order: number
  decision: 'BUY' | 'SELL' | 'HOLD' | 'KILL'; position: number; killed: boolean
  validation_status: 'matched' | 'reference'; host_round_trip_us: number | null
  python_compute_us: number | null; engine_cycles: number | null; estimated_engine_ns: number | null
  symbol?: string; data_source?: string; market_timestamp?: string | null
  price_usd?: number | null; anchor_usd?: number | null; input_quantity?: number
  control_only?: boolean; normalization?: string; paper?: Paper; performance?: Performance
  risk_checks?: { max_order: number; position_limit: number; position_before: number; position_after: number; order_within_limit: boolean; position_within_limit: boolean }
}
export interface Status {
  type: 'status'; state: string; mode: Mode; run_id: string | null
  owner: string | null; speed: number; port: string; error: string | null
  reset_required: boolean; kill_pending: boolean; latest: Telemetry | null
  source?: DataSource; symbol?: string; replay_id?: string; performance?: Performance
}
export interface Port { device: string; description: string; hwid: string }
export const initialStatus: Status = { type: 'status', state: 'idle', mode: 'simulation', run_id: null, owner: null, speed: 5, port: '', error: null, reset_required: false, kill_pending: false, latest: null }
