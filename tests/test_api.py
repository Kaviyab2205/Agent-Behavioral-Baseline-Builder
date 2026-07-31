import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from backend.database import Base, get_db
from backend.main import app
from backend.models import Agent, Scenario, ExecutionTrace, Baseline, BaselineFingerprint

from sqlalchemy.pool import StaticPool

# In-memory database for isolated API testing
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
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

# 1. Test Health Endpoint
def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "healthy"
    assert "timestamp" in json_data
    assert "version" in json_data

# 2. Test Agents CRUD & Validations
def test_api_agents_lifecycle(client):
    # Test valid agent creation
    payload = {
        "name": "Finance Agent",
        "system_prompt": "You answer banking queries and process balance requests.",
        "tools": ["get_account", "search_database"],
        "version": "1.0.0"
    }
    response = client.post("/api/agents", json=payload)
    assert response.status_code == 201
    agent_data = response.json()
    assert "id" in agent_data
    assert agent_data["name"] == "Finance Agent"
    assert agent_data["version"] == "1.0.0"
    agent_id = agent_data["id"]

    # Test duplicate agent creation
    response_dup = client.post("/api/agents", json=payload)
    assert response_dup.status_code == 400
    assert "already exists" in response_dup.json()["detail"]

    # Test invalid empty prompt
    payload_bad_prompt = payload.copy()
    payload_bad_prompt["name"] = "Finance Agent v2"
    payload_bad_prompt["system_prompt"] = "  "
    response_bad = client.post("/api/agents", json=payload_bad_prompt)
    assert response_bad.status_code in [400, 422]

    # Test invalid empty tools
    payload_bad_tools = payload.copy()
    payload_bad_tools["name"] = "Finance Agent v3"
    payload_bad_tools["tools"] = []
    response_bad_tools = client.post("/api/agents", json=payload_bad_tools)
    assert response_bad_tools.status_code in [400, 422]

    # Test GET agents list
    response_list = client.get("/api/agents")
    assert response_list.status_code == 200
    assert len(response_list.json()) == 1

    # Test GET agent by ID
    response_detail = client.get(f"/api/agents/{agent_id}")
    assert response_detail.status_code == 200
    assert response_detail.json()["id"] == agent_id

    # Test GET non-existent agent
    response_missing = client.get("/api/agents/agt_nonexistent")
    assert response_missing.status_code == 404

# 3. Test Scenario Generation Endpoints
def test_api_scenarios_generation(client):
    # Register Agent
    payload = {
        "name": "Ecom Agent",
        "system_prompt": "You are a shopping assistant checking order data.",
        "tools": ["retrieve_order", "search_database"],
        "version": "1.0.0"
    }
    agent_data = client.post("/api/agents", json=payload).json()
    agent_id = agent_data["id"]

    # Test scenarios generation
    gen_payload = {
        "agent_id": agent_id,
        "count": 12
    }
    response_gen = client.post("/api/scenarios/generate", json=gen_payload)
    assert response_gen.status_code == 201
    scenarios_list = response_gen.json()
    assert len(scenarios_list) == 12
    assert scenarios_list[0]["agent_id"] == agent_id

    # Test GET scenarios for agent
    response_get = client.get(f"/api/scenarios/{agent_id}")
    assert response_get.status_code == 200
    assert len(response_get.json()) == 12

    # Test generate scenarios for invalid agent ID
    gen_payload_bad = {
        "agent_id": "agt_nonexistent",
        "count": 10
    }
    response_gen_bad = client.post("/api/scenarios/generate", json=gen_payload_bad)
    assert response_gen_bad.status_code == 404

    # Test GET scenarios for invalid agent ID
    response_get_bad = client.get("/api/scenarios/agt_nonexistent")
    assert response_get_bad.status_code == 404

# 4. Test Baseline Endpoints
def test_api_baseline_workflow(client):
    # Register Agent
    payload = {
        "name": "General Agent",
        "system_prompt": "You are a helpful IT bot.",
        "tools": ["search_database", "send_email"],
        "version": "1.0.0"
    }
    agent_data = client.post("/api/agents", json=payload).json()
    agent_id = agent_data["id"]

    # Test Baseline creation BEFORE scenario generation (expect 400)
    response_bl_fail = client.post(f"/api/baseline/create/{agent_id}")
    assert response_bl_fail.status_code == 400
    assert "No scenarios found" in response_bl_fail.json()["detail"]

    # Generate 5 scenarios
    client.post("/api/scenarios/generate", json={"agent_id": agent_id, "count": 5})

    # Test Baseline creation (expect 201)
    response_bl = client.post(f"/api/baseline/create/{agent_id}")
    assert response_bl.status_code == 201
    baseline_data = response_bl.json()
    assert "id" in baseline_data
    assert baseline_data["agent_id"] == agent_id
    assert baseline_data["scenario_count"] == 5
    baseline_v_id = baseline_data["id"]
    assert baseline_v_id

    # Test GET active baseline
    response_get_bl = client.get(f"/api/baseline/{agent_id}")
    assert response_get_bl.status_code == 200
    assert response_get_bl.json()["id"] == baseline_v_id

    # Test GET baseline fingerprint
    response_fp = client.get(f"/api/baseline/{agent_id}/fingerprint")
    assert response_fp.status_code == 200
    fp_data = response_fp.json()
    assert fp_data["baseline_id"] == baseline_v_id
    assert "tool_frequency" in fp_data
    assert "latency_stats" in fp_data
    assert fp_data["success_rate"] >= 0.0

    # Test GET active baseline for non-existent agent
    response_missing = client.get("/api/baseline/agt_nonexistent")
    assert response_missing.status_code == 404

    # Test GET active baseline fingerprint for non-existent agent
    response_missing_fp = client.get("/api/baseline/agt_nonexistent/fingerprint")
    assert response_missing_fp.status_code == 404
