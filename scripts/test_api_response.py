import urllib.request
import json

# 1. Login
req = urllib.request.Request(
    "http://localhost:8000/api/auth/login",
    data=json.dumps({"email": "investigator@finspectra.dev", "password": "finspectra_inv"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        token = data["access_token"]
        print("Login SUCCESS. Token:", token[:20])

        # 2. Fetch Alerts
        req_alerts = urllib.request.Request(
            "http://localhost:8000/api/alerts?page_size=50",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req_alerts) as resp_alerts:
            alerts_data = json.loads(resp_alerts.read().decode("utf-8"))
            print("Alerts count:", len(alerts_data.get("items", [])))
            for a in alerts_data.get("items", [])[:3]:
                print("  Alert:", a.get("id"), "Priority:", a.get("initial_priority"), "Score:", a.get("anomaly_score"))

        # 3. Fetch Dashboard Summary
        req_summary = urllib.request.Request(
            "http://localhost:8000/api/dashboard/summary",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req_summary) as resp_summary:
            summary_data = json.loads(resp_summary.read().decode("utf-8"))
            print("Summary Metrics:", summary_data.get("metrics"))

except Exception as e:
    print("API error:", e)
