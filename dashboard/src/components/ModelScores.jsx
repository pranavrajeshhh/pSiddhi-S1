import { useEffect, useState } from 'react'

function ScoreBar({ value }) {
  if (value === null || value === undefined) return <span style={{ color: '#CBD5E1' }}>—</span>
  const pct = Math.max(0, Math.min(100, (value + 0.5) * 100))
  const color = value < -0.3 ? '#EF4444' : value < -0.1 ? '#F59E0B' : '#22C55E'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div style={{ flex: 1, height: '6px', background: '#E2E8F0', borderRadius: '3px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '3px' }} />
      </div>
      <span style={{ fontSize: '0.65rem', fontVariantNumeric: 'tabular-nums', color, minWidth: '3rem', textAlign: 'right', fontWeight: 600 }}>
        {value.toFixed(4)}
      </span>
    </div>
  )
}

function SeverityBadge({ severity }) {
  if (!severity) return null
  const colors = { high: '#FEE2E2', medium: '#FEF3C7', low: '#DCFCE7' }
  const text = { high: '#B91C1C', medium: '#92400E', low: '#166534' }
  return (
    <span style={{ background: colors[severity], color: text[severity], fontSize: '0.65rem', fontWeight: 700, padding: '0.15rem 0.45rem', borderRadius: '999px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
      {severity}
    </span>
  )
}

export default function ModelScores() {
  const [state, setState] = useState({ loading: true, data: [], error: null, cached: false })
  const [filter, setFilter] = useState('all')
  const [pipeline, setPipeline] = useState('all')

  const loadScores = (refresh = false) => {
    setState(s => ({ ...s, loading: true }))
    fetch(`/api/scores${refresh ? '?refresh=true' : ''}`)
      .then(r => r.json())
      .then(res => setState({ loading: false, data: res.data || [], error: res.error || null, cached: res.cached }))
      .catch(e => setState({ loading: false, data: [], error: e.message, cached: false }))
  }

  useEffect(() => { loadScores() }, [])

  if (state.loading) return <div className="loading">Scoring all records... please wait...</div>
  if (state.error) return <div className="empty">Error: {state.error}</div>

  let rows = state.data
  if (filter === 'anomaly') rows = rows.filter(r => r.ml_is_anomaly)
  if (filter === 'normal') rows = rows.filter(r => r.ml_is_anomaly === false)
  if (pipeline !== 'all') rows = rows.filter(r => r.pipeline_name.includes(pipeline))

  const anomalyCount = state.data.filter(r => r.ml_is_anomaly).length
  const normalCount = state.data.filter(r => r.ml_is_anomaly === false).length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <div className="section-title" style={{ margin: 0 }}>Model Scores</div>
        {state.cached && <span style={{ fontSize: '0.72rem', color: '#94A3B8' }}>cached</span>}
        <button
          onClick={() => loadScores(true)}
          disabled={state.loading}
          style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem', background: state.loading ? '#E2E8F0' : '#1E3A5F', color: state.loading ? '#94A3B8' : 'white', border: 'none', borderRadius: '0.375rem', cursor: state.loading ? 'not-allowed' : 'pointer', fontWeight: 600 }}
        >
          {state.loading ? '⏳ Scoring...' : '↻ Refresh Scores'}
        </button>

        <div style={{ display: 'flex', gap: '0.5rem', marginLeft: 'auto', flexWrap: 'wrap' }}>
          <select value={pipeline} onChange={e => setPipeline(e.target.value)}
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.6rem', border: '1px solid #E2E8F0', borderRadius: '0.375rem', color: '#374151' }}>
            <option value="all">All Pipelines</option>
            <option value="batch">Batch Ingestion</option>
            <option value="transformation">Transformation</option>
          </select>
          <select value={filter} onChange={e => setFilter(e.target.value)}
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.6rem', border: '1px solid #E2E8F0', borderRadius: '0.375rem', color: '#374151' }}>
            <option value="all">All Records</option>
            <option value="anomaly">Anomalies Only</option>
            <option value="normal">Normal Only</option>
          </select>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <div style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '0.5rem', padding: '0.75rem 1.25rem', display: 'flex', gap: '0.5rem', alignItems: 'baseline' }}>
          <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#166534' }}>{normalCount}</span>
          <span style={{ fontSize: '0.78rem', color: '#166534' }}>Normal</span>
        </div>
        <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '0.5rem', padding: '0.75rem 1.25rem', display: 'flex', gap: '0.5rem', alignItems: 'baseline' }}>
          <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#B91C1C' }}>{anomalyCount}</span>
          <span style={{ fontSize: '0.78rem', color: '#B91C1C' }}>Anomalies</span>
        </div>
        <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '0.5rem', padding: '0.75rem 1.25rem', display: 'flex', gap: '0.5rem', alignItems: 'baseline' }}>
          <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1E3A5F' }}>{state.data.length}</span>
          <span style={{ fontSize: '0.78rem', color: '#64748B' }}>Total</span>
        </div>
        <div style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: '0.5rem', padding: '0.75rem 1.25rem', display: 'flex', gap: '0.5rem', alignItems: 'baseline' }}>
          <span style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1D4ED8' }}>{((anomalyCount / state.data.length) * 100).toFixed(1)}%</span>
          <span style={{ fontSize: '0.78rem', color: '#1D4ED8' }}>Anomaly Rate</span>
        </div>
      </div>

      <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '0.5rem', padding: '0.75rem 1rem', marginBottom: '1rem', fontSize: '0.78rem', color: '#475569' }}>
        <strong style={{ color: '#1E3A5F' }}>How models work:</strong> Each record is scored by two models.{' '}
        <strong>Isolation Forest</strong> gives a score from ~−0.5 (most anomalous) to ~+0.5 (most normal) — more negative = more isolated from the crowd.{' '}
        <strong>LOF</strong> compares local density of neighbors — 1 = anomaly, 0 = normal.{' '}
        A record is flagged if <em>either</em> model says anomaly (OR logic).{' '}
        Severity: score &lt; −0.3 = high, &lt; −0.1 = medium, else low.
      </div>

      <div className="table-wrap">
        <table className="table-compact" style={{ minWidth: '960px' }}>
          <thead>
            <tr>
              <th>#</th>
              <th>Pipeline</th>
              <th>Stage</th>
              <th>Duration (s)</th>
              <th>Rows In</th>
              <th>Rows Out</th>
              <th style={{ minWidth: '140px' }}>IF Score</th>
              <th>LOF</th>
              <th>IF Flag</th>
              <th>Models Flagged</th>
              <th>Result</th>
              <th>Severity</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} style={{ background: r.ml_is_anomaly ? '#FFF5F5' : 'transparent' }}>
                <td style={{ color: '#94A3B8' }}>{r.id}</td>
                <td style={{ fontWeight: 600, color: '#1E3A5F' }}>
                  {r.pipeline_name.replace('_01', '')}
                </td>
                <td>{r.stage}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{r.duration_seconds?.toFixed(1)}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{r.rows_ingested?.toLocaleString()}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{r.rows_output?.toLocaleString()}</td>
                <td style={{ minWidth: '140px' }}>
                  <ScoreBar value={r.iso_score} />
                </td>
                <td style={{ textAlign: 'center' }}>
                  {r.lof_pred === null ? '—' : r.lof_pred === 1
                    ? <span style={{ color: '#EF4444', fontWeight: 700 }}>1</span>
                    : <span style={{ color: '#22C55E' }}>0</span>}
                </td>
                <td style={{ textAlign: 'center' }}>
                  {r.iso_pred === null ? '—' : r.iso_pred === -1
                    ? <span style={{ color: '#EF4444', fontWeight: 700 }}>-1</span>
                    : <span style={{ color: '#22C55E' }}>+1</span>}
                </td>
                <td style={{ color: r.models_flagged?.length ? '#B91C1C' : '#64748B' }}>
                  {r.models_flagged?.length ? r.models_flagged.join(', ') : '—'}
                </td>
                <td>
                  {r.ml_is_anomaly === null
                    ? <span style={{ color: '#94A3B8' }}>no model</span>
                    : r.ml_is_anomaly
                      ? <span className="badge badge-anomaly">⚠ Anomaly</span>
                      : <span className="badge badge-success">Normal</span>}
                </td>
                <td><SeverityBadge severity={r.ml_severity} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#94A3B8' }}>
        Showing {rows.length} of {state.data.length} records
      </div>
    </div>
  )
}
