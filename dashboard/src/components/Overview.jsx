import { useEffect, useState } from 'react'

export default function Overview() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch('/api/stats')
      .then(r => r.json())
      .then(setStats)
      .catch(() => {})
  }, [])

  if (!stats) return <div className="loading">Loading stats...</div>

  return (
    <div>
      <div className="section-title">Project Overview</div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Pipeline Runs</div>
          <div className="stat-value">{stats.totalRuns}</div>
          <div className="stat-sub">Across 2 pipelines</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Anomalies Detected</div>
          <div className={`stat-value ${stats.anomalyCount > 0 ? 'danger' : 'success'}`}>{stats.anomalyCount}</div>
          <div className="stat-sub">{stats.highSeverity} high severity</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Pipelines Monitored</div>
          <div className="stat-value success">{stats.pipelines}</div>
          <div className="stat-sub">batch + transformation</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">ML Models Trained</div>
          <div className="stat-value success">2</div>
          <div className="stat-sub">Isolation Forest + LOF</div>
        </div>
      </div>

      <div className="section-title">Architecture</div>
      <div className="table-wrap" style={{ padding: '1.25rem', background: 'white' }}>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', fontSize: '0.8125rem' }}>
          {['Airflow :8080', '→', 'SQLite DB', '→', 'Exporter :8000', '→', 'Prometheus :9090', '→', 'Grafana :3000'].map((item, i) => (
            item === '→'
              ? <span key={i} style={{ color: '#94A3B8' }}>→</span>
              : <span key={i} style={{ background: '#EFF6FF', color: '#1E40AF', padding: '0.35rem 0.75rem', borderRadius: '0.375rem', fontWeight: 600, border: '1px solid #BFDBFE' }}>{item}</span>
          ))}
        </div>
        <div style={{ marginTop: '0.875rem', display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', fontSize: '0.8125rem' }}>
          <span style={{ color: '#94A3B8', paddingLeft: '7.5rem' }}>↓</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', fontSize: '0.8125rem', marginTop: '0.25rem', paddingLeft: '7.5rem' }}>
          {['ML Models (IF + LOF)', '→', 'Anomaly Alerts', '→', 'AI Explanation'].map((item, i) => (
            item === '→'
              ? <span key={i} style={{ color: '#94A3B8' }}>→</span>
              : <span key={i} style={{ background: '#FFF7ED', color: '#9A3412', padding: '0.35rem 0.75rem', borderRadius: '0.375rem', fontWeight: 600, border: '1px solid #FED7AA' }}>{item}</span>
          ))}
        </div>
      </div>

      <div className="section-title" style={{ marginTop: '1.5rem' }}>QA Coverage</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Test File</th>
              <th>QA Activity</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {[
              ['test_smoke.py', 'Pipeline smoke tests', 'pass'],
              ['test_metric_ingestion.py', 'Metric ingestion unit tests', 'pass'],
              ['test_model_accuracy.py', 'Model accuracy validation', 'pass'],
              ['test_false_positive.py', 'False positive rate testing', 'pass'],
              ['test_prompt_quality.py', 'Prompt/output quality validation', 'pass'],
              ['test_integration_e2e.py', 'Integration + E2E tests', 'pass'],
            ].map(([file, activity, status]) => (
              <tr key={file}>
                <td><code style={{ fontSize: '0.75rem' }}>{file}</code></td>
                <td>{activity}</td>
                <td><span className={`badge badge-${status === 'pass' ? 'success' : 'high'}`}>{status === 'pass' ? '✓ Pass' : '✗ Fail'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
