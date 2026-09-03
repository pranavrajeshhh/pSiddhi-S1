import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')

# Load .env from project root so script works both standalone and via Node.js
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key, val = key.strip(), val.strip()
            if key and not os.environ.get(key):
                os.environ[key] = val

_load_dotenv()

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

FEATURES = ['duration_seconds', 'rows_ingested', 'rows_output', 'data_volume_mb', 'processing_time_seconds']


def get_normal_stats(conn, pipeline_name):
    """Compute mean and std of each feature from non-anomaly records in same pipeline."""
    rows = conn.execute(
        """SELECT duration_seconds, rows_ingested, rows_output, data_volume_mb, processing_time_seconds
           FROM job_runs WHERE pipeline_name = ? AND is_anomaly = 0""",
        (pipeline_name,)
    ).fetchall()
    if len(rows) < 5:
        return None
    import statistics
    stats = {}
    for i, feat in enumerate(FEATURES):
        vals = [r[i] for r in rows if r[i] is not None]
        if vals:
            stats[feat] = {'mean': statistics.mean(vals), 'std': statistics.stdev(vals) if len(vals) > 1 else 0}
    return stats


def deviance_label(value, mean, std):
    if std == 0:
        return ''
    z = abs((value - mean) / std)
    direction = 'HIGHER' if value > mean else 'LOWER'
    if z > 3:
        return f'← {z:.1f}x std {direction} than normal ⚠⚠'
    if z > 2:
        return f'← {z:.1f}x std {direction} than normal ⚠'
    if z > 1:
        return f'← {z:.1f}x std {direction} than normal'
    return ''


def build_prompt(anomaly, job_run, normal_stats):
    lines = [
        "You are an ETL pipeline monitoring expert. An ML model flagged this pipeline run as anomalous.",
        "",
        f"Pipeline: {anomaly['pipeline_name']}",
        f"Stage:    {anomaly['stage']}",
        f"Anomaly Score (Isolation Forest): {anomaly['iso_score']:.4f}  (more negative = more anomalous; normal ≈ 0 to +0.1)",
        f"Flagged by: {anomaly.get('models_flagged', 'ML model')}",
        "",
    ]

    if job_run and normal_stats:
        lines.append("METRIC COMPARISON (this run vs normal range):")
        for feat in FEATURES:
            val = job_run.get(feat)
            if val is None:
                continue
            label = ''
            if feat in normal_stats:
                s = normal_stats[feat]
                label = deviance_label(val, s['mean'], s['std'])
                lines.append(f"  {feat:<32} {val:>10.2f}   (normal mean={s['mean']:.1f}, std={s['std']:.1f}) {label}")
            else:
                lines.append(f"  {feat:<32} {val:>10.2f}")
        lines.append("")

    lines += [
        "In plain English (under 80 words):",
        "1. State which metric(s) are most unusual and by how much",
        "2. What likely caused it in an ETL context",
        "3. One specific action to investigate",
        "",
        "Do NOT repeat the numbers verbatim. Explain the business meaning."
    ]
    return '\n'.join(lines)


def explain_with_groq(prompt):
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f'  [Groq error] {e}', flush=True)
        return None


def explain_with_gemini(prompt):
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception:
        return None


def fallback_explanation(anomaly, normal_stats, job_run):
    pipeline = anomaly['pipeline_name']
    stage = anomaly['stage']
    score = anomaly['iso_score']

    if job_run and normal_stats:
        worst_feat = None
        worst_z = 0
        for feat in FEATURES:
            val = job_run.get(feat)
            if val and feat in normal_stats:
                s = normal_stats[feat]
                z = abs((val - s['mean']) / s['std']) if s['std'] > 0 else 0
                if z > worst_z:
                    worst_z = z
                    worst_feat = feat
        if worst_feat:
            s = normal_stats[worst_feat]
            val = job_run[worst_feat]
            direction = 'higher' if val > s['mean'] else 'lower'
            return (f"Pipeline {pipeline} at stage '{stage}' was flagged by ML models (score: {score:.4f}). "
                    f"The metric '{worst_feat}' was {direction} than normal ({val:.1f} vs avg {s['mean']:.1f}). "
                    f"This may indicate data volume changes or processing delays. Review pipeline logs for this run.")

    templates = {
        'ml_detected': (f"ML models flagged pipeline {pipeline} at stage '{stage}' as anomalous "
                        f"(score: {score:.4f}). The Isolation Forest and/or LOF model detected statistical "
                        f"deviation from the training baseline. Review metrics for this run."),
        'unknown_anomaly': (f"Pipeline {pipeline} at stage '{stage}' exhibited unusual behaviour "
                            f"across multiple metrics. Manual review of pipeline logs recommended.")
    }
    atype = anomaly.get('anomaly_type', 'unknown_anomaly')
    return templates.get(atype, templates['unknown_anomaly'])


def generate_explanations():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Ensure columns exist
    for col in ['explanation_source', 'models_flagged']:
        try:
            conn.execute(f'ALTER TABLE anomaly_alerts ADD COLUMN {col} TEXT')
            conn.commit()
        except Exception:
            pass

    try:
        # Re-process template explanations too — upgrade to Groq/Gemini when keys available
        if GROQ_API_KEY or GEMINI_API_KEY:
            anomalies = conn.execute('''
                SELECT id, pipeline_name, stage, anomaly_type, severity, iso_score,
                       job_run_id, models_flagged
                FROM anomaly_alerts
                WHERE ai_explanation IS NULL OR ai_explanation = ''
                   OR explanation_source = 'template'
            ''').fetchall()
        else:
            anomalies = conn.execute('''
                SELECT id, pipeline_name, stage, anomaly_type, severity, iso_score,
                       job_run_id, models_flagged
                FROM anomaly_alerts
                WHERE ai_explanation IS NULL OR ai_explanation = ''
            ''').fetchall()
    except Exception:
        conn.close()
        return

    if not anomalies:
        conn.close()
        return

    print(f"Generating explanations for {len(anomalies)} anomalies...", flush=True)

    for row in anomalies:
        anomaly = dict(row)

        job_run = None
        if anomaly.get('job_run_id'):
            jr = conn.execute(
                'SELECT * FROM job_runs WHERE id = ?', (anomaly['job_run_id'],)
            ).fetchone()
            if jr:
                job_run = dict(jr)

        normal_stats = get_normal_stats(conn, anomaly['pipeline_name'])
        prompt = build_prompt(anomaly, job_run, normal_stats)

        explanation = None
        source = 'fallback'

        if GROQ_API_KEY:
            explanation = explain_with_groq(prompt)
            if explanation:
                source = 'Groq (llama-3.3-70b)'
                print(f"  [Groq] {anomaly['pipeline_name']}/{anomaly['stage']}", flush=True)

        if not explanation and GEMINI_API_KEY:
            explanation = explain_with_gemini(prompt)
            if explanation:
                source = 'Gemini'
                print(f"  [Gemini] {anomaly['pipeline_name']}/{anomaly['stage']}", flush=True)

        if not explanation:
            explanation = fallback_explanation(anomaly, normal_stats, job_run)
            source = 'template'
            print(f"  [Template] {anomaly['pipeline_name']}/{anomaly['stage']}", flush=True)

        conn.execute(
            'UPDATE anomaly_alerts SET ai_explanation = ?, explanation_source = ? WHERE id = ?',
            (explanation, source, anomaly['id'])
        )
        conn.commit()
        time.sleep(0.3)

    conn.close()
    print("Done.", flush=True)


if __name__ == '__main__':
    generate_explanations()
