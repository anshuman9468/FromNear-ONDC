import json

with open('/tmp/cloudrun_logs.json') as f:
    logs = json.load(f)

for log in logs:
    payload = log.get('jsonPayload', {})
    msg = payload.get('message', '')
    if 'on_issue_status' in msg or 'on_issue' in msg or 'validation' in msg.lower():
        print(f"Timestamp: {log.get('timestamp')} | Msg: {msg}")
