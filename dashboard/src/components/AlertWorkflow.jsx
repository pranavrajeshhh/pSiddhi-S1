import { useState, useEffect } from 'react'

const API = 'http://localhost:3001'

const SEVERITY_COLOR = { high: '#DC2626', medium: '#D97706', low: '#16A34A' }

export default function AlertWorkflow() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [lastRun, setLastRun] = useState(null)

  const fetchAlerts = () => {
    setLoading(true)
    fetch(`${API}/api/alerts/high`)
      .then(r => r.json())
      .then(data => {
        const arr = Array.isArray(data) ? data : []
        arr.sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at))
        setAlerts(arr)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    fetchAlerts()
    const id = setInterval(fetchAlerts, 30000)
    return () => clearInterval(id)
  }, [])

  const runAlertWorkflow = () => {
    setRunning(true)
    fetch(`${API}/api/alerts/run`, { method: 'POST' })
      .then(r => r.json())
      .then(data => {
        setLastRun(data.output || '')
        setRunning(false)
        fetchAlerts()
      })
      .catch(() => setRunning(false))
  }

  const byPipeline = alerts.reduce((acc, a) => {
    acc[a.pipeline_name] = (acc[a.pipeline_name] || 0) + 1
    return acc
  }, {})

  return (
    <div>
      <div className="section-title">Alert Workflow</div>
      <div style={{ fontSize: '0.78rem', color: '#64748B', marginBottom: '1.25rem' }}>
        High-severity anomalies are automatically routed to the alert log. Use the button below to run on-demand.
      </div>

      {/* KPI row */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <div className="stat-card" style={{ flex: 1, minWidth: 140 }}>
          <div className="stat-value" style={{ color: '#DC2626' }}>{alerts.length}</div>
          <div className="stat-label">Total High-Severity Alerts</div>
        </div>
        {Object.entries(byPipeline).map(([p, count]) => (
          <div key={p} className="stat-card" style={{ flex: 1, minWidth: 140 }}>
            <div className="stat-value">{count}</div>
            <div className="stat-label">{p.replace(/_/g, ' ')}</div>
          </div>
        ))}
        <div className="stat-card" style={{ flex: 1, minWidth: 140 }}>
          <div className="stat-value" style={{ color: '#16A34A' }}>JSON</div>
          <div className="stat-label">Alert log format</div>
        </div>
      </div>

      {/* Run button */}
      <div style={{ marginBottom: '1rem' }}>
        <button
          onClick={runAlertWorkflow}
          disabled={running}
          style={{
            background: running ? '#94A3B8' : '#DC2626',
            color: 'white', border: 'none', borderRadius: '0.4rem',
            padding: '0.5rem 1.25rem', cursor: running ? 'not-allowed' : 'pointer',
            fontWeight: 600, fontSize: '0.82rem',
          }}
        >
          {running ? '⏳ Running alert workflow…' : '🔔 Run Alert Workflow'}
        </button>
        {lastRun && (
          <pre style={{
            marginTop: '0.75rem', background: '#F8FAFC', border: '1px solid #E2E8F0',
            borderRadius: '0.4rem', padding: '0.75rem', fontSize: '0.7rem',
            color: '#334155', maxHeight: 120, overflow: 'auto',
          }}>{lastRun}</pre>
        )}
      </div>

      {/* Alert log table */}
      {loading ? (
        <div style={{ color: '#94A3B8', fontSize: '0.82rem' }}>Loading alert log…</div>
      ) : alerts.length === 0 ? (
        <div style={{ color: '#94A3B8', fontSize: '0.82rem' }}>
          No high-severity alerts in log yet. Run the alert workflow above to populate.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table table-compact" style={{ minWidth: 860 }}>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Pipeline</th>
                <th>Stage</th>
                <th>Anomaly Type</th>
                <th>Severity</th>
                <th>IF Score</th>
                <th>Detected At</th>
                <th>Notified At</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a, i) => (
                <tr key={a.alert_id}>
                  <td>{a.job_run_id ?? a.alert_id}</td>
                  <td>{a.pipeline_name}</td>
                  <td>{a.stage}</td>
                  <td>{a.anomaly_type || '—'}</td>
                  <td>
                    <span style={{
                      background: SEVERITY_COLOR[a.severity] + '20',
                      color: SEVERITY_COLOR[a.severity],
                      padding: '0.15rem 0.5rem', borderRadius: '0.3rem',
                      fontWeight: 700, fontSize: '0.7rem', textTransform: 'uppercase',
                    }}>{a.severity}</span>
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                    {typeof a.iso_score === 'number' ? a.iso_score.toFixed(4) : '—'}
                  </td>
                  <td>{a.detected_at ? a.detected_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                  <td>{a.notified_at ? a.notified_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}
