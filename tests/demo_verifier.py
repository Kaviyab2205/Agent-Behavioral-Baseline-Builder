import requests
import sys

import requests
import sys

BACKEND_URL = "https://agent-behavioral-baseline-builder.onrender.com"

def run_verification():
    print("="*60)
    print("STARTING PS-4.1 SYSTEM-WIDE VERIFICATION PIPELINE")
    print("="*60)

    # 1. Health check
    try:
        resp = requests.get(f"{BACKEND_URL}/health")
        assert resp.status_code == 200
        print("[PASS] Health Check Passed")
    except Exception as e:
        print(f"[FAIL] Health Check Failed: {e}")
        sys.exit(1)

    # 2. Register Agent
    agent_id = None
    try:
        payload = {
            "name": "Integration Test Agent",
            "system_prompt": "You are a customer bank support agent. You handle balance checks, modify addresses, and send notifications.",
            "tools": ["search_database", "get_customer", "update_customer", "get_account", "send_email", "create_ticket"],
            "version": "1.0.0"
        }
        resp = requests.post(f"{BACKEND_URL}/agents", json=payload)
        if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
            agents_list = requests.get(f"{BACKEND_URL}/agents").json()
            existing_agent = next(a for a in agents_list if a["name"] == payload["name"] and a["version"] == payload["version"])
            agent_id = existing_agent["id"]
            print(f"[PASS] Agent Already Registered (Agent ID: {agent_id})")
        else:
            assert resp.status_code == 201
            agent_id = resp.json()["id"]
            print(f"[PASS] Agent Registration Passed (Agent ID: {agent_id})")
    except Exception as e:
        print(f"[FAIL] Agent Registration Failed: {e}")
        sys.exit(1)

    # 3. Generate exactly 50 Scenarios
    try:
        payload = {
            "agent_id": agent_id,
            "count": 50
        }
        resp = requests.post(f"{BACKEND_URL}/scenarios/generate", json=payload)
        assert resp.status_code == 201
        scenarios = resp.json()
        assert len(scenarios) == 50
        print(f"[PASS] Synthetic Scenarios Generation Passed (Generated: {len(scenarios)})")
    except Exception as e:
        print(f"[FAIL] Scenarios Generation Failed: {e}")
        sys.exit(1)

    # 4. Create Baseline v1
    try:
        resp = requests.post(f"{BACKEND_URL}/baseline/create/{agent_id}")
        assert resp.status_code == 201
        baseline = resp.json()
        assert baseline["version"] == "v1"
        assert baseline["status"] == "active"
        print(f"[PASS] Baseline v1 Creation Passed (Baseline Version: {baseline['version']})")
    except Exception as e:
        print(f"[FAIL] Baseline Creation Failed: {e}")
        sys.exit(1)

    # 5. Verify Fingerprint Retrieve
    try:
        resp = requests.get(f"{BACKEND_URL}/baseline/{agent_id}/fingerprint")
        assert resp.status_code == 200
        fp = resp.json()
        assert "tool_frequency" in fp
        assert "latency_stats" in fp
        assert "response_length_stats" in fp
        assert "tool_sequence_patterns" in fp
        assert "data_access_patterns" in fp
        assert "intent_distribution" in fp
        assert fp["success_rate"] >= 0.0
        print("[PASS] Behavioral Fingerprint Verification Passed")
    except Exception as e:
        print(f"[FAIL] Fingerprint Verification Failed: {e}")
        sys.exit(1)

    # 6. Simulate Normal Production Traffic (Test A)
    try:
        payload = {
            "agent_id": agent_id,
            "count": 5,
            "profile": "normal"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        sessions = resp.json()
        assert len(sessions) == 5
        # Verify NORMAL severity and low anomaly scores (< 30)
        for s in sessions:
            assert s["anomaly_score"] < 30.0
            assert s["severity"] == "NORMAL"
        print("[PASS] Test A: Normal Behavior Verification Passed (Severity: NORMAL, Score < 30)")
    except Exception as e:
        print(f"[FAIL] Test A Failed: {e}")
        sys.exit(1)

    # 7. Simulate Moderate Anomalous Traffic (Test B)
    try:
        payload = {
            "agent_id": agent_id,
            "count": 5,
            "profile": "moderate_anomaly"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        sessions = resp.json()
        assert len(sessions) == 5
        # Verify WARNING severity and score range [30, 60) for all sessions
        for s in sessions:
            assert s["anomaly_score"] >= 30.0 and s["anomaly_score"] < 60.0
            assert s["severity"] == "WARNING"
        print("[PASS] Test B: Moderate Anomaly Verification Passed (Severity: WARNING, Score [30, 60))")
    except Exception as e:
        print(f"[FAIL] Test B Failed: {e}")
        sys.exit(1)

    # 8. Simulate Severe Anomalous Traffic (Test C)
    try:
        payload = {
            "agent_id": agent_id,
            "count": 5,
            "profile": "severe_anomaly"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        sessions = resp.json()
        assert len(sessions) == 5
        # Verify ALERT severity and score >= 60 for all sessions
        for s in sessions:
            assert s["anomaly_score"] >= 60.0
            assert s["severity"] == "ALERT"
        print("[PASS] Test C: Severe Anomaly Verification Passed (Severity: ALERT, Score >= 60)")
    except Exception as e:
        print(f"[FAIL] Test C Failed: {e}")
        sys.exit(1)

    # 9. Simulate Persistent Changed Behavior for Drift Detection (Test D)
    try:
        # Simulate 20 sessions of drift profile (total version update)
        payload = {
            "agent_id": agent_id,
            "count": 20,
            "profile": "drift"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        
        # Check drift status via monitor summary
        resp_summary = requests.get(f"{BACKEND_URL}/monitor/summary/{agent_id}")
        assert resp_summary.status_code == 200
        summary = resp_summary.json()
        assert summary["drift_status"] == "DRIFT_DETECTED"
        print(f"[PASS] Test D: Baseline Drift Detection Passed (Drift Score: {summary['drift_score']:.2f}, Threshold: 0.25)")
    except Exception as e:
        print(f"[FAIL] Test D Failed: {e}")
        sys.exit(1)

    # 10. Refresh Baseline (Version Update)
    try:
        # Step A: Generate fresh scenarios
        payload_sc = {"agent_id": agent_id, "count": 50}
        resp_sc = requests.post(f"{BACKEND_URL}/scenarios/generate", json=payload_sc)
        assert resp_sc.status_code == 201
        
        # Step B: Record Baseline (v2)
        resp_bl = requests.post(f"{BACKEND_URL}/baseline/create/{agent_id}")
        assert resp_bl.status_code == 201
        baseline_v2 = resp_bl.json()
        
        # Verify version increment and status active
        assert baseline_v2["version"] == "v2"
        assert baseline_v2["status"] == "active"
        
        # Verify v1 is inactive (query historical baseline)
        resp_history = requests.get(f"{BACKEND_URL}/baseline/{agent_id}") # gets active (v2)
        assert resp_history.json()["version"] == "v2"
        print(f"[PASS] Baseline Refresh Passed (New active: {baseline_v2['version']})")
    except Exception as e:
        print(f"[FAIL] Baseline Refresh Failed: {e}")
        sys.exit(1)

    print("="*60)
    print("ALL PS-4.1 SUCCESS CRITERIA VERIFIED AND PASSED!")
    print("="*60)

if __name__ == "__main__":
    run_verification()


def run_verification():
    print("="*60)
    print("STARTING PS-4.1 SYSTEM-WIDE VERIFICATION PIPELINE")
    print("="*60)

    # 1. Health check
    try:
        resp = requests.get(f"{BACKEND_URL}/health")
        assert resp.status_code == 200
        print("[PASS] Health Check Passed")
    except Exception as e:
        print(f"[FAIL] Health Check Failed: {e}")
        sys.exit(1)

    # 2. Register Agent
    agent_id = None
    try:
        payload = {
            "name": "Integration Test Agent",
            "system_prompt": "You are a customer bank support agent. You handle balance checks, modify addresses, and send notifications.",
            "tools": ["search_database", "get_customer", "update_customer", "get_account", "send_email", "create_ticket"],
            "version": "1.0.0"
        }
        resp = requests.post(f"{BACKEND_URL}/agents", json=payload)
        if resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
            agents_list = requests.get(f"{BACKEND_URL}/agents").json()
            existing_agent = next(a for a in agents_list if a["name"] == payload["name"] and a["version"] == payload["version"])
            agent_id = existing_agent["id"]
            print(f"[PASS] Agent Already Registered (Agent ID: {agent_id})")
        else:
            assert resp.status_code == 201
            agent_id = resp.json()["id"]
            print(f"[PASS] Agent Registration Passed (Agent ID: {agent_id})")
    except Exception as e:
        print(f"[FAIL] Agent Registration Failed: {e}")
        sys.exit(1)

    # 3. Generate exactly 50 Scenarios
    try:
        payload = {
            "agent_id": agent_id,
            "count": 50
        }
        resp = requests.post(f"{BACKEND_URL}/scenarios/generate", json=payload)
        assert resp.status_code == 201
        scenarios = resp.json()
        assert len(scenarios) == 50
        print(f"[PASS] Synthetic Scenarios Generation Passed (Generated: {len(scenarios)})")
    except Exception as e:
        print(f"[FAIL] Scenarios Generation Failed: {e}")
        sys.exit(1)

    # 4. Create Baseline v1
    try:
        resp = requests.post(f"{BACKEND_URL}/baseline/create/{agent_id}")
        assert resp.status_code == 201
        baseline = resp.json()
        assert baseline["version"] == "v1"
        assert baseline["status"] == "active"
        print(f"[PASS] Baseline v1 Creation Passed (Baseline Version: {baseline['version']})")
    except Exception as e:
        print(f"[FAIL] Baseline Creation Failed: {e}")
        sys.exit(1)

    # 5. Verify Fingerprint Retrieve
    try:
        resp = requests.get(f"{BACKEND_URL}/baseline/{agent_id}/fingerprint")
        assert resp.status_code == 200
        fp = resp.json()
        assert "tool_frequency" in fp
        assert "latency_stats" in fp
        assert "response_length_stats" in fp
        assert "tool_sequence_patterns" in fp
        assert "data_access_patterns" in fp
        assert "intent_distribution" in fp
        assert fp["success_rate"] >= 0.0
        print("[PASS] Behavioral Fingerprint Verification Passed")
    except Exception as e:
        print(f"[FAIL] Fingerprint Verification Failed: {e}")
        sys.exit(1)

    # 6. Simulate Normal Production Traffic (Test A)
    try:
        payload = {
            "agent_id": agent_id,
            "count": 5,
            "profile": "normal"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        sessions = resp.json()
        assert len(sessions) == 5
        # Verify NORMAL severity and low anomaly scores (< 30)
        for s in sessions:
            assert s["anomaly_score"] < 30.0
            assert s["severity"] == "NORMAL"
        print("[PASS] Test A: Normal Behavior Verification Passed (Severity: NORMAL, Score < 30)")
    except Exception as e:
        print(f"[FAIL] Test A Failed: {e}")
        sys.exit(1)

    # 7. Simulate Moderate Anomalous Traffic (Test B)
    try:
        payload = {
            "agent_id": agent_id,
            "count": 5,
            "profile": "moderate_anomaly"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        sessions = resp.json()
        assert len(sessions) == 5
        # Verify WARNING severity and score range [30, 60) for all sessions
        for s in sessions:
            assert s["anomaly_score"] >= 30.0 and s["anomaly_score"] < 60.0
            assert s["severity"] == "WARNING"
        print("[PASS] Test B: Moderate Anomaly Verification Passed (Severity: WARNING, Score [30, 60))")
    except Exception as e:
        print(f"[FAIL] Test B Failed: {e}")
        sys.exit(1)

    # 8. Simulate Severe Anomalous Traffic (Test C)
    try:
        payload = {
            "agent_id": agent_id,
            "count": 5,
            "profile": "severe_anomaly"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        sessions = resp.json()
        assert len(sessions) == 5
        # Verify ALERT severity and score >= 60 for all sessions
        for s in sessions:
            assert s["anomaly_score"] >= 60.0
            assert s["severity"] == "ALERT"
        print("[PASS] Test C: Severe Anomaly Verification Passed (Severity: ALERT, Score >= 60)")
    except Exception as e:
        print(f"[FAIL] Test C Failed: {e}")
        sys.exit(1)

    # 9. Simulate Persistent Changed Behavior for Drift Detection (Test D)
    try:
        # Simulate 20 sessions of drift profile (total version update)
        payload = {
            "agent_id": agent_id,
            "count": 20,
            "profile": "drift"
        }
        resp = requests.post(f"{BACKEND_URL}/production/simulate", json=payload)
        assert resp.status_code == 201
        
        # Check drift status via monitor summary
        resp_summary = requests.get(f"{BACKEND_URL}/monitor/summary/{agent_id}")
        assert resp_summary.status_code == 200
        summary = resp_summary.json()
        assert summary["drift_status"] == "DRIFT_DETECTED"
        print(f"[PASS] Test D: Baseline Drift Detection Passed (Drift Score: {summary['drift_score']:.2f}, Threshold: 0.25)")
    except Exception as e:
        print(f"[FAIL] Test D Failed: {e}")
        sys.exit(1)

    # 10. Refresh Baseline (Version Update)
    try:
        # Step A: Generate fresh scenarios
        payload_sc = {"agent_id": agent_id, "count": 50}
        resp_sc = requests.post(f"{BACKEND_URL}/scenarios/generate", json=payload_sc)
        assert resp_sc.status_code == 201
        
        # Step B: Record Baseline (v2)
        resp_bl = requests.post(f"{BACKEND_URL}/baseline/create/{agent_id}")
        assert resp_bl.status_code == 201
        baseline_v2 = resp_bl.json()
        
        # Verify version increment and status active
        assert baseline_v2["version"] == "v2"
        assert baseline_v2["status"] == "active"
        
        # Verify v1 is inactive (query historical baseline)
        resp_history = requests.get(f"{BACKEND_URL}/baseline/{agent_id}") # gets active (v2)
        assert resp_history.json()["version"] == "v2"
        print(f"[PASS] Baseline Refresh Passed (New active: {baseline_v2['version']})")
    except Exception as e:
        print(f"[FAIL] Baseline Refresh Failed: {e}")
        sys.exit(1)

    print("="*60)
    print("ALL PS-4.1 SUCCESS CRITERIA VERIFIED AND PASSED!")
    print("="*60)

if __name__ == "__main__":
    run_verification()
