import { describe, it, expect } from 'vitest'
import { appendTelemetry, averageHostMs } from './telemetry'
import type { Telemetry } from './types'

const row: Telemetry = { type: 'telemetry', run_id: 'a', timestamp: '2026-10-20T00:00:00Z', mode: 'simulation', sequence: 0, price: 9999, quantity: 7, order: 0, decision: 'HOLD', position: 0, killed: false, validation_status: 'reference', host_round_trip_us: null, python_compute_us: 3, engine_cycles: null, estimated_engine_ns: null }
describe('telemetry history and measurement provenance', () => {
  it('clears previous run history and ignores duplicate sequences', () => {
    expect(appendTelemetry([row], { ...row, run_id: 'b' })).toHaveLength(1)
    expect(appendTelemetry([row], row)).toEqual([row])
  })
  it('bounds chart and export memory at 240 samples', () => {
    let rows: Telemetry[] = []
    for (let sequence=0; sequence<300; sequence++) rows=appendTelemetry(rows, {...row,sequence})
    expect(rows).toHaveLength(240)
    expect(rows[0].sequence).toBe(60)
  })
  it('does not report Python or architectural timing as measured host RTT', () => {
    expect(averageHostMs([row])).toBeNull()
    expect(averageHostMs([row, {...row,mode:'fpga',host_round_trip_us:4000}, {...row,mode:'fpga',host_round_trip_us:4600}])).toBe(4.3)
  })
})
