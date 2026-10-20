export type Mode = 'simulation' | 'fpga'
export interface Telemetry {
  type: 'telemetry'; run_id: string; timestamp: string; mode: Mode
  sequence: number; price: number; quantity: number; order: number
  decision: 'BUY' | 'SELL' | 'HOLD' | 'KILL'; position: number; killed: boolean
  validation_status: 'matched' | 'reference'; host_round_trip_us: number | null
  python_compute_us: number | null; engine_cycles: number | null; estimated_engine_ns: number | null
}
export interface Status {
  type: 'status'; state: string; mode: Mode; run_id: string | null
  owner: string | null; speed: number; port: string; error: string | null
  reset_required: boolean; latest: Telemetry | null
}
export interface Port { device: string; description: string; hwid: string }
export const initialStatus: Status = { type: 'status', state: 'idle', mode: 'simulation', run_id: null, owner: null, speed: 5, port: '', error: null, reset_required: false, latest: null }
