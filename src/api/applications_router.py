"""API endpoints to manage persisted guided-flow applications (PA, Travel, Serenicare)."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException

from src.chatbot.controllers.personal_accident_controller import PersonalAccidentController
from src.chatbot.controllers.travel_insurance_controller import TravelInsuranceController
from src.chatbot.controllers.serenicare_controller import SerenicareController
from src.api.main import get_db, get_router

api = APIRouter()

# Personal Accident
@api.post("/applications/pa", tags=["Applications"])
async def create_pa_application(user_id: str, db=Depends(get_db)):
    controller = PersonalAccidentController(db)
    app = controller.create_application(user_id, {})
    return app

@api.get("/applications/pa/{app_id}", tags=["Applications"])
async def get_pa_application(app_id: str, db=Depends(get_db)):
    controller = PersonalAccidentController(db)
    app = controller.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

@api.delete("/applications/pa/{app_id}", tags=["Applications"])
async def delete_pa_application(app_id: str, db=Depends(get_db)):
    controller = PersonalAccidentController(db)
    ok = controller.delete_application(app_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"deleted": True}

# Travel
@api.post("/applications/travel", tags=["Applications"])
async def create_travel_application(user_id: str, db=Depends(get_db)):
    controller = TravelInsuranceController(db)
    app = controller.create_application(user_id, {})
    return app

@api.get("/applications/travel/{app_id}", tags=["Applications"])
async def get_travel_application(app_id: str, db=Depends(get_db)):
    controller = TravelInsuranceController(db)
    app = controller.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

@api.delete("/applications/travel/{app_id}", tags=["Applications"])
async def delete_travel_application(app_id: str, db=Depends(get_db)):
    controller = TravelInsuranceController(db)
    ok = controller.delete_application(app_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"deleted": True}

# Serenicare
@api.post("/applications/serenicare", tags=["Applications"])
async def create_serenicare_application(user_id: str, db=Depends(get_db)):
    controller = SerenicareController(db)
    app = controller.create_application(user_id, {})
    return app

@api.get("/applications/serenicare/{app_id}", tags=["Applications"])
async def get_serenicare_application(app_id: str, db=Depends(get_db)):
    controller = SerenicareController(db)
    app = controller.get_application(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

@api.delete("/applications/serenicare/{app_id}", tags=["Applications"])
async def delete_serenicare_application(app_id: str, db=Depends(get_db)):
    controller = SerenicareController(db)
    ok = controller.delete_application(app_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"deleted": True}
