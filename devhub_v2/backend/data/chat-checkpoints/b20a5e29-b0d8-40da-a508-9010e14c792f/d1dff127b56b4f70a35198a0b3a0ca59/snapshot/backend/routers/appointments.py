from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Appointment, Doctor, User
from schemas import AppointmentCreate, AppointmentResponse
from auth import get_current_user

router = APIRouter(
    prefix="/api/appointments",
    tags=["appointments"]
)

@router.post("", response_model=AppointmentResponse)
def create_appointment(
    appointment: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doctor = db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    new_appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=appointment.doctor_id,
        appointment_date=appointment.appointment_date,
        status="scheduled",
        consultation_type=appointment.consultation_type,
        notes=appointment.notes
    )
    
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)
    
    return new_appointment

@router.get("", response_model=List[AppointmentResponse])
def list_user_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "doctor":
        doctor_profile = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor_profile:
            return []
        appointments = db.query(Appointment).filter(
            Appointment.doctor_id == doctor_profile.id
        ).order_by(Appointment.appointment_date.desc()).all()
    else:
        appointments = db.query(Appointment).filter(
            Appointment.patient_id == current_user.id
        ).order_by(Appointment.appointment_date.desc()).all()
        
    return appointments