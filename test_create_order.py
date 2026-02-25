import urllib.request, json
import urllib.error

# 1. Login to get token
req = urllib.request.Request(
    'http://localhost:8000/api/auth/login',
    data=b'{"username":"client1","password":"password123"}',
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access_token']

# 2. Create Order
req2 = urllib.request.Request(
    'http://localhost:8000/api/orders',
    data=b'{"pickup_address": "123 Test St", "delivery_address": "456 Main St", "package_details": {"weight": 5.0, "type": "electronics"}}',
    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
    method='POST'
)
try:
    resp2 = urllib.request.urlopen(req2)
    print(resp2.read().decode())
except urllib.error.HTTPError as e:
    print('HTTP Error', e.code, e.read().decode())
except Exception as e:
    print(e)
