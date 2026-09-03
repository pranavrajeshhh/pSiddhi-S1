import { useEffect, useState, useMemo } from 'react'

const COLS = [
  { key: 'id',                    label: '#',           numeric: true  },
  { key: 'pipeline_name',         label: 'Pipeline',    numeric: false },
  { key: 'stage',                 label: 'Stage',       numeric: false },
  { key: 'duration_seconds',      label: 'Duration (s)',numeric: true  },
  { key: 'rows_ingested',         label: 'Rows In',     numeric: true  },
  { key: 'rows_output',           label: 'Rows Out',    numeric: true  },
  { key: 'data_volume_mb',        label: 'Volume (MB)', numeric: true  },
  { key: 'status',                label: 'Status',      numeric: false },
  { key: 'is_anomaly',            label: 'Anomaly',     numeric: false },
]

export default function PipelineRuns() {
  const [runs, setRuns]               = useState(null)
  const [search, setSearch]           = useState('')
  const [anomalyFilter, setAnomalyFilter] = useState('all')
  const [sortKey, setSortKey]         = useState('id')
  const [sortDir, setSortDir]         = useState('desc')

  useEffect(() => {
    const load = () => fetch('/api/job-runs').then(r => r.json()).then(setRuns).catch(() => {})
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [])

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const filtered = useMemo(() => {
    if (!runs) return []
    let rows = runs
    if (search.trim()) {
      rows = rows.filter(r => String(r.id) === search.trim())
    }
    if (anomalyFilter === 'anomaly') rows = rows.filter(r => r.is_anomaly)
    if (anomalyFilter === 'normal')  rows = rows.filter(r => !r.is_anomaly)

    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? ''
      const bv = b[sortKey] ?? ''
      let cmp = 0
      if (typeof av === 'number' && typeof bv === 'number') {
        cmp = av - bv
      } else {
        cmp = String(av).localeCompare(String(bv))
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [runs, search, anomalyFilter, sortKey, sortDir])

  if (!runs) return <div className="loading">Loading pipeline runs...</div>

  const anomalyCount = runs.filter(r => r.is_anomaly).length

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span style={{ color: '#CBD5E1', marginLeft: '0.2rem', fontSize: '0.65rem' }}>⇅</span>
    return <span style={{ color: '#1E3A5F', marginLeft: '0.2rem', fontSize: '0.65rem' }}>{sortDir === 'asc' ? '▲' : '▼'}</span>
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <div className="section-title" style={{ margin: 0 }}>Pipeline Runs</div>
        <span className="badge badge-anomaly">{anomalyCount} anomalies</span>
        <span style={{ fontSize: '0.72rem', color: '#94A3B8' }}>{runs.length} total records</span>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="number"
            placeholder="Go to run #..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '0.35rem 0.625rem', border: '1px solid #E2E8F0', borderRadius: '0.375rem', color: '#374151', width: '160px' }}
          />
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
              {COLS.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}
                >
                  {col.label}<SortIcon col={col.key} />
                </th>
              ))}
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
