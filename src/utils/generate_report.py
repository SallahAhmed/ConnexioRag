import json
import os
from datetime import datetime

def generate_html_report(trace_json_path: str, output_path: str = "rag_report.html"):
    """
    Parses a RAG trace JSON and generates a beautiful HTML dashboard.
    """
    if not os.path.exists(trace_json_path):
        print(f"Error: {trace_json_path} not found.")
        return

    with open(trace_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    steps_html = ""
    total_tokens = 0
    total_duration = 0

    for step in data.get("steps", []):
        usage = step.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        total_tokens += tokens
        total_duration += step.get("duration_ms", 0)
        
        usage_html = ""
        if usage:
            usage_html = f"""
            <div class="usage-pill">
                <span>Prompt: {usage.get('prompt_tokens')}</span>
                <span>Completion: {usage.get('completion_tokens')}</span>
                <span class="total">Total: {tokens}</span>
            </div>
            """

        steps_html += f"""
        <div class="step-card">
            <div class="step-header">
                <span class="step-name">{step['action_name']}</span>
                <span class="step-duration">{step.get('duration_ms', 0):.0f}ms</span>
            </div>
            <div class="step-body">
                <p><strong>Output:</strong> {step.get('output_summary', 'N/A')}</p>
                {usage_html}
            </div>
        </div>
        """

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Connexio RAG Trace Report</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #0f172a;
                --card: #1e293b;
                --primary: #38bdf8;
                --text: #f8fafc;
                --accent: #818cf8;
            }}
            body {{
                font-family: 'Inter', sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                padding: 40px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .container {{ max-width: 800px; width: 100%; }}
            h1 {{ font-weight: 800; font-size: 2.5rem; margin-bottom: 10px; color: var(--primary); }}
            .summary-bar {{
                display: flex;
                gap: 20px;
                margin-bottom: 40px;
                background: var(--card);
                padding: 20px;
                border-radius: 16px;
                border: 1px solid #334155;
            }}
            .stat {{ flex: 1; text-align: center; }}
            .stat-val {{ display: block; font-size: 1.5rem; font-weight: 800; color: var(--accent); }}
            .stat-label {{ font-size: 0.8rem; text-transform: uppercase; opacity: 0.6; }}
            .step-card {{
                background: var(--card);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 20px;
                border: 1px solid #334155;
                transition: transform 0.2s;
            }}
            .step-card:hover {{ transform: translateY(-4px); border-color: var(--primary); }}
            .step-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
                border-bottom: 1px solid #334155;
                padding-bottom: 12px;
            }}
            .step-name {{ font-weight: 800; font-size: 1.1rem; }}
            .step-duration {{ opacity: 0.5; font-size: 0.9rem; }}
            .usage-pill {{
                display: flex;
                gap: 12px;
                margin-top: 16px;
                font-size: 0.85rem;
            }}
            .usage-pill span {{
                background: #0f172a;
                padding: 4px 12px;
                border-radius: 20px;
                border: 1px solid #334155;
            }}
            .usage-pill .total {{ background: var(--primary); color: #000; font-weight: 800; border: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>RAG Trace Report</h1>
            <p style="opacity: 0.6">Trace ID: {data.get('trace_id')}</p>
            
            <div class="summary-bar">
                <div class="stat">
                    <span class="stat-val">{total_tokens}</span>
                    <span class="stat-label">Total Tokens</span>
                </div>
                <div class="stat">
                    <span class="stat-val">{total_duration:.0f}ms</span>
                    <span class="stat-label">Latency</span>
                </div>
                <div class="stat">
                    <span class="stat-val">{len(data.get('steps', []))}</span>
                    <span class="stat-label">Total Steps</span>
                </div>
            </div>

            {steps_html}
        </div>
    </body>
    </html>
    """

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_template)
    print(f"Report generated successfully at {output_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        generate_html_report(sys.argv[1])
    else:
        print("Usage: python generate_report.py path_to_trace.json")
