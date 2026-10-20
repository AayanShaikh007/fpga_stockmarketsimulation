import type { Telemetry } from './types'

export function appendTelemetry(previous: Telemetry[], row: Telemetry): Telemetry[] {
  // A fresh run must never inherit price or position history from another run.
  const sameRun = previous[0]?.run_id === row.run_id ? previous : []
  if (sameRun.at(-1)?.sequence === row.sequence) return sameRun
  return [...sameRun, row].slice(-240)
}

export function averageHostMs(rows: Telemetry[]): number | null {
  const measured = rows.filter(row => row.mode === 'fpga' && row.host_round_trip_us !== null)
  return measured.length ? measured.reduce((sum, row) => sum + row.host_round_trip_us!, 0) / measured.length / 1000 : null
}
