import json
import urllib.request

payload = {
    'customer_email': 'customer@example.com',
    'subject': 'Order delayed',
    'body': 'My order has not arrived and I am very frustrated. Can you help me with shipping status?'
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    'http://127.0.0.1:8011/process-email',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST',
)

with urllib.request.urlopen(req, timeout=30) as resp:
    print(resp.read().decode('utf-8'))
