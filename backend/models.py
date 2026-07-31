from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=False)
    tools = Column(JSON, nullable=False)  # List of strings (tool names)
    version = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    scenarios = relationship("Scenario", back_populates="agent", cascade="all, delete-orphan")
    baselines = relationship("Baseline", back_populates="agent", cascade="all, delete-orphan")
    execution_traces = relationship("ExecutionTrace", back_populates="agent", cascade="all, delete-orphan")
    production_sessions = relationship("ProductionSession", back_populates="agent", cascade="all, delete-orphan")
    anomaly_events = relationship("AnomalyEvent", back_populates="agent", cascade="all, delete-orphan")
    drift_events = relationship("DriftEvent", back_populates="agent", cascade="all, delete-orphan")


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    intent = Column(String, nullable=False)  # Information Retrieval, Data Modification, Communication
    user_request = Column(Text, nullable=False)
    expected_tool_calls = Column(JSON, nullable=False)  # List of strings
    expected_behavior = Column(Text, nullable=False)
    data_sensitivity = Column(String, nullable=False)  # Public, Internal, Restricted, PII
    difficulty = Column(String, nullable=False)  # Easy, Medium, Hard
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="scenarios")
    execution_traces = relationship("ExecutionTrace", back_populates="scenario", cascade="all, delete-orphan")


class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    session_id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=False)
    intent = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Trace details
    tool_calls = Column(JSON, nullable=False)  # List of tools called
    tool_sequence = Column(JSON, nullable=False)  # Sequence of transitions e.g. ["toolA -> toolB"]
    tool_count = Column(Integer, nullable=False)
    response_length = Column(Integer, nullable=False)
    latency_ms = Column(Float, nullable=False)
    data_access = Column(JSON, nullable=False)  # Categories of data accessed e.g. ["customer_data"]
    success = Column(Boolean, nullable=False)
    error_count = Column(Integer, nullable=False)
    profile = Column(String, default="normal")  # normal, moderate_anomaly, severe_anomaly, drift

    # Relationships
    agent = relationship("Agent", back_populates="execution_traces")
    scenario = relationship("Scenario", back_populates="execution_traces")

    # Future integration hooks for Part 2:
    # production_session = relationship("ProductionSession", back_populates="trace")
    # anomaly_event = relationship("AnomalyEvent", back_populates="trace")


class Baseline(Base):
    __tablename__ = "baselines"

    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    agent_version = Column(String, nullable=False)
    scenario_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False, default="active")  # active, inactive
    version = Column(String, nullable=False)  # v1, v2, v3...

    # Relationships
    agent = relationship("Agent", back_populates="baselines")
    fingerprint = relationship("BaselineFingerprint", uselist=False, back_populates="baseline", cascade="all, delete-orphan")

    # Future integration hooks for Part 2:
    # drift_events = relationship("DriftEvent", back_populates="baseline")


class BaselineFingerprint(Base):
    __tablename__ = "baseline_fingerprints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    baseline_id = Column(String, ForeignKey("baselines.id"), nullable=False)
    intent = Column(String, nullable=True, default=None)  # None for global baseline
    
    # Statistical baseline metrics
    tool_frequency = Column(JSON, nullable=False)  # dict: tool_name -> relative frequency (0.0 to 1.0)
    avg_response_length = Column(Float, nullable=False)
    response_length_stats = Column(JSON, nullable=False)  # dict: avg, min, max, std_dev
    tool_sequence_patterns = Column(JSON, nullable=False)  # list of dicts: pattern (e.g. "A -> B"), frequency
    tool_count_stats = Column(JSON, nullable=False)  # dict: avg, min, max, std_dev
    data_access_patterns = Column(JSON, nullable=False)  # dict: category -> frequency
    intent_distribution = Column(JSON, nullable=False)  # dict: intent -> frequency
    latency_stats = Column(JSON, nullable=False)  # dict: avg, min, max, std_dev
    error_rate = Column(Float, nullable=False)  # average errors per execution
    success_rate = Column(Float, nullable=False)  # percentage of successful runs (0.0 to 1.0)

    # Relationships
    baseline = relationship("Baseline", back_populates="fingerprint")


class ProductionSession(Base):
    __tablename__ = "production_sessions"

    session_id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_request = Column(Text, nullable=False)
    intent = Column(String, nullable=False)
    
    # Execution metrics
    tool_calls = Column(JSON, nullable=False)
    tool_sequence = Column(JSON, nullable=False)
    response_length = Column(Integer, nullable=False)
    latency_ms = Column(Float, nullable=False)
    data_access = Column(JSON, nullable=False)
    success = Column(Boolean, nullable=False)
    error_count = Column(Integer, nullable=False)
    
    # Model Metadata
    model_version = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    
    # Analysis result
    anomaly_score = Column(Float, nullable=False)
    severity = Column(String, nullable=False)  # NORMAL, WARNING, ALERT
    explanation = Column(Text, nullable=False)

    # Relationships
    agent = relationship("Agent", back_populates="production_sessions")
    anomaly_events = relationship("AnomalyEvent", back_populates="session", cascade="all, delete-orphan")


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    event_id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    session_id = Column(String, ForeignKey("production_sessions.session_id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    severity = Column(String, nullable=False)  # WARNING, ALERT, DRIFT
    anomaly_score = Column(Float, nullable=False)
    reasons = Column(JSON, nullable=False)  # List of strings
    baseline_version = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    status = Column(String, nullable=False, default="OPEN")  # OPEN, RESOLVED

    # Relationships
    agent = relationship("Agent", back_populates="anomaly_events")
    session = relationship("ProductionSession", back_populates="anomaly_events")


class DriftEvent(Base):
    __tablename__ = "drift_events"

    id = Column(String, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    baseline_id = Column(String, ForeignKey("baselines.id"), nullable=False)
    model_version = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    drift_score = Column(Float, nullable=False)
    reasons = Column(JSON, nullable=False)  # List of strings

    # Relationships
    agent = relationship("Agent", back_populates="drift_events")
    baseline = relationship("Baseline")


class MonitoringSettings(Base):
    __tablename__ = "monitoring_settings"

    id = Column(String, primary_key=True, default="default")  # "default" or agent_id
    warning_threshold = Column(Float, nullable=False, default=30.0)
    alert_threshold = Column(Float, nullable=False, default=60.0)
    drift_threshold = Column(Float, nullable=False, default=0.25)
    drift_window = Column(Integer, nullable=False, default=20)
    min_drift_sessions = Column(Integer, nullable=False, default=10)
    
    # weights for scoring
    tool_frequency_weight = Column(Float, nullable=False, default=1.0)
    sequence_weight = Column(Float, nullable=False, default=1.0)
    response_length_weight = Column(Float, nullable=False, default=1.0)
    data_access_weight = Column(Float, nullable=False, default=1.5)
    intent_weight = Column(Float, nullable=False, default=0.5)
    latency_weight = Column(Float, nullable=False, default=0.8)
    error_rate_weight = Column(Float, nullable=False, default=2.0)
