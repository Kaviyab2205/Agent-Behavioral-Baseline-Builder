import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import Agent, Scenario, ExecutionTrace, Baseline, BaselineFingerprint
from backend.services.scenario_generator import ScenarioGenerator
from backend.services.agent_simulator import AgentSimulator
from backend.services.behavior_analyzer import BehaviorAnalyzer
from backend.services.baseline_recorder import BaselineRecorder

# Test DB setup
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="db_session")
def db_session_fixture():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

# 1. Test Agent Creation & Database Persistence
def test_agent_creation(db_session):
    agent = Agent(
        id="agt_test1",
        name="Support Agent",
        system_prompt="You are a helpful customer support assistant.",
        tools=["search_database", "send_email"],
        version="1.0.0"
    )
    db_session.add(agent)
    db_session.commit()
    
    saved_agent = db_session.query(Agent).filter(Agent.id == "agt_test1").first()
    assert saved_agent is not None
    assert saved_agent.name == "Support Agent"
    assert "send_email" in saved_agent.tools
    assert saved_agent.version == "1.0.0"

# 2. Test Scenario Generation: Count & Intent Categories
def test_scenario_generation(db_session):
    agent_id = "agt_test2"
    system_prompt = "You are a customer banking assistant."
    tools = ["get_account", "update_customer", "send_email"]
    
    # Generate scenarios
    scenarios_data = ScenarioGenerator.generate_scenarios(
        agent_id=agent_id,
        system_prompt=system_prompt,
        tools=tools,
        count=50
    )
    
    # Test count
    assert len(scenarios_data) == 50
    
    # Test intent distribution completeness
    intents = [s["intent"] for s in scenarios_data]
    assert "Information Retrieval" in intents
    assert "Data Modification" in intents
    assert "Communication" in intents
    
    # Test scenario detail presence
    first_scn = scenarios_data[0]
    assert "id" in first_scn
    assert first_scn["agent_id"] == agent_id
    assert len(first_scn["expected_tool_calls"]) >= 1
    assert "user_request" in first_scn
    assert first_scn["difficulty"] in ["Easy", "Medium", "Hard"]
    assert first_scn["data_sensitivity"] in ["Public", "Internal", "Restricted", "PII"]

# 3. Test Agent Simulator (Normal Profile Trace Output)
def test_agent_simulator_normal():
    agent_id = "agt_test3"
    scenario = {
        "id": "scn_001",
        "intent": "Information Retrieval",
        "expected_tool_calls": ["get_customer", "search_database"],
        "data_sensitivity": "Internal",
        "difficulty": "Easy"
    }
    
    trace = AgentSimulator.simulate_execution(agent_id, scenario, profile="normal")
    
    assert trace["session_id"].startswith("sess_")
    assert trace["agent_id"] == agent_id
    assert trace["scenario_id"] == "scn_001"
    assert trace["intent"] == "Information Retrieval"
    assert trace["profile"] == "normal"
    assert trace["success"] in [True, False]
    assert isinstance(trace["tool_calls"], list)
    assert trace["latency_ms"] >= 200.0 and trace["latency_ms"] <= 600.0
    assert trace["response_length"] >= 100 and trace["response_length"] <= 300

# 4. Test Agent Simulator (Anomaly Profiles Variance)
def test_agent_simulator_anomalies():
    agent_id = "agt_test4"
    scenario = {
        "id": "scn_002",
        "intent": "Communication",
        "expected_tool_calls": ["send_email"],
        "data_sensitivity": "PII",
        "difficulty": "Medium"
    }
    
    # Severe Anomaly execution check
    trace_severe = AgentSimulator.simulate_execution(agent_id, scenario, profile="severe_anomaly")
    assert trace_severe["profile"] == "severe_anomaly"
    # Severe anomalies should access sensitive credentials_data or loop
    assert "credentials_data" in trace_severe["data_access"]
    assert trace_severe["error_count"] >= 0 # could fail fast or loop errors

    # Drift execution check
    trace_drift = AgentSimulator.simulate_execution(agent_id, scenario, profile="drift")
    assert "search_database" in trace_drift["tool_calls"] # systematically prepended

# 5. Test Behavior Analyzer calculation
def test_behavior_analyzer():
    # Construct mock traces
    traces = [
        {
            "tool_calls": ["search_database", "get_customer"],
            "response_length": 200,
            "latency_ms": 300.0,
            "data_access": ["customer_data", "system_index"],
            "intent": "Information Retrieval",
            "success": True,
            "error_count": 0
        },
        {
            "tool_calls": ["update_customer", "send_email"],
            "response_length": 400,
            "latency_ms": 500.0,
            "data_access": ["customer_data", "communication_log"],
            "intent": "Data Modification",
            "success": True,
            "error_count": 0
        },
        {
            "tool_calls": ["search_database"],
            "response_length": 150,
            "latency_ms": 250.0,
            "data_access": ["system_index"],
            "intent": "Information Retrieval",
            "success": False,
            "error_count": 1
        }
    ]
    
    fingerprint = BehaviorAnalyzer.calculate_fingerprint(traces)
    
    # Assert statistical math correctness
    assert fingerprint["success_rate"] == pytest.approx(2/3)
    assert fingerprint["error_rate"] == pytest.approx(1/3)
    assert fingerprint["avg_response_length"] == pytest.approx((200 + 400 + 150) / 3)
    
    # Tool call count stats
    # counts are [2, 2, 1] -> avg = 1.67, min = 1, max = 2
    assert fingerprint["tool_count_stats"]["avg"] == pytest.approx(1.67, rel=1e-2)
    assert fingerprint["tool_count_stats"]["min"] == 1.0
    assert fingerprint["tool_count_stats"]["max"] == 2.0
    
    # Latency: [300.0, 500.0, 250.0] -> avg = 350.0, min = 250.0, max = 500.0
    assert fingerprint["latency_stats"]["avg"] == 350.0
    assert fingerprint["latency_stats"]["min"] == 250.0
    assert fingerprint["latency_stats"]["max"] == 500.0
    
    # Tool call relative frequency
    # total calls = 2 + 2 + 1 = 5
    # search_database = 2/5 = 0.40, get_customer = 1/5 = 0.20, update_customer = 0.20, send_email = 0.20
    assert fingerprint["tool_frequency"]["search_database"] == 0.40
    assert fingerprint["tool_frequency"]["get_customer"] == 0.20
    
    # Sequence transitions
    # Traces:
    # 1: search_database -> get_customer
    # 2: update_customer -> send_email
    # 3: search_database -> [END] (single call)
    # total transitions = 3
    assert fingerprint["tool_sequence_patterns"]["search_database -> get_customer"] == pytest.approx(1/3)

# 6. Test Baseline Recorder (E2E Service execution & DB persistence)
def test_baseline_recorder(db_session):
    # Setup agent
    agent = Agent(
        id="agt_rec_test",
        name="Logistics Agent",
        system_prompt="You manage e-commerce orders.",
        tools=["search_database", "retrieve_order", "send_email"],
        version="1.0"
    )
    db_session.add(agent)
    db_session.commit()
    
    # Generate scenarios and save to DB
    scenarios_data = ScenarioGenerator.generate_scenarios(
        agent_id=agent.id,
        system_prompt=agent.system_prompt,
        tools=agent.tools,
        count=10 # smaller count for fast test
    )
    for sc in scenarios_data:
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
        db_session.add(db_sc)
    db_session.commit()
    
    # Create Baseline
    baseline = BaselineRecorder.create_baseline(db_session, agent.id)
    
    # Verify DB persistence of baseline
    assert baseline.id.startswith("bl_")
    assert baseline.agent_id == agent.id
    assert baseline.scenario_count == 10
    assert baseline.version == "v1"
    assert baseline.status == "active"
    
    # Verify fingerprint link
    assert baseline.fingerprint is not None
    assert isinstance(baseline.fingerprint.tool_frequency, dict)
    assert baseline.fingerprint.success_rate >= 0.0
    
    # Check traces got recorded in execution_traces table
    trace_count = db_session.query(ExecutionTrace).filter(ExecutionTrace.agent_id == agent.id).count()
    assert trace_count == 10
    
    # Test version incrementing by building v2 baseline
    baseline_v2 = BaselineRecorder.create_baseline(db_session, agent.id)
    assert baseline_v2.version == "v2"
    assert baseline_v2.status == "active"
    
    # Confirm v1 got deactivated
    baseline_v1 = db_session.query(Baseline).filter(Baseline.id == baseline.id).first()
    assert baseline_v1.status == "inactive"
