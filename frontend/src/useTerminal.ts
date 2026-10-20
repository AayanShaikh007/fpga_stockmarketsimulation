import { useCallback, useEffect, useRef, useState } from 'react'
import { initialStatus } from './types'
import type { Status, Telemetry } from './types'
import { appendTelemetry } from './telemetry'

export function useTerminal() {
  const [status, setStatus] = useState<Status>(initialStatus)
  const [rows, setRows] = useState<Telemetry[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [clientId, setClientId] = useState('')
  const socket = useRef<WebSocket | null>(null)
  useEffect(() => {
    let disposed = false
    let retry: ReturnType<typeof setTimeout>
    function connect() {
      if (disposed) return
      const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
      socket.current = ws
      ws.onopen = () => { if (!disposed) { setConnected(true); setError(null) } }
      ws.onmessage = event => {
        if (disposed) return
        const data = JSON.parse(event.data)
        if (data.type === 'hello') { setClientId(data.client_id); setStatus(data.status); setRows(data.status.latest ? [data.status.latest] : []) }
        else if (data.type === 'status') {
          setStatus(data)
          if (data.state === 'running' && !data.latest) setRows([])
        } else if (data.type === 'telemetry') {
          setRows(previous => appendTelemetry(previous, data))
        } else if (data.type === 'command_error') setError(data.message)
      }
      ws.onclose = () => {
        if (!disposed) { setConnected(false); setError('Backend disconnected. Active runs stop; reconnecting will not restart them.'); retry = setTimeout(connect, 2000) }
      }
      ws.onerror = () => ws.close()
    }
    connect()
    return () => { disposed = true; clearTimeout(retry); socket.current?.close() }
  }, [])
  const send = useCallback((message: object) => {
    if (socket.current?.readyState !== WebSocket.OPEN) { setError('Backend is offline. Start the Python service first.'); return }
    setError(null)
    socket.current.send(JSON.stringify(message))
  }, [])
  const clearHistory = useCallback(() => setRows([]), [])
  return { status, rows, connected, error: error || status.error, clientId, send, clearHistory }
}
