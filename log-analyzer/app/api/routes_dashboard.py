from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.services.storage import get_db, Incident

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(db: Session = Depends(get_db)):
    """Simple HTML dashboard to visualize incidents"""

    incidents = db.query(Incident).order_by(Incident.last_seen.desc()).limit(50).all()

    # Build severity badges based on count
    def get_severity_class(count):
        if count >= 10:
            return "critical"
        elif count >= 5:
            return "high"
        elif count >= 2:
            return "medium"
        return "low"

    html = (
        """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Log Analyzer Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                min-height: 100vh;
            }
            
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            
            .header {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 30px;
            }
            
            .header h1 {
                color: #2d3748;
                font-size: 32px;
                margin-bottom: 10px;
            }
            
            .header .stats {
                display: flex;
                gap: 30px;
                margin-top: 20px;
            }
            
            .stat {
                background: #f7fafc;
                padding: 15px 25px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }
            
            .stat-value {
                font-size: 28px;
                font-weight: bold;
                color: #2d3748;
            }
            
            .stat-label {
                font-size: 14px;
                color: #718096;
                margin-top: 5px;
            }
            
            .incidents {
                background: white;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            
            .incident {
                padding: 20px;
                border-bottom: 1px solid #e2e8f0;
                transition: background 0.2s;
            }
            
            .incident:hover {
                background: #f7fafc;
            }
            
            .incident:last-child {
                border-bottom: none;
            }
            
            .incident-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            
            .incident-title {
                display: flex;
                align-items: center;
                gap: 15px;
            }
            
            .severity-badge {
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }
            
            .severity-badge.critical {
                background: #fed7d7;
                color: #c53030;
            }
            
            .severity-badge.high {
                background: #feebc8;
                color: #c05621;
            }
            
            .severity-badge.medium {
                background: #fefcbf;
                color: #744210;
            }
            
            .severity-badge.low {
                background: #c6f6d5;
                color: #22543d;
            }
            
            .count-badge {
                background: #4299e1;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            
            .source-tag {
                background: #edf2f7;
                color: #4a5568;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            
            .timestamp {
                color: #718096;
                font-size: 13px;
            }
            
            .sample {
                background: #2d3748;
                color: #e2e8f0;
                padding: 15px;
                border-radius: 6px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                overflow-x: auto;
                white-space: pre-wrap;
                word-break: break-all;
                line-height: 1.5;
            }
            
            .signature {
                color: #718096;
                font-size: 11px;
                font-family: monospace;
                margin-top: 10px;
            }
            
            .auto-refresh {
                text-align: center;
                color: white;
                margin-top: 20px;
                font-size: 14px;
            }
            
            .empty-state {
                text-align: center;
                padding: 60px 20px;
                color: #718096;
            }
            
            .empty-state h2 {
                font-size: 24px;
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Log Analyzer Dashboard</h1>
                <p style="color: #718096; margin-top: 10px;">Real-time incident monitoring and clustering</p>
                
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">"""
        + str(len(incidents))
        + """</div>
                        <div class="stat-label">Active Incidents</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">"""
        + str(sum(inc.count for inc in incidents))
        + """</div>
                        <div class="stat-label">Total Events</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">"""
        + str(len([inc for inc in incidents if inc.count >= 5]))
        + """</div>
                        <div class="stat-label">High Frequency</div>
                    </div>
                </div>
            </div>
            
            <div class="incidents">
    """
    )

    if not incidents:
        html += """
                <div class="empty-state">
                    <h2>No incidents yet</h2>
                    <p>Start generating traffic to see incidents appear here</p>
                </div>
        """
    else:
        for inc in incidents:
            severity = get_severity_class(inc.count)
            sample = inc.sample_lines[0] if inc.sample_lines else "N/A"

            html += f"""
                <div class="incident">
                    <div class="incident-header">
                        <div class="incident-title">
                            <span class="severity-badge {severity}">{severity}</span>
                            <span class="source-tag">{inc.source}</span>
                            <span class="count-badge">{inc.count}x</span>
                        </div>
                        <div class="timestamp">
                            Last seen: {inc.last_seen.strftime('%H:%M:%S')}
                        </div>
                    </div>
                    
                    <div class="sample">{sample}</div>
                    
                    <div class="signature">
                        Signature: {inc.signature}
                    </div>
                </div>
            """

    html += """
            </div>
            
            <div class="auto-refresh">
                ⟳ Auto-refreshing every 5 seconds
            </div>
        </div>
        
        <script>
            // Auto-refresh every 5 seconds
            setTimeout(() => location.reload(), 5000);
        </script>
    </body>
    </html>
    """

    return html
