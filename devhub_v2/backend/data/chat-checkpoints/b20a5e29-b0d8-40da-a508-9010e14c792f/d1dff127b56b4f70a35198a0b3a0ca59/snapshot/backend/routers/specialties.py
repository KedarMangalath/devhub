from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Doctor

router = APIRouter(
    prefix="/api/specialties",
    tags=["specialties"]
)

@router.get("")
def get_specialties(db: Session = Depends(get_db)):
    results = db.query(
        Doctor.specialty,
        func.count(Doctor.id).label("count")
    ).group_by(Doctor.specialty).all()
    
    specialties = []
    for row in results:
        if row.specialty:
            specialties.append({
                "name": row.specialty,
                "count": row.count
            })
            
    return specialties