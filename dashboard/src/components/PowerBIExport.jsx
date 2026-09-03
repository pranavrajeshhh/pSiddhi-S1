import { useState } from 'react'

const API = 'http://localhost:3001'

const EXPORTS = [
  { file: 'anomaly_summary.csv',   label: 'Anomaly Summary',   desc: 'One row per anomaly — pipeline, stage, severity, IF score, AI explanation' },
  { file: 'pipeline_health.csv',   label: 'Pipeline Health',   desc: 'Daily health score per pipeline — anomaly rate, avg duration, yield rate'  },
  { file: 'severity_trends.csv',   label: 'Severity Trends',   desc: 'Weekly severity counts (HIGH / MEDIUM / LOW) per pipeline'                  },
  { file: 'weekly_report.csv',     label: 'Weekly Report',     desc: 'KPI summary by week — total runs, anomalies, high-severity, anomaly rate'   },
]

export default function PowerBIExport() {
  const [exporting, setExporting] = useState(false)
  const [exported, setExported] = useState(false)
  const [output, setOutput] = useState('')
  const [error, setError] = useState('')

  const runExport = () => {
    setExporting(true)
    setError('')
    fetch(`${API}/api/export/powerbi`, { method: 'POST' })
      .then(r => r.json())
      .then(data => {
        setExporting(false)
        if (data.success) {
          setExported(true)
          setOutput(data.output || '')
        } else {
          setError(data.output || 'Export failed')
        }
      })
      .catch(() => { setExporting(false); setError('Could not reach server') })
  }

  return (
    <div>
      <div className="section-title">Power BI Export</div>
      <div style={{ fontSize: '0.78rem', color: '#64748B', marginBottom: '1.25rem' }}>
        Generate 4 CSV files from the live database, then import them into Power BI Desktop to build your reporting dashboard.
      </div>

      {/* Step 1 — Generate */}
      <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '0.625rem', padding: '1rem 1.25rem', marginBottom: '1rem' }}>
        <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: '0.5rem' }}>Step 1 — Generate CSV files</div>
        <button
          onClick={runExport}
          disabled={exporting}
          style={{
            background: exporting ? '#94A3B8' : '#1E3A5F',
            color: 'white', border: 'none', borderRadius: '0.4rem',
            padding: '0.5rem 1.25rem', cursor: exporting ? 'not-allowed' : 'pointer',
            fontWeight: 600, fontSize: '0.82rem',
          }}
        >
          {exporting ? 'Generating...' : exported ? 'Re-Generate CSVs' : 'Generate CSVs'}
        </button>
        {output && (
          <pre style={{ marginTop: '0.75rem', background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '0.4rem', padding: '0.6rem', fontSize: '0.7rem', color: '#166534', maxHeight: 100, overflow: 'auto' }}>{output}</pre>
        )}
        {error && (
          <pre style={{ marginTop: '0.75rem', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '0.4rem', padding: '0.6rem', fontSize: '0.7rem', color: '#991B1B' }}>{error}</pre>
        )}
      </div>

      {/* Step 2 — Download */}
      <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '0.625rem', padding: '1rem 1.25rem', marginBottom: '1rem' }}>
        <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: '0.75rem' }}>Step 2 — Download & import into Power BI</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {EXPORTS.map(({ file, label, desc }) => (
            <div key={file} style={{ display: 'flex', alignItems: 'center', gap: '1rem', background: 'white', border: '1px solid #E2E8F0', borderRadius: '0.5rem', padding: '0.65rem 1rem' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '0.8rem' }}>{label}</div>
                <div style={{ fontSize: '0.7rem', color: '#64748B' }}>{desc}</div>
              </div>
              <a
                href={`${API}/api/export/powerbi/${file}`}
                download={file}
                style={{
                  background: exported ? '#1E3A5F' : '#94A3B8',
                  color: 'white', borderRadius: '0.35rem',
                  padding: '0.35rem 0.9rem', fontSize: '0.75rem',
                  fontWeight: 600, textDecoration: 'none',
                  pointerEvents: exported ? 'auto' : 'none',
                  opacity: exported ? 1 : 0.5,
                }}
              >
                Download
              </a>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
