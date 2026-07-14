import { useState } from 'react'
import Overview from './components/Overview'
import PipelineRuns from './components/PipelineRuns'
import AnomalyAlerts from './components/AnomalyAlerts'
import EmbedView from './components/EmbedView'
import TestResults from './components/TestResults'
import ModelScores from './components/ModelScores'
import './App.css'

const TABS = [
  { id: 'overview',     label: '📊 Overview' },
  { id: 'runs',         label: '⚙️ Pipeline Runs' },
  { id: 'anomalies',    label: '🚨 Anomaly Alerts' },
  { id: 'modelscores',  label: '🤖 Model Scores' },
  { id: 'grafana',      label: '📈 Grafana' },
  { id: 'airflow',      label: '🔁 Airflow' },
  { id: 'tests',        label: '✅ Test Results' },
]

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
        {active === 'grafana'     && <EmbedView url="http://localhost:3000" title="Grafana Dashboards" />}
        {active === 'airflow'     && <EmbedView url="http://localhost:8080" title="Airflow Pipelines" />}
        {active === 'tests'       && <TestResults />}
      </main>
    </div>
  )
}
