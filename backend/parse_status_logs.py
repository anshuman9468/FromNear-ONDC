import json

with open('/tmp/on_status_logs.json') as f:
    logs = json.load(f)

for l in logs:
    p = l.get('jsonPayload', {})
    print(l.get('timestamp'), p.get('message'))

