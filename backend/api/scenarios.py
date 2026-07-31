from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.models import Agent, Scenario
from backend.schemas import ScenarioGenerateRequest, ScenarioResponse
from backend.services.scenario_generator import ScenarioGenerator

router = APIRouter()

@router.post("/scenarios/generate", response_model=List[ScenarioResponse], status_code=status.HTTP_201_CREATED)
def generate_scenarios(payload: ScenarioGenerateRequest, db: Session = Depends(get_db)):
    # Fetch Agent
    agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID {payload.agent_id} not found.")

    # Validate count
    if payload.count <= 0 or payload.count > 100:
        raise HTTPException(status_code=400, detail="Invalid scenario count. Must be between 1 and 100.")

    # Delete existing scenarios for this agent to start fresh
    db.query(Scenario).filter(Scenario.agent_id == payload.agent_id).delete()
    db.commit()

    # Generate Scenarios
    generated_data = ScenarioGenerator.generate_scenarios(
        agent_id=agent.id,
        system_prompt=agent.system_prompt,
        tools=agent.tools,
        count=payload.count
    )

    # Save to Database
    db_scenarios = []
    for sc in generated_data:
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
        db_scenarios.append(db_sc)
    
    db.commit()
    
    # Refresh to fetch auto-fields / relationships
    for db_sc in db_scenarios:
        db.refresh(db_sc)

    return db_scenarios

@router.get("/scenarios/{agent_id}", response_model=List[ScenarioResponse])
def get_scenarios_by_agent(agent_id: str, db: Session = Depends(get_db)):
    # Check if agent exists
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found.")
    
    scenarios = db.query(Scenario).filter(Scenario.agent_id == agent_id).all()
    return scenarios
