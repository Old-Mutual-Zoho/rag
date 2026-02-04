"""
API endpoints to manage persisted guided-flow applications
(Personal Accident, Travel Insurance, Serenicare).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.main import get_db
from src.chatbot.controllers.personal_accident_controller import PersonalAccidentController
from src.chatbot.controllers.serenicare_controller import SerenicareController
from src.chatbot.controllers.travel_insurance_controller import TravelInsuranceController

api = APIRouter()


def _parse_sort(sort: str, direction: str) -> tuple[str, bool]:
    sort = (sort or "created_at").strip()
    direction = (direction or "desc").strip().lower()
    descending = direction != "asc"
    return sort, descending


# --------------------------------------------------------------------------- #
# Personal Accident
# --------------------------------------------------------------------------- #
@api.get("/applications/pa", tags=["Applications"])
async def list_pa_applications(
    user_id: Optional[str] = None,
    sort: str = "created_at",
    direction: str = "desc",
    db=Depends(get_db),
):
    controller = PersonalAccidentController(db)
    sort, descending = _parse_sort(sort, direction)
    # Only allow scalar fields (never JSON like `next_of_kin`)
    if sort not in {"id", "user_id", "status", "created_at", "updated_at"}:
        sort = "created_at"
    return controller.list_applications(user_id=user_id, order_by=sort, descending=descending)


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


# --------------------------------------------------------------------------- #
# Travel Insurance
# --------------------------------------------------------------------------- #
@api.get("/applications/travel", tags=["Applications"])
async def list_travel_applications(
    user_id: Optional[str] = None,
    sort: str = "created_at",
    direction: str = "desc",
    db=Depends(get_db),
):
    controller = TravelInsuranceController(db)
    sort, descending = _parse_sort(sort, direction)
    if sort not in {"id", "user_id", "status", "created_at", "updated_at"}:
        sort = "created_at"
    return controller.list_applications(user_id=user_id, order_by=sort, descending=descending)


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


# --------------------------------------------------------------------------- #
# Serenicare
# --------------------------------------------------------------------------- #
@api.get("/applications/serenicare", tags=["Applications"])
async def list_serenicare_applications(
    user_id: Optional[str] = None,
    sort: str = "created_at",
    direction: str = "desc",
    db=Depends(get_db),
):
    controller = SerenicareController(db)
    sort, descending = _parse_sort(sort, direction)
    if sort not in {"id", "user_id", "status", "created_at", "updated_at"}:
        sort = "created_at"
    return controller.list_applications(user_id=user_id, order_by=sort, descending=descending)


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
