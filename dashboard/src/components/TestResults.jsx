import { useState } from 'react'

export default function TestResults() {
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)
  const [ran, setRan] = useState(false)

  const runTests = async () => {
    setRunning(true)
    setOutput('Running pytest... this takes ~10 seconds...\n')
    try {
      const res = await fetch('/api/tests')
      const data = await res.json()
      setOutput(data.output)
      setRan(true)
    } catch {
      setOutput('Error connecting to API server.')
    }
    setRunning(false)
  }

  const colorLine = (line) => {
    if (line.includes('PASSED')) return 'color: #4ADE80'
    if (line.includes('FAILED') || line.includes('ERROR')) return 'color: #F87171'
    if (line.includes('SKIPPED')) return 'color: #FCD34D'
    if (line.includes('passed') || line.includes('passed,')) return 'color: #4ADE80; font-weight: bold'
    if (line.includes('failed')) return 'color: #F87171; font-weight: bold'
    return ''
  }

  return (
    <div>
      <div className="test-header">
        <div className="section-title" style={{ margin: 0 }}>Test Results</div>
        <button className="run-btn" onClick={runTests} disabled={running}>
          {running ? '⏳ Running...' : '▶ Run All Tests'}
        </button>
        {ran && !running && (
          <span style={{ fontSize: '0.8rem', color: '#64748B' }}>
            {output.includes('failed') ? '❌ Some tests failed' : '✅ All tests passed'}
          </span>
        )}
      </div>

      {!ran && !running && (
        <div style={{ background: 'white', border: '1px solid #E2E8F0', borderRadius: '0.625rem', padding: '2rem', textAlign: 'center', color: '#64748B', fontSize: '0.875rem' }}>
          Click <strong>Run All Tests</strong> to execute the full test suite (41 tests across 6 files)
        </div>
      )}

      {output && (
        <div className="test-output">
          {output.split('\n').map((line, i) => (
            <span key={i} style={{ display: 'block', ...(colorLine(line) ? { cssText: colorLine(line) } : {}) }}>
              <span style={{ color: line.includes('PASSED') ? '#4ADE80' : line.includes('FAILED') || line.includes('ERROR') ? '#F87171' : line.includes('SKIPPED') ? '#FCD34D' : line.includes('passed') && !line.includes('PASSED') ? '#4ADE80' : line.includes('failed') && !line.includes('FAILED') ? '#F87171' : 'inherit' }}>
                {line}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
