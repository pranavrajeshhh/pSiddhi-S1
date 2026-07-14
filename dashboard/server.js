import express from 'express'
import cors from 'cors'
import Database from 'better-sqlite3'
import { execSync, spawn } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DB_PATH = path.join(__dirname, '..', 'data', 'etl_metrics.db')
const PROJECT_ROOT = path.join(__dirname, '..')

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
    LIMIT 100
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
      'python ml/explain.py',
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
      'python ml/score_all.py',
      { cwd: PROJECT_ROOT, timeout: 120000, encoding: 'utf8' }
    )
    scoresCache = JSON.parse(output)
    // Run explain.py in background to generate AI explanations
    const exp = spawn('python', ['ml/explain.py'], {
      cwd: PROJECT_ROOT, stdio: 'ignore', detached: true
    })
    exp.unref()
    res.json({ success: true, data: scoresCache, cached: false })
  } catch (err) {
    res.json({ success: false, data: [], error: err.message })
  }
})

// Run pytest and return output
app.get('/api/tests', (req, res) => {
  try {
    const output = execSync(
      'python -m pytest tests/ -v --tb=short 2>&1',
      { cwd: PROJECT_ROOT, timeout: 60000, encoding: 'utf8' }
    )
    res.json({ success: true, output })
  } catch (err) {
    res.json({ success: false, output: err.stdout || err.message })
  }
})

app.listen(3001, () => {
  console.log('API server running on http://localhost:3001')
})
