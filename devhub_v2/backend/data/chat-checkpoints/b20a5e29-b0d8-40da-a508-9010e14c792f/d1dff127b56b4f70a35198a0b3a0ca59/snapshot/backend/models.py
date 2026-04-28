from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Numeric, Boolean
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    full_name = Column(String)
    role = Column(String)
    phone = Column(String)
    created_at = Column(DateTime)

    doctor_profile = relationship("Doctor", back_populates="user", uselist=False)
    appointments_as_patient = relationship("Appointment", back_populates="patient")
    prescriptions_as_patient = relationship("Prescription", back_populates="patient")
    orders = relationship("Order", back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    specialty = Column(String)
    experience_years = Column(Integer)
    consultation_fee = Column(Numeric)
    bio = Column(Text)
    image_url = Column(String)

    user = relationship("User", back_populates="doctor_profile")
    appointments = relationship("Appointment", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    appointment_date = Column(DateTime)
    status = Column(String)
    consultation_type = Column(String)
    notes = Column(Text)

    patient = relationship("User", back_populates="appointments_as_patient")
    doctor = relationship("Doctor", back_populates="appointments")
    prescription = relationship("Prescription", back_populates="appointment", uselist=False)


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"))
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    patient_id = Column(Integer, ForeignKey("users.id"))
    medications = Column(Text)
    instructions = Column(Text)
    created_at = Column(DateTime)

    appointment = relationship("Appointment", back_populates="prescription")
    doctor = relationship("Doctor", back_populates="prescriptions")
    patient = relationship("User", back_populates="prescriptions_as_patient")


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    price = Column(Numeric)
    requires_prescription = Column(Boolean, default=False)
    stock = Column(Integer, default=0)
    image_url = Column(String)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    total_amount = Column(Numeric)
    status = Column(String)
    shipping_address = Column(Text)
    created_at = Column(DateTime)

    patient = relationship("User", back_populates="orders")