from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from backend.database import get_db
from backend.models import Agent
from backend.schemas import AgentCreate, AgentResponse

router = APIRouter()

@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(agent_data: AgentCreate, db: Session = Depends(get_db)):
    # Validations
    if not agent_data.system_prompt.strip():
        raise HTTPException(status_code=400, detail="System prompt cannot be empty.")
    if not agent_data.tools:
        raise HTTPException(status_code=400, detail="Tool list cannot be empty. Specify at least one tool.")
    
    # Check for duplicate name + version
    existing_agent = db.query(Agent).filter(
        Agent.name == agent_data.name,
        Agent.version == agent_data.version
    ).first()
    if existing_agent:
        raise HTTPException(
            status_code=400, 
            detail=f"Agent '{agent_data.name}' with version '{agent_data.version}' already exists."
        )

    # Create new agent
    agent_id = f"agt_{uuid.uuid4().hex[:8]}"
    db_agent = Agent(
        id=agent_id,
        name=agent_data.name,
        system_prompt=agent_data.system_prompt,
        tools=agent_data.tools,
        version=agent_data.version
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@router.get("/agents", response_model=List[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    return db.query(Agent).all()

@router.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found.")
    return agent
