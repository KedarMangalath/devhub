from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Medicine
from schemas import MedicineResponse

router = APIRouter(
    prefix="/api/medicines",
    tags=["medicines"]
)

@router.get("", response_model=List[MedicineResponse])
def list_medicines(db: Session = Depends(get_db)):
    return db.query(Medicine).all()