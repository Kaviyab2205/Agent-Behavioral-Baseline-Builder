from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime

# Agent Schemas
class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="The name of the agent")
    system_prompt: str = Field(..., min_length=5, description="The system instruction for the agent")
    tools: List[str] = Field(..., min_items=1, description="List of tools available to the agent")
    version: str = Field(default="1.0.0", description="Semantic version of the agent configuration")

class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    system_prompt: str
    tools: List[str]
    version: str
    created_at: datetime

# Scenario Schemas
class ScenarioGenerateRequest(BaseModel):
    agent_id: str = Field(..., description="The ID of the agent to generate scenarios for")
    count: int = Field(default=50, ge=1, le=100, description="Number of synthetic scenarios to generate")

class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    intent: str
    user_request: str
    expected_tool_calls: List[str]
    expected_behavior: str
    data_sensitivity: str
    difficulty: str
    created_at: datetime

# Execution Trace Schemas
class ExecutionTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    agent_id: str
    scenario_id: str
    intent: str
    timestamp: datetime
    tool_calls: List[str]
    tool_sequence: List[str]
    tool_count: int
    response_length: int
    latency_ms: float
    data_access: List[str]
    success: bool
    error_count: int
    profile: str

# Baseline Schemas
class BaselineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    agent_version: str
    scenario_count: int
    created_at: datetime
    status: str
    version: str

# Fingerprint Schemas
class FingerprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    baseline_id: str
    tool_frequency: Dict[str, float]
    avg_response_length: float
    response_length_stats: Dict[str, float]
    tool_sequence_patterns: Dict[str, float]
    tool_count_stats: Dict[str, float]
    data_access_patterns: Dict[str, float]
    intent_distribution: Dict[str, float]
    latency_stats: Dict[str, float]
    error_rate: float
    success_rate: float

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str

# Production Simulator Schemas
class ProductionSimulateRequest(BaseModel):
    agent_id: str = Field(..., description="The ID of the agent to run simulation for")
    count: int = Field(default=10, ge=1, le=100, description="Number of production sessions to simulate")
    profile: str = Field(default="normal", description="Behavior profile: normal, moderate_anomaly, severe_anomaly, drift")

# Production Session Schemas
class ProductionSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    agent_id: str
    timestamp: datetime
    user_request: str
    intent: str
    tool_calls: List[str]
    tool_sequence: List[str]
    response_length: int
    latency_ms: float
    data_access: List[str]
    success: bool
    error_count: int
    model_version: str
    prompt_version: str
    anomaly_score: float
    severity: str
    explanation: str

# Anomaly Event Schemas
class AnomalyEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    agent_id: str
    session_id: str
    timestamp: datetime
    severity: str
    anomaly_score: float
    reasons: List[str]
    baseline_version: str
    model_version: str
    prompt_version: str
    status: str

# Monitoring Settings Schemas
class MonitoringSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    warning_threshold: float
    alert_threshold: float
    drift_threshold: float
    drift_window: int
    min_drift_sessions: int
    
    # weights
    tool_frequency_weight: float
    sequence_weight: float
    response_length_weight: float
    data_access_weight: float
    intent_weight: float
    latency_weight: float
    error_rate_weight: float

class MonitoringSettingsUpdate(BaseModel):
    warning_threshold: Optional[float] = Field(None, ge=0.0, le=100.0)
    alert_threshold: Optional[float] = Field(None, ge=0.0, le=100.0)
    drift_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    drift_window: Optional[int] = Field(None, ge=5, le=100)
    min_drift_sessions: Optional[int] = Field(None, ge=2, le=100)
    
    # weights
    tool_frequency_weight: Optional[float] = Field(None, ge=0.0)
    sequence_weight: Optional[float] = Field(None, ge=0.0)
    response_length_weight: Optional[float] = Field(None, ge=0.0)
    data_access_weight: Optional[float] = Field(None, ge=0.0)
    intent_weight: Optional[float] = Field(None, ge=0.0)
    latency_weight: Optional[float] = Field(None, ge=0.0)
    error_rate_weight: Optional[float] = Field(None, ge=0.0)

# Monitoring Dashboard Summary Schemas
class MonitorSummaryResponse(BaseModel):
    total_sessions: int
    normal_count: int
    warning_count: int
    alert_count: int
    avg_anomaly_score: float
    avg_latency: float
    avg_response_length: float
    error_rate: float
    drift_status: str
    drift_score: float
    drift_threshold: float
    reasons: List[str]
