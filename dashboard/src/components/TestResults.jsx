import { useState } from 'react'

const STATUS = {
  PASSED:  { color: '#16A34A', bg: '#F0FDF4', border: '#BBF7D0', label: '✓ Passed'  },
  FAILED:  { color: '#DC2626', bg: '#FEF2F2', border: '#FECACA', label: '✗ Failed'  },
  SKIPPED: { color: '#D97706', bg: '#FFFBEB', border: '#FDE68A', label: '⊘ Skipped' },
  ERROR:   { color: '#DC2626', bg: '#FEF2F2', border: '#FECACA', label: '! Error'   },
}

const CATEGORIES = [
  { key: 'test_smoke',             label: 'Smoke Tests',            icon: '🔥' },
  { key: 'test_metric_ingestion',  label: 'Metric Ingestion',       icon: '📊' },
  { key: 'test_model_accuracy',    label: 'Model Accuracy',         icon: '🤖' },
  { key: 'test_false_positive',    label: 'False Positive',         icon: '🎯' },
  { key: 'test_integration_e2e',   label: 'Integration & E2E',      icon: '🔗' },
  { key: 'test_prompt_quality',    label: 'AI Explanation Quality', icon: '💬' },
  { key: 'test_ml_units',          label: 'ML Unit Tests',          icon: '🧬' },
  { key: 'test_alert_workflow',    label: 'Alert Workflow',         icon: '🔔' },
  { key: 'test_anomaly_scenarios', label: 'Anomaly Scenarios',      icon: '⚡' },
  { key: 'test_benchmark',         label: 'FP Benchmark',           icon: '📐' },
]

const FILE_LABELS = Object.fromEntries(CATEGORIES.map(c => [c.key, c.label]))

function parseOutput(raw) {
  if (!raw) return null
  const clean = raw.replace(/\x1b\[[0-9;]*m/g, '')
  const filesMap = {}
  for (const line of clean.split(/\r?\n/)) {
    const m = line.match(/tests[/\\](\w+)\.py::(?:\w+::)?(\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)/)
    if (!m) continue
    const [, fileKey, testFn, status] = m
    if (!filesMap[fileKey]) filesMap[fileKey] = { file: fileKey, label: FILE_LABELS[fileKey] || fileKey, tests: [] }
    const label = testFn.replace(/^test_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    filesMap[fileKey].tests.push({ name: label, status })
  }
  const files = CATEGORIES.map(c => c.key).filter(k => filesMap[k]).map(k => filesMap[k])
  const allTests = files.flatMap(f => f.tests)
  return {
    files,
    summary: {
      passed:  allTests.filter(t => t.status === 'PASSED').length,
      failed:  allTests.filter(t => t.status === 'FAILED').length,
      skipped: allTests.filter(t => t.status === 'SKIPPED').length,
      total:   allTests.length,
    }
  }
}

function CountBadge({ count, status }) {
  if (!count) return null
  const s = STATUS[status]
  return (
    <span style={{ fontSize: '0.68rem', background: s.bg, color: s.color, padding: '0.1rem 0.45rem', borderRadius: '999px', fontWeight: 700 }}>
      {count} {status.toLowerCase()}
    </span>
  )
}

export default function TestResults() {
  const [rawOutput, setRawOutput] = useState(null)
  const [running, setRunning]     = useState(false)
  const [showRaw, setShowRaw]     = useState(false)
  const [selected, setSelected]   = useState(new Set(CATEGORIES.map(c => c.key)))
  // snapshot of which categories were selected when Run was last clicked
  const [ranWith, setRanWith]     = useState(null)

  const toggleCategory = (key) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  const runTests = async () => {
    const snapshot = new Set(selected)   // capture selection at click time
    setRanWith(snapshot)
    setRunning(true)
    setRawOutput(null)
    setShowRaw(false)
    const filesParam = snapshot.size === CATEGORIES.length
      ? ''
      : `?files=${[...snapshot].join(',')}`
    try {
      const res  = await fetch(`/api/tests${filesParam}`)
      const data = await res.json()
      setRawOutput(data.output || '')
    } catch {
      setRawOutput('Error connecting to API server.')
    }
    setRunning(false)
  }

  // Parse full output, then filter to only the categories that were run
  const allParsed = parseOutput(rawOutput)
  const filteredFiles = allParsed?.files.filter(f => !ranWith || ranWith.has(f.file)) ?? []
  const filteredTests = filteredFiles.flatMap(f => f.tests)
  const structured = allParsed ? {
    files: filteredFiles,
    summary: {
      passed:  filteredTests.filter(t => t.status === 'PASSED').length,
      failed:  filteredTests.filter(t => t.status === 'FAILED').length,
      skipped: filteredTests.filter(t => t.status === 'SKIPPED').length,
      total:   filteredTests.length,
    }
  } : null

  const { passed = 0, failed = 0, skipped = 0, total = 0 } = structured?.summary || {}
  const allSelected = selected.size === CATEGORIES.length

  return (
    <div>
      {/* ── Category filter chips ── */}
      <div style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 600, marginRight: '0.1rem' }}>Run:</span>
        {CATEGORIES.map(c => {
          const on = selected.has(c.key)
          return (
            <button
              key={c.key}
              onClick={() => toggleCategory(c.key)}
              style={{
                fontSize: '0.72rem', padding: '0.2rem 0.6rem',
                border: `1px solid ${on ? '#1E3A5F' : '#E2E8F0'}`,
                borderRadius: '999px', cursor: 'pointer',
                background: on ? '#1E3A5F' : 'white',
                color: on ? 'white' : '#64748B',
                fontWeight: on ? 700 : 400,
              }}
            >
              {c.icon} {c.label}
            </button>
          )
        })}
        <button
          onClick={() => setSelected(allSelected ? new Set() : new Set(CATEGORIES.map(c => c.key)))}
          style={{ fontSize: '0.68rem', color: '#64748B', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline', marginLeft: '0.1rem' }}
        >
          {allSelected ? 'Deselect all' : 'Select all'}
        </button>
      </div>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <div className="section-title" style={{ margin: 0 }}>Test Results</div>
        {structured && (
          <>
            <CountBadge count={passed}  status="PASSED"  />
            <CountBadge count={failed}  status="FAILED"  />
            <CountBadge count={skipped} status="SKIPPED" />
            <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>{total} total</span>
          </>
        )}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {rawOutput && (
            <button
              onClick={() => setShowRaw(v => !v)}
              style={{ fontSize: '0.72rem', padding: '0.3rem 0.7rem', background: 'transparent', color: '#64748B', border: '1px solid #E2E8F0', borderRadius: '0.375rem', cursor: 'pointer' }}
            >
              {showRaw ? 'Hide Raw' : 'Raw Output'}
            </button>
          )}
          <button
            onClick={runTests}
            disabled={running || selected.size === 0}
            style={{
              fontSize: '0.8rem', padding: '0.35rem 1rem', fontWeight: 600,
              background: running || selected.size === 0 ? '#E2E8F0' : '#1E3A5F',
              color: running || selected.size === 0 ? '#94A3B8' : 'white',
              border: 'none', borderRadius: '0.375rem',
              cursor: running || selected.size === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            {running
              ? '⏳ Running...'
              : allSelected
                ? '▶ Run All Tests'
                : `▶ Run ${selected.size} File${selected.size > 1 ? 's' : ''}`}
          </button>
        </div>
      </div>

      {/* ── Empty / loading states ── */}
      {!rawOutput && !running && (
        <div style={{ background: 'white', border: '1px solid #E2E8F0', borderRadius: '0.625rem', padding: '3rem', textAlign: 'center', color: '#64748B', fontSize: '0.875rem' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🧪</div>
          Select categories above, then click <strong>Run All Tests</strong> (10 files · 127 tests)
        </div>
      )}

      {running && (
        <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '0.625rem', padding: '2.5rem', textAlign: 'center', color: '#64748B', fontSize: '0.875rem' }}>
          <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>⏳</div>
          Running {ranWith && ranWith.size < CATEGORIES.length ? `${ranWith.size} test file${ranWith.size > 1 ? 's' : ''}` : 'all tests'}… ~60–90 seconds
        </div>
      )}

      {/* ── Raw output ── */}
      {showRaw && rawOutput && (
        <div style={{ background: '#0F172A', color: '#94A3B8', fontFamily: 'monospace', fontSize: '0.72rem', padding: '0.75rem 1rem', borderRadius: '0.5rem', marginBottom: '1rem', whiteSpace: 'pre-wrap', maxHeight: '18rem', overflowY: 'auto' }}>
          {rawOutput.replace(/\x1b\[[0-9;]*m/g, '')}
        </div>
      )}

      {/* ── Structured cards ── */}
      {structured && structured.files.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {structured.files.map(file => {
            const fp = file.tests.filter(t => t.status === 'PASSED').length
            const ff = file.tests.filter(t => t.status === 'FAILED').length
            const fs = file.tests.filter(t => t.status === 'SKIPPED').length
            const ok = ff === 0
            const cat = CATEGORIES.find(c => c.key === file.file)

            return (
              <div key={file.file} style={{ background: 'white', border: `1px solid ${ok ? '#E2E8F0' : '#FECACA'}`, borderRadius: '0.625rem', overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.55rem 1rem', background: ok ? '#F8FAFC' : '#FFF5F5', borderBottom: '1px solid #E2E8F0' }}>
                  <span style={{ fontSize: '1rem' }}>{cat?.icon || '🧪'}</span>
                  <span style={{ fontWeight: 700, color: '#1E3A5F', fontSize: '0.875rem' }}>{file.label}</span>
                  <span style={{ fontSize: '0.68rem', color: '#94A3B8' }}>{file.file}.py</span>
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.35rem' }}>
                    <CountBadge count={fp} status="PASSED"  />
                    <CountBadge count={ff} status="FAILED"  />
                    <CountBadge count={fs} status="SKIPPED" />
                  </div>
                </div>

                {file.tests.map((test, i) => {
                  const s = STATUS[test.status] || STATUS.ERROR
                  return (
                    <div
                      key={i}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '0.75rem',
                        padding: '0.45rem 1rem',
                        borderBottom: i < file.tests.length - 1 ? '1px solid #F1F5F9' : 'none',
                        background: test.status === 'FAILED' ? '#FFF5F5' : 'transparent',
                      }}
                    >
                      <span style={{
                        fontSize: '0.72rem', fontWeight: 700,
                        color: s.color, background: s.bg, border: `1px solid ${s.border}`,
                        padding: '0.1rem 0.5rem', borderRadius: '0.25rem',
                        minWidth: '5.5rem', textAlign: 'center', flexShrink: 0,
                      }}>
                        {s.label}
                      </span>
                      <span style={{ fontSize: '0.82rem', color: '#374151' }}>{test.name}</span>
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
