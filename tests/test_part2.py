import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.models import Agent, Scenario, Baseline, BaselineFingerprint, ProductionSession, AnomalyEvent, MonitoringSettings
from backend.services.baseline_recorder import BaselineRecorder
from backend.services.scenario_generator import ScenarioGenerator
from backend.services.production_simulator import ProductionSimulator
from backend.services.drift_detector import DriftDetector

# Isolated test DB with StaticPool for Part 2 testing
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="client")
def client_fixture():
    Base.metadata.create_all(bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

# Setup agent & baseline helper for tests
def _setup_agent_and_baseline(db):
    agent = Agent(
        id="agt_p2_test",
        name="Security Agent",
        system_prompt="You protect corporate systems.",
        tools=["search_database", "send_email", "get_account"],
        version="1.0"
    )
    db.add(agent)
    db.commit()

    # Generate and save scenarios
    scenarios = ScenarioGenerator.generate_scenarios(
        agent_id=agent.id,
        system_prompt=agent.system_prompt,
        tools=agent.tools,
        count=15
    )
    for sc in scenarios:
        db_sc = Scenario(
            id=sc["id"],
            agent_id=sc["agent_id"],
            intent=sc["intent"],
            user_request=sc["user_request"],
            expected_tool_calls=sc["expected_tool_calls"],
            expected_behavior=sc["expected_behavior"],
            data_sensitivity=sc["data_sensitivity"],
            difficulty=sc["difficulty"]
        )
        db.add(db_sc)
    db.commit()

    # Record baseline v1
    BaselineRecorder.create_baseline(db, agent.id)

# 1. Test Settings Configuration Endpoints
def test_api_settings(client):
    # Fetch default settings
    response = client.get("/api/settings")
    assert response.status_code == 200
    settings = response.json()
    assert settings["warning_threshold"] == 30.0
    assert settings["alert_threshold"] == 60.0

    # Modify thresholds
    payload = {"warning_threshold": 40.0, "alert_threshold": 75.0}
    response_update = client.post("/api/settings", json=payload)
    assert response_update.status_code == 200
    updated_settings = response_update.json()
    assert updated_settings["warning_threshold"] == 40.0
    assert updated_settings["alert_threshold"] == 75.0

    # Validate incorrect values (warning >= alert)
    response_bad = client.post("/api/settings", json={"warning_threshold": 80.0, "alert_threshold": 70.0})
    assert response_bad.status_code == 400

# 2. Test Anomaly Scores: NORMAL, WARNING, ALERT
def test_production_traffic_scoring(client):
    db = TestingSessionLocal()
    Base.metadata.create_all(bind=engine)
    _setup_agent_and_baseline(db)
    db.close()

    # Simulate Normal Traffic
    resp_normal = client.post("/api/production/simulate", json={"agent_id": "agt_p2_test", "count": 3, "profile": "normal"})
    assert resp_normal.status_code == 201
    normal_sessions = resp_normal.json()
    print("NORMAL SESSIONS SCORES:", [s["anomaly_score"] for s in normal_sessions])
    print("NORMAL SESSIONS EXPLANATIONS:", [s["explanation"] for s in normal_sessions])
    assert len(normal_sessions) == 3
    # All/most normal runs should be NORMAL severity with score < warning_threshold
    assert all(s["anomaly_score"] < 30.0 for s in normal_sessions)
    assert all(s["severity"] == "NORMAL" for s in normal_sessions)

    # Simulate Moderate Anomaly
    resp_mod = client.post("/api/production/simulate", json={"agent_id": "agt_p2_test", "count": 3, "profile": "moderate_anomaly"})
    assert resp_mod.status_code == 201
    mod_sessions = resp_mod.json()
    print("MODERATE SESSIONS SCORES:", [s["anomaly_score"] for s in mod_sessions])
    print("MODERATE SESSIONS EXPLANATIONS:", [s["explanation"] for s in mod_sessions])
    assert len(mod_sessions) == 3
    assert all(s["anomaly_score"] >= 30.0 and s["anomaly_score"] < 60.0 for s in mod_sessions)
    assert all(s["severity"] == "WARNING" for s in mod_sessions)

    # Simulate Severe Anomaly
    resp_severe = client.post("/api/production/simulate", json={"agent_id": "agt_p2_test", "count": 2, "profile": "severe_anomaly"})
    assert resp_severe.status_code == 201
    severe_sessions = resp_severe.json()
    assert len(severe_sessions) == 2
    # At least some severe sessions should trigger ALERT (score >= 60)
    assert any(s["anomaly_score"] >= 60.0 for s in severe_sessions)
    assert any(s["severity"] == "ALERT" for s in severe_sessions)

# 3. Test Alerts logging and resolving
def test_anomaly_alerts_lifecycle(client):
    db = TestingSessionLocal()
    Base.metadata.create_all(bind=engine)
    _setup_agent_and_baseline(db)
    db.close()

    # Trigger some severe anomalies to log alerts
    client.post("/api/production/simulate", json={"agent_id": "agt_p2_test", "count": 5, "profile": "severe_anomaly"})

    # Fetch alerts
    response_alerts = client.get("/api/alerts")
    assert response_alerts.status_code == 200
    alerts = response_alerts.json()
    assert len(alerts) > 0
    assert alerts[0]["status"] == "OPEN"
    target_event_id = alerts[0]["event_id"]

    # Mark as resolved
    response_res = client.post(f"/api/alerts/{target_event_id}/resolve")
    assert response_res.status_code == 200
    assert response_res.json()["status"] == "RESOLVED"

# 4. Test Sliding-Window Drift Detection & Baseline Refresh
def test_drift_and_baseline_refresh(client):
    db = TestingSessionLocal()
    Base.metadata.create_all(bind=engine)
    _setup_agent_and_baseline(db)
    
    # Assert initial state has no production sessions, so drift status is INSUFFICIENT_DATA
    drift_res_init = DriftDetector.detect_drift(db, "agt_p2_test")
    assert drift_res_init["status"] == "INSUFFICIENT_DATA"

    # Simulate 5 Normal traffic sessions (still less than min 10 sessions required)
    ProductionSimulator.simulate_production_traffic(db, "agt_p2_test", count=5, profile="normal")
    drift_res_insufficient = DriftDetector.detect_drift(db, "agt_p2_test")
    assert drift_res_insufficient["status"] == "INSUFFICIENT_DATA"

    # Simulate 10 more Normal sessions (total 15 - meets threshold)
    ProductionSimulator.simulate_production_traffic(db, "agt_p2_test", count=10, profile="normal")
    
    # Normal traffic should result in NORMAL status (no drift)
    drift_res_normal = DriftDetector.detect_drift(db, "agt_p2_test")
    assert drift_res_normal["status"] == "NORMAL"
    assert drift_res_normal["drift_detected"] is False

    # Simulate 1 outlier Severe Anomaly session
    ProductionSimulator.simulate_production_traffic(db, "agt_p2_test", count=1, profile="severe_anomaly")
    
    # Assert that one outlier anomaly does NOT trigger drift
    drift_res_outlier = DriftDetector.detect_drift(db, "agt_p2_test")
    assert drift_res_outlier["drift_detected"] is False
    assert drift_res_outlier["status"] == "NORMAL"

    # Simulate 20 sessions of Drift traffic (Version update)
    ProductionSimulator.simulate_production_traffic(db, "agt_p2_test", count=20, profile="drift")
    
    # Slide window evaluates recent 20 sessions. 
    # Since they are all drift sessions, it should detect DRIFT_DETECTED!
    drift_res_drifted = DriftDetector.detect_drift(db, "agt_p2_test")
    assert drift_res_drifted["drift_detected"] is True
    assert drift_res_drifted["status"] == "DRIFT_DETECTED"
    assert len(drift_res_drifted["reasons"]) >= 1

    # Verify Baseline refresh workflow
    # Before refresh, baseline version is v1
    active_bl = db.query(Baseline).filter(Baseline.agent_id == "agt_p2_test", Baseline.status == "active").first()
    assert active_bl.version == "v1"
    old_bl_id = active_bl.id

    # Trigger Refresh (via API endpoints simulating UI click)
    # Generate fresh scenarios, and run baseline
    client.post("/api/scenarios/generate", json={"agent_id": "agt_p2_test", "count": 15})
    response_refresh = client.post(f"/api/baseline/create/agt_p2_test")
    assert response_refresh.status_code == 201
    
    # Verify new baseline is v2
    new_bl = response_refresh.json()
    assert new_bl["version"] == "v2"
    assert new_bl["status"] == "active"

    # Verify old baseline remains in history as inactive
    old_bl = db.query(Baseline).filter(Baseline.id == old_bl_id).first()
    db.refresh(old_bl)
    assert old_bl.status == "inactive"
    db.close()
