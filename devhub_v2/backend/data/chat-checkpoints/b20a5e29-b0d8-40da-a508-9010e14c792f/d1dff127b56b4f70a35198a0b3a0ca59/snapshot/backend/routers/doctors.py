from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from database import get_db
from models import Doctor, User
from schemas import DoctorResponse

router = APIRouter(
    prefix="/api/doctors",
    tags=["doctors"]
)

@router.get("", response_model=List[DoctorResponse])
def list_doctors(specialty: str = None, db: Session = Depends(get_db)):
    query = db.query(Doctor).join(User)
    
    if specialty:
        query = query.filter(Doctor.specialty == specialty)
        
    return query.all()

@router.get("/{id}", response_model=DoctorResponse)
def get_doctor_details(id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).join(User).filter(Doctor.id == id).first()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    return doctor

@router.get("/{id}/slots")
def get_doctor_slots(id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == id).first()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    slots = []
    now = datetime.now()
    
    for day_offset in range(1, 4):
        current_date = now + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        day_slots = [
            f"{date_str}T09:00:00",
            f"{date_str}T10:00:00",
            f"{date_str}T11:00:00",
            f"{date_str}T13:00:00",
            f"{date_str}T14:00:00",
            f"{date_str}T15:00:00",
            f"{date_str}T16:00:00"
        ]
        slots.extend(day_slots)
        
    return {
        "doctor_id": id,
        "available_slots": slots
    }