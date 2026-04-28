from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DoctorBase(BaseModel):
    specialty: str
    experience_years: int
    consultation_fee: Decimal
    bio: Optional[str] = None
    image_url: Optional[str] = None

class DoctorResponse(DoctorBase):
    id: int
    user_id: int
    user: UserResponse
    
    model_config = ConfigDict(from_attributes=True)

class AppointmentBase(BaseModel):
    doctor_id: int
    appointment_date: datetime
    consultation_type: str
    notes: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentResponse(AppointmentBase):
    id: int
    patient_id: int
    status: str
    doctor: Optional[DoctorResponse] = None
    patient: Optional[UserResponse] = None
    
    model_config = ConfigDict(from_attributes=True)

class PrescriptionBase(BaseModel):
    appointment_id: int
    medications: str
    instructions: str

class PrescriptionCreate(PrescriptionBase):
    pass

class PrescriptionResponse(PrescriptionBase):
    id: int
    doctor_id: int
    patient_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MedicineBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    requires_prescription: bool = False
    stock: int = 0
    image_url: Optional[str] = None

class MedicineResponse(MedicineBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

class OrderItemCreate(BaseModel):
    medicine_id: int
    quantity: int

class OrderCreate(BaseModel):
    items: List[OrderItemCreate]
    shipping_address: str

class OrderResponse(BaseModel):
    id: int
    patient_id: int
    total_amount: Decimal
    status: str
    shipping_address: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)