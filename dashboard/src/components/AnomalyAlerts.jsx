import { useEffect, useState } from 'react'

function SourceBadge({ source }) {
  if (!source) return null
  const config = {
    'Groq (llama-3.3-70b)': { bg: '#F0FDF4', color: '#166534', label: 'Groq AI' },
    'Gemini':               { bg: '#EFF6FF', color: '#1D4ED8', label: 'Gemini AI' },
    'template':             { bg: '#F8FAFC', color: '#64748B', label: 'Template' },
  }
  const c = config[source] || { bg: '#F8FAFC', color: '#64748B', label: source }
  return (
    <span style={{ fontSize: '0.65rem', background: c.bg, color: c.color, padding: '0.1rem 0.5rem', borderRadius: '999px', fontWeight: 600 }}>
      {c.label}
    </span>
  )
}

function fmt(val, unit) {
  if (val == null) return '—'
  if (unit === 's') return `${val.toFixed(1)}s`
  if (unit === 'MB') return `${val.toFixed(1)} MB`
  if (unit === 'rows') return val.toLocaleString()
  return val.toFixed(4)
}

function deviation(val, avg) {
  if (!avg || avg === 0) return null
  const ratio = val / avg
  const pct = ((ratio - 1) * 100).toFixed(0)
  const dir = val > avg ? '↑' : '↓'
  const isHigh = Math.abs(ratio - 1) > 0.5
  return { ratio, pct, dir, isHigh }
}

function MetricComparison({ a, normal }) {
  if (!a.duration_seconds && !a.rows_ingested) return null

  const metrics = [
    { key: 'duration_seconds',        label: 'Duration',     unit: 's',    val: a.duration_seconds,        avg: normal?.avg_duration  },
    { key: 'rows_ingested',           label: 'Rows In',      unit: 'rows', val: a.rows_ingested,           avg: normal?.avg_rows_in   },
    { key: 'rows_output',             label: 'Rows Out',     unit: 'rows', val: a.rows_output,             avg: normal?.avg_rows_out  },
    { key: 'data_volume_mb',          label: 'Volume',       unit: 'MB',   val: a.data_volume_mb,          avg: normal?.avg_volume    },
    { key: 'processing_time_seconds', label: 'Proc Time',    unit: 's',    val: a.processing_time_seconds, avg: normal?.avg_proc_time },
  ]

  return (
    <div style={{ margin: '0.75rem 0', overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
        <thead>
          <tr style={{ background: '#F8FAFC' }}>
            <th style={{ padding: '0.3rem 0.6rem', textAlign: 'left', color: '#64748B', fontWeight: 600, borderBottom: '1px solid #E2E8F0' }}>Metric</th>
            <th style={{ padding: '0.3rem 0.6rem', textAlign: 'right', color: '#64748B', fontWeight: 600, borderBottom: '1px solid #E2E8F0' }}>This Run</th>
            <th style={{ padding: '0.3rem 0.6rem', textAlign: 'right', color: '#64748B', fontWeight: 600, borderBottom: '1px solid #E2E8F0' }}>Normal Avg</th>
            <th style={{ padding: '0.3rem 0.6rem', textAlign: 'left', color: '#64748B', fontWeight: 600, borderBottom: '1px solid #E2E8F0' }}>Compared to Normal</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map(m => {
            const dev = m.avg != null ? deviation(m.val, m.avg) : null
            const rowBg = dev?.isHigh ? (m.val > m.avg ? '#FFF5F5' : '#FFFBEB') : 'transparent'
            return (
              <tr key={m.key} style={{ background: rowBg, borderBottom: '1px solid #F1F5F9' }}>
                <td style={{ padding: '0.3rem 0.6rem', color: '#374151', fontWeight: 500 }}>{m.label}</td>
                <td style={{ padding: '0.3rem 0.6rem', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 700, color: dev?.isHigh ? (m.val > m.avg ? '#B91C1C' : '#92400E') : '#1E3A5F' }}>
                  {fmt(m.val, m.unit)}
                </td>
                <td style={{ padding: '0.3rem 0.6rem', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#64748B' }}>
                  {m.avg != null ? fmt(m.avg, m.unit) : '—'}
                </td>
                <td style={{ padding: '0.3rem 0.6rem' }}>
                  {dev ? (
                    <span style={{
                      fontSize: '0.7rem', fontWeight: 600,
                      color: dev.isHigh ? (m.val > m.avg ? '#B91C1C' : '#92400E') : '#22C55E',
                      background: dev.isHigh ? (m.val > m.avg ? '#FEE2E2' : '#FEF3C7') : '#F0FDF4',
                      padding: '0.1rem 0.4rem', borderRadius: '999px'
                    }}>
                      {dev.dir} {Math.abs(dev.pct)}%{dev.isHigh ? ' !' : ''}
                    </span>
                  ) : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function AnomalyAlerts() {
  const [data, setData] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [genLog, setGenLog] = useState('')

  const loadAlerts = () => {
    fetch('/api/anomalies')
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
  }

  useEffect(() => {
    loadAlerts()
    const id = setInterval(loadAlerts, 30000)
    return () => clearInterval(id)
  }, [])

  const generateExplanations = async () => {
    setGenerating(true)
    setGenLog('Calling Groq AI for each anomaly...')
    try {
      const res = await fetch('/api/explain')
      const d = await res.json()
      setGenLog(d.output || 'All explanations already generated.')
      loadAlerts()
    } catch {
      setGenLog('Error calling /api/explain')
    }
    setGenerating(false)
  }

  if (!data) return <div className="loading">Loading anomaly alerts...</div>

  const { alerts = [], normalStats = {} } = data
  const withoutExplanation = alerts.filter(a => !a.ai_explanation).length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <div className="section-title" style={{ margin: 0 }}>Anomaly Alerts</div>
        <span className="badge badge-high">{alerts.length} detected</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {withoutExplanation > 0 && (
            <span style={{ fontSize: '0.72rem', color: '#94A3B8' }}>{withoutExplanation} need explanation</span>
          )}
          <button
            onClick={generateExplanations}
            disabled={generating}
            style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem', background: generating ? '#E2E8F0' : '#1E3A5F', color: generating ? '#94A3B8' : 'white', border: 'none', borderRadius: '0.375rem', cursor: generating ? 'not-allowed' : 'pointer', fontWeight: 600 }}
          >
            {generating ? 'Generating...' : 'Generate Explanations'}
          </button>
        </div>
      </div>

      {genLog && (
        <div style={{ background: '#0F172A', color: '#94A3B8', fontFamily: 'monospace', fontSize: '0.72rem', padding: '0.75rem 1rem', borderRadius: '0.5rem', marginBottom: '1rem', whiteSpace: 'pre-wrap' }}>
          {genLog}
        </div>
      )}

      {alerts.length === 0 && (
        <div className="empty">No anomalies detected yet. Open the <strong>Model Scores</strong> tab first.</div>
      )}

      <div className="anomaly-list">
        {alerts.map(a => {
          const normal = normalStats[a.pipeline_name]
          return (
            <div key={a.id} className={`anomaly-card ${a.severity}`}>
              <div className="anomaly-header" style={{ flexWrap: 'wrap', gap: '0.35rem' }}>
                <span className="anomaly-pipeline">{a.pipeline_name}</span>
                <span className="anomaly-stage">/ {a.stage}</span>
                {a.job_run_id && (
                  <span style={{ fontSize: '0.7rem', color: '#94A3B8', background: '#F1F5F9', padding: '0.1rem 0.4rem', borderRadius: '0.25rem', fontVariantNumeric: 'tabular-nums' }}>
                    Run #{a.job_run_id}
                  </span>
                )}
                <span className={`badge badge-${a.severity}`}>{a.severity}</span>
                {a.models_flagged && (
                  <span style={{ fontSize: '0.65rem', background: '#FEF3C7', color: '#92400E', padding: '0.1rem 0.4rem', borderRadius: '999px', fontWeight: 600 }}>
                    {a.models_flagged}
                  </span>
                )}
                <SourceBadge source={a.explanation_source} />
              </div>

              <MetricComparison a={a} normal={normal} />

              {a.ai_explanation ? (
                <div className="anomaly-explanation">
                  {a.ai_explanation}
                </div>
              ) : (
                <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontStyle: 'italic', marginTop: '0.4rem' }}>
                  No explanation yet — click "Generate Explanations" above
                </div>
              )}
              <div className="anomaly-time">Detected at {a.detected_at}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
