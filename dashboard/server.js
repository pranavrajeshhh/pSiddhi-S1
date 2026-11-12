import express from 'express'
import cors from 'cors'
import Database from 'better-sqlite3'
import { execSync, spawn } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'
import { readFileSync, existsSync } from 'fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DB_PATH = path.join(__dirname, '..', 'data', 'etl_metrics.db')
const PROJECT_ROOT = path.join(__dirname, '..')
// Prefer the project venv (Codespaces/Linux or Windows) so ML packages are found; fall back to system python.
const VENV_PY = [path.join(PROJECT_ROOT, 'venv', 'bin', 'python'), path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe')].find(existsSync)
const PY = VENV_PY ? `"${VENV_PY}"` : 'python'

const app = express()
app.use(cors())
app.use(express.json())

function getDb() {
  return new Database(DB_PATH, { readonly: true })
}

// In-memory cache for scores (cleared on server restart or ?refresh=true)
let scoresCache = null

// Stats summary
app.get('/api/stats', (req, res) => {
  const db = getDb()
  const totalRuns = db.prepare('SELECT COUNT(*) as count FROM job_runs').get().count
  const anomalyCount = db.prepare('SELECT COUNT(*) as count FROM anomaly_alerts').get().count
  const pipelines = db.prepare('SELECT COUNT(DISTINCT pipeline_name) as count FROM job_runs').get().count
  const highSeverity = db.prepare("SELECT COUNT(*) as count FROM anomaly_alerts WHERE severity='high'").get().count
  db.close()
  res.json({ totalRuns, anomalyCount, pipelines, highSeverity })
})

// Recent job runs
app.get('/api/job-runs', (req, res) => {
  const db = getDb()
  const rows = db.prepare(`
    SELECT id, pipeline_name, stage, duration_seconds,
           rows_ingested, rows_output, data_volume_mb,
           processing_time_seconds, status, is_anomaly, start_time
    FROM job_runs
    ORDER BY id DESC
  `).all()
  db.close()
  res.json(rows)
})

// Anomaly alerts joined with job_runs + normal baselines per pipeline
app.get('/api/anomalies', (req, res) => {
  const db = getDb()
  const rows = db.prepare(`
    SELECT a.id, a.pipeline_name, a.stage, a.anomaly_type,
           a.severity, a.iso_score, a.ai_explanation, a.detected_at,
           a.job_run_id, a.models_flagged, a.explanation_source,
           j.duration_seconds, j.rows_ingested, j.rows_output,
           j.data_volume_mb, j.processing_time_seconds
    FROM anomaly_alerts a
    LEFT JOIN job_runs j ON a.job_run_id = j.id
    ORDER BY a.id DESC
  `).all()

  // Normal baseline per pipeline (mean of non-anomaly records)
  const baseline = db.prepare(`
    SELECT pipeline_name,
      AVG(duration_seconds)        AS avg_duration,
      AVG(rows_ingested)           AS avg_rows_in,
      AVG(rows_output)             AS avg_rows_out,
      AVG(data_volume_mb)          AS avg_volume,
      AVG(processing_time_seconds) AS avg_proc_time
    FROM job_runs
    WHERE is_anomaly = 0
    GROUP BY pipeline_name
  `).all()

  const normalStats = {}
  for (const b of baseline) {
    normalStats[b.pipeline_name] = b
  }

  db.close()
  res.json({ alerts: rows, normalStats })
})

// Run explain.py synchronously (on-demand from UI)
app.get('/api/explain', (req, res) => {
  try {
    const output = execSync(
      `${PY} ml/explain.py`,
      { cwd: PROJECT_ROOT, timeout: 60000, encoding: 'utf8' }
    )
    res.json({ success: true, output })
  } catch (err) {
    res.json({ success: false, output: err.stdout || err.message })
  }
})

// Model scores — cached, use ?refresh=true to re-score
app.get('/api/scores', (req, res) => {
  if (scoresCache && req.query.refresh !== 'true') {
    return res.json({ success: true, data: scoresCache, cached: true })
  }
  try {
    const output = execSync(
      `${PY} ml/score_all.py`,
      { cwd: PROJECT_ROOT, timeout: 120000, encoding: 'utf8' }
    )
    scoresCache = JSON.parse(output)
    // Chain: explain → alert in background so dashboard updates automatically
    const chain = spawn(VENV_PY || 'python', ['-c',
      'import sys; sys.path.insert(0,"."); from ml.explain import generate_explanations; generate_explanations(); from ml.alert import send_alerts; send_alerts(severity_filter="high")'
    ], { cwd: PROJECT_ROOT, stdio: 'ignore', detached: true })
    chain.unref()
    res.json({ success: true, data: scoresCache, cached: false })
  } catch (err) {
    res.json({ success: false, data: [], error: err.message })
  }
})

const FILE_LABELS = {
  'test_smoke':             'Smoke Tests',
  'test_metric_ingestion':  'Metric Ingestion',
  'test_model_accuracy':    'Model Accuracy',
  'test_false_positive':    'False Positive Analysis',
  'test_integration_e2e':   'Integration & E2E',
  'test_prompt_quality':    'AI Explanation Quality',
  'test_ml_units':          'ML Unit Tests',
  'test_alert_workflow':    'Alert Workflow',
  'test_anomaly_scenarios': 'Anomaly Scenarios',
  'test_benchmark':         'FP Tuning & Benchmark',
  'test_coverage_boost':    'Coverage Boost',
}

function parseTestOutput(raw) {
  // Strip ANSI escape codes so the regex can find plain PASSED/FAILED/SKIPPED
  const output = raw.replace(/\x1b\[[0-9;]*m/g, '')
  const filesMap = {}
  for (const line of output.split(/\r?\n/)) {
    const m = line.match(/tests[/\\](\w+)\.py::(?:\w+::)?(\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)/)
    if (!m) continue
    const [, fileKey, testFn, status] = m
    if (!filesMap[fileKey]) filesMap[fileKey] = { file: fileKey, label: FILE_LABELS[fileKey] || fileKey, tests: [] }
    const label = testFn.replace(/^test_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    filesMap[fileKey].tests.push({ name: label, status })
  }
  const files = Object.keys(FILE_LABELS).filter(k => filesMap[k]).map(k => filesMap[k])
  const allTests = files.flatMap(f => f.tests)
  const summary = {
    passed:  allTests.filter(t => t.status === 'PASSED').length,
    failed:  allTests.filter(t => t.status === 'FAILED').length,
    skipped: allTests.filter(t => t.status === 'SKIPPED').length,
    total:   allTests.length,
  }
  return { files, summary }
}

// Run pytest — optional ?files=test_smoke,test_model_accuracy to run specific categories
app.get('/api/tests', (req, res) => {
  let testTarget = 'tests/'
  if (req.query.files) {
    const allowed = Object.keys(FILE_LABELS)
    const valid = req.query.files.split(',').map(f => f.trim()).filter(f => allowed.includes(f))
    if (valid.length) testTarget = valid.map(f => `tests/${f}.py`).join(' ')
  }
  try {
    const output = execSync(
      `${PY} -m pytest ${testTarget} -v --tb=short 2>&1`,
      { cwd: PROJECT_ROOT, timeout: 120000, encoding: 'utf8' }
    )
    res.json({ success: true, structured: parseTestOutput(output), output })
  } catch (err) {
    const raw = err.stdout || err.message
    res.json({ success: false, structured: parseTestOutput(raw), output: raw })
  }
})

// Power BI — run export script then serve download links
app.post('/api/export/powerbi', (req, res) => {
  let output = ''
  try {
    output = execSync(`${PY} ml/export_powerbi.py`, { cwd: PROJECT_ROOT, timeout: 30000, encoding: 'utf8' })
  } catch (err) {
    output = err.stdout || err.message
  }
  // Success = files exist on disk (don't rely on exit code)
  const exportDir = path.join(PROJECT_ROOT, 'data', 'powerbi_exports')
  const csvFiles = ['anomaly_summary.csv', 'pipeline_health.csv', 'severity_trends.csv', 'weekly_report.csv']
  const allExist = csvFiles.every(f => existsSync(path.join(exportDir, f)))
  res.json({ success: allExist, output })
})

app.get('/api/export/powerbi/:file', (req, res) => {
  const allowed = ['anomaly_summary.csv', 'pipeline_health.csv', 'severity_trends.csv', 'weekly_report.csv']
  const file = req.params.file
  if (!allowed.includes(file)) return res.status(404).json({ error: 'Not found' })
  const filePath = path.join(PROJECT_ROOT, 'data', 'powerbi_exports', file)
  if (!existsSync(filePath)) return res.status(404).json({ error: 'Run export first' })
  res.download(filePath)
})

// High-severity alert log (from ml/alert.py output)
app.get('/api/alerts/high', (req, res) => {
  const logPath = path.join(PROJECT_ROOT, 'data', 'alert_log.json')
  try {
    if (!existsSync(logPath)) return res.json([])
    res.json(JSON.parse(readFileSync(logPath, 'utf8')))
  } catch {
    res.json([])
  }
})

// Run alert workflow — routes high-severity anomalies to alert log
app.post('/api/alerts/run', (req, res) => {
  try {
    const output = execSync(
      `${PY} ml/alert.py`,
      { cwd: PROJECT_ROOT, timeout: 30000, encoding: 'utf8' }
    )
    res.json({ success: true, output })
  } catch (err) {
    res.json({ success: false, output: err.stdout || err.message })
  }
})

// Benchmark report (from ml/benchmark.py output)
app.get('/api/benchmark', (req, res) => {
  const reportPath = path.join(PROJECT_ROOT, 'data', 'benchmark_report.json')
  try {
    if (!existsSync(reportPath)) return res.json({ available: false })
    res.json({ available: true, report: JSON.parse(readFileSync(reportPath, 'utf8')) })
  } catch {
    res.json({ available: false })
  }
})

app.listen(3001, () => console.log('Server running on port 3001'))
