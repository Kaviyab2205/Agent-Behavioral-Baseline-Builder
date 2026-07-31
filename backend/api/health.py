from fastapi import APIRouter
from datetime import datetime
from backend.schemas import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }
