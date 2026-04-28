from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Prescription, User, Doctor
from schemas import PrescriptionCreate, PrescriptionResponse
from auth import get_current_user

router = APIRouter(
    prefix="/api/prescriptions",
    tags=["prescriptions"]
)

@router.get("", response_model=List[PrescriptionResponse])
def list_user_prescriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "doctor":
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            return []
        return db.query(Prescription).filter(Prescription.doctor_id == doctor.id).all()
    
    return db.query(Prescription).filter(Prescription.patient_id == current_user.id).all()

@router.post("", response_model=PrescriptionResponse)
def create_prescription(
    prescription: PrescriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import datetime
    
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can create prescriptions")
        
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
        
    existing_prescription = db.query(Prescription).filter(Prescription.appointment_id == prescription.appointment_id).first()
    if existing_prescription:
        raise HTTPException(status_code=400, detail="Prescription already exists for this appointment")
        
    appointment = next((a for a in doctor.appointments if a.id == prescription.appointment_id), None)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found or not assigned to you")
        
    new_prescription = Prescription(
        appointment_id=prescription.appointment_id,
        doctor_id=doctor.id,
        patient_id=appointment.patient_id,
        medications=prescription.medications,
        instructions=prescription.instructions,
        created_at=datetime.datetime.utcnow()
    )
    
    db.add(new_prescription)
    db.commit()
    db.refresh(new_prescription)
    
    return new_prescription