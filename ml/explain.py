import sqlite3
import os
import json
import time

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'etl_metrics.db')

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')


def build_prompt(anomaly):
    return f"""You are an ETL pipeline monitoring expert. Analyze this anomaly and provide a concise root-cause explanation.

Pipeline: {anomaly['pipeline_name']}
Stage: {anomaly['stage']}
Anomaly Type: {anomaly['anomaly_type']}
Severity: {anomaly['severity']}
Anomaly Score: {anomaly['iso_score']}

Provide:
1. What likely went wrong
2. Business impact
3. Recommended action

Keep response under 100 words, plain English."""


def explain_with_gemini(prompt):
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return None


def explain_with_groq(prompt):
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return None


def fallback_explanation(anomaly):
    templates = {
        'duration_spike': f"Pipeline {anomaly['pipeline_name']} at stage '{anomaly['stage']}' completed with an abnormally long duration. This may indicate upstream data source slowness, resource contention, or a logic bottleneck. Recommend investigating infrastructure load and query performance.",
        'volume_drop': f"Pipeline {anomaly['pipeline_name']} at stage '{anomaly['stage']}' produced significantly fewer output records than expected. This is consistent with an upstream data gap, failed extraction, or transformation filter issue. Immediate pipeline inspection recommended.",
        'processing_time_deviation': f"Pipeline {anomaly['pipeline_name']} at stage '{anomaly['stage']}' showed abnormal processing time. This may be caused by increased data complexity, resource limitations, or inefficient transformation logic.",
        'unknown_anomaly': f"Pipeline {anomaly['pipeline_name']} at stage '{anomaly['stage']}' exhibited unusual behaviour across multiple metrics. Manual review of pipeline logs recommended."
    }
    anomaly_type = anomaly.get('anomaly_type', 'unknown_anomaly')
    for key in templates:
        if key in anomaly_type:
            return templates[key]
    return templates['unknown_anomaly']


def generate_explanations():
    conn = sqlite3.connect(DB_PATH)

    try:
        anomalies = conn.execute('''
            SELECT id, pipeline_name, stage, anomaly_type, severity, iso_score
            FROM anomaly_alerts
            WHERE ai_explanation IS NULL OR ai_explanation = ''
        ''').fetchall()
    except Exception:
        print("No anomaly_alerts table found. Run detect.py first.")
        conn.close()
        return

    if not anomalies:
        print("No unexplained anomalies found.")
        conn.close()
        return

    print(f"Generating explanations for {len(anomalies)} anomalies...")

    for row in anomalies:
        anomaly = {
            'id': row[0],
            'pipeline_name': row[1],
            'stage': row[2],
            'anomaly_type': row[3],
            'severity': row[4],
            'iso_score': row[5]
        }

        prompt = build_prompt(anomaly)
        explanation = None

        if GROQ_API_KEY:
            explanation = explain_with_groq(prompt)
            if explanation:
                print(f"  [Groq] {anomaly['pipeline_name']}/{anomaly['stage']}: explained")

        if not explanation and GEMINI_API_KEY:
            explanation = explain_with_gemini(prompt)
            if explanation:
                print(f"  [Gemini] {anomaly['pipeline_name']}/{anomaly['stage']}: explained")

        if not explanation:
            explanation = fallback_explanation(anomaly)
            print(f"  [Fallback] {anomaly['pipeline_name']}/{anomaly['stage']}: using template")

        conn.execute('''
            UPDATE anomaly_alerts SET ai_explanation = ? WHERE id = ?
        ''', (explanation, anomaly['id']))
        conn.commit()
        time.sleep(0.5)

    conn.close()
    print("All explanations generated.")


if __name__ == '__main__':
    generate_explanations()
