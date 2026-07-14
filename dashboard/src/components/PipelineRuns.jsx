import { useEffect, useState } from 'react'

export default function PipelineRuns() {
  const [runs, setRuns] = useState(null)
  const [pipeline, setPipeline] = useState('all')
  const [anomalyFilter, setAnomalyFilter] = useState('all')

  useEffect(() => {
    fetch('/api/job-runs')
      .then(r => r.json())
      .then(setRuns)
      .catch(() => {})
  }, [])

  if (!runs) return <div className="loading">Loading pipeline runs...</div>

  let filtered = runs
  if (pipeline !== 'all') filtered = filtered.filter(r => r.pipeline_name.includes(pipeline))
  if (anomalyFilter === 'anomaly') filtered = filtered.filter(r => r.is_anomaly)
  if (anomalyFilter === 'normal') filtered = filtered.filter(r => !r.is_anomaly)

  const anomalyCount = runs.filter(r => r.is_anomaly).length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div className="section-title" style={{ margin: 0 }}>Pipeline Runs</div>
          <span className="badge badge-anomaly">{anomalyCount} anomalies</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <select
            value={pipeline}
            onChange={e => setPipeline(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.625rem', border: '1px solid #E2E8F0', borderRadius: '0.375rem', color: '#374151' }}
          >
            <option value="all">All Pipelines</option>
            <option value="batch">Batch Ingestion</option>
            <option value="transformation">Transformation</option>
          </select>
          <select
            value={anomalyFilter}
            onChange={e => setAnomalyFilter(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.625rem', border: '1px solid #E2E8F0', borderRadius: '0.375rem', color: '#374151' }}
          >
            <option value="all">All Records</option>
            <option value="anomaly">Anomalies Only</option>
            <option value="normal">Normal Only</option>
          </select>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Pipeline</th>
              <th>Stage</th>
              <th>Duration (s)</th>
              <th>Rows In</th>
              <th>Rows Out</th>
              <th>Volume (MB)</th>
              <th>Status</th>
              <th>Anomaly</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id} style={r.is_anomaly ? { background: '#FFF5F5' } : {}}>
                <td style={{ color: '#94A3B8', fontSize: '0.72rem' }}>{r.id}</td>
                <td style={{ fontWeight: 600, color: '#1E3A5F', fontSize: '0.75rem' }}>{r.pipeline_name}</td>
                <td>{r.stage}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{r.duration_seconds?.toFixed(1)}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{r.rows_ingested?.toLocaleString()}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{r.rows_output?.toLocaleString()}</td>
                <td style={{ fontVariantNumeric: 'tabular-nums' }}>{r.data_volume_mb?.toFixed(1)}</td>
                <td><span className="badge badge-success">{r.status}</span></td>
                <td>{r.is_anomaly ? <span className="badge badge-anomaly">⚠ Yes</span> : <span style={{ color: '#94A3B8', fontSize: '0.72rem' }}>—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#94A3B8' }}>
        Showing {filtered.length} of {runs.length} runs
      </div>
    </div>
  )
}
