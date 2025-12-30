import base64
import json
import requests
from urllib.parse import urlencode

def encode_key(api_key):
    return "Basic " + base64.b64encode(api_key.encode()).decode()

def kebab_to_camel_case(s):
    parts = s.split('-')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])

def api_request(url, credentials, method="GET", payload=None):
    headers = {
        "Accept": "application/json",
        "Authorization": encode_key(credentials),
    }
    if payload:
        headers["Content-Type"] = "application/json"

    response = requests.request(method, url, headers=headers, data=json.dumps(payload) if payload else None)
    response.raise_for_status()
    return response.json()

def paginated_api_request(base_url, credentials, method, payload, endpoint_key, params=None):
    all_results = []
    next_token = None

    while True:
        query_params = params.copy() if params else {}
        if next_token:
            query_params["nextToken"] = next_token
        url = base_url + "?" + urlencode(query_params)
        data = api_request(url, credentials, method, payload)
        items = data.get(endpoint_key, [])
        all_results += items
        next_token = data.get("nextToken")
        if not next_token:
            break

    return all_results

def request_handler(config, endpoint, method="GET", payload=None, version="v2", params=None):
    domain = config["domain"]
    api_key = config["api_key"]
    base_url = f"https://{domain}/api/{version}/{endpoint}"
    endpoint_key = "items" if version == "v3-alpha" else kebab_to_camel_case(endpoint)
    return paginated_api_request(base_url, api_key, method, payload, endpoint_key, params)

def query(config, endpoint, params=None, version="v2"):
    return request_handler(config, endpoint, "GET", None, version, params)

def create(config, endpoint, payload, version="v2"):
    return request_handler(config, endpoint, "POST", payload, version)

def update(config, endpoint, payload, version="v2"):
    return request_handler(config, endpoint, "PATCH", payload, version)

def get_oauth_token(domain, client_id, client_secret):
    url = f"https://{domain}/api/v2/token"
    credentials = f"{client_id}:{client_secret}"
    headers = {
        "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
        "Content-Type": "application/x-www-form-urlencoded"
    }
    body = {"grant_type": "client_credentials"}
    response = requests.post(url, headers=headers, data=body)
    response.raise_for_status()
    return response.json()["access_token"]
