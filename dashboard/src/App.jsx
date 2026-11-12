import { useState } from 'react'
import Overview from './components/Overview'
import PipelineRuns from './components/PipelineRuns'
import AnomalyAlerts from './components/AnomalyAlerts'
import EmbedView from './components/EmbedView'
import TestResults from './components/TestResults'
import ModelScores from './components/ModelScores'
import AlertWorkflow from './components/AlertWorkflow'
import PowerBIExport from './components/PowerBIExport'
import './App.css'

const TABS = [
  { id: 'overview',     label: 'Overview' },
  { id: 'runs',         label: 'Pipeline Runs' },
  { id: 'anomalies',    label: 'Anomaly Alerts' },
  { id: 'modelscores',  label: 'Model Scores' },
  { id: 'alerts',       label: 'Alert Workflow' },
  { id: 'powerbi',      label: 'Power BI Export' },
  { id: 'grafana',      label: 'Grafana' },
  { id: 'airflow',      label: 'Airflow' },
  { id: 'tests',        label: 'Test Results' },
]

// In Codespaces the browser reaches services at <name>-<port>.<domain>, not localhost.
function svcUrl(port) {
  const h = window.location.hostname
  if (h.includes('.app.github.dev') || h.includes('.githubpreview.dev')) {
    return `https://${h.replace(/-\d+\./, `-${port}.`)}`
  }
  return `http://localhost:${port}`
}

export default function App() {
  const [active, setActive] = useState('overview')

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <span className="brand-tag">S1-D-03</span>
          <span className="brand-title">pSiddhi — ML Anomaly Detection</span>
        </div>
        <div className="header-right">EMP-2025-P499 · Pranav Rajesh</div>
      </header>

      <nav className="tab-nav">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-btn${active === tab.id ? ' active' : ''}`}
            onClick={() => setActive(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="content">
        {active === 'overview'    && <Overview />}
        {active === 'runs'        && <PipelineRuns />}
        {active === 'anomalies'   && <AnomalyAlerts />}
        {active === 'modelscores' && <ModelScores />}
        {active === 'alerts'      && <AlertWorkflow />}
        {active === 'powerbi'     && <PowerBIExport />}
        {active === 'grafana'     && <EmbedView url={svcUrl(3000)} title="Grafana Dashboards" />}
        {active === 'airflow'     && <EmbedView url={svcUrl(8080)} title="Airflow Pipelines" />}
        {active === 'tests'       && <TestResults />}
      </main>
    </div>
  )
}
