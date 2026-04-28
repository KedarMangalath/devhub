# Repo Map: Omnia

- Fingerprint: c15ef1ce67635e54b8acc44999c47ab10384fdc9
- Indexed files: 51

## Top Directories
- `frontend`: 37 files
- `backend`: 14 files

## Important Files
- `frontend/src/App.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 27 lines. Primary symbol: App. Key imports: import { BrowserRouter as Router, Routes, Route } from 'react-router-dom', import { AuthProvider } from './hooks/useAuth', import Home from './pages/Home', import DoctorDirectory from './pages/DoctorDirectory', import DoctorProfile from './pages/DoctorProfile'.
- `frontend/vite.config.js`: Build or bundling configuration that tells the toolchain how to compile, package, or emit artifacts for this project. It has about 15 lines. Key imports: import { defineConfig } from 'vite', import react from '@vitejs/plugin-react'.
- `backend/requirements.txt`: Configuration file that controls tooling, runtime behavior, or project conventions. It has about 7 lines. Representative commands: uvicorn>=0.23.2, python-jose[cryptography]>=3.3.0, python-multipart>=0.0.6.
- `frontend/package.json`: Node package manifest defining runtime metadata, scripts, dependencies, and package-manager behavior for the repo or workspace. It has about 26 lines. Top-level keys: name, private, version, type, scripts, dependencies.
- `frontend/src/main.jsx`: Reusable UI component responsible for part of the interface. It has about 10 lines. Key imports: import React from 'react', import ReactDOM from 'react-dom/client', import App from './App', import './index.css'.
- `backend/main.py`: Source file that contributes to the `backend` area of the repository. It has about 3 lines. Key imports: from fastapi import FastAPI.
- `frontend/postcss.config.js`: Source file that contributes to the `frontend` area of the repository. It has about 6 lines.
- `frontend/tailwind.config.js`: Source file that contributes to the `frontend` area of the repository. It has about 40 lines.
- `backend/routers/auth.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 37 lines. Primary symbol: login_for_access_token. Key imports: from fastapi import APIRouter, Depends, HTTPException, status, from fastapi.security import OAuth2PasswordRequestForm, from sqlalchemy.orm import Session, from database import get_db, from models import User.
- `backend/routers/doctors.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 60 lines. Primary symbol: list_doctors. Key imports: from fastapi import APIRouter, Depends, HTTPException, from sqlalchemy.orm import Session, from typing import List, from datetime import datetime, timedelta, from database import get_db.
- `backend/models.py`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 92 lines. Primary symbol: User. Key imports: from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Numeric, Boolean, from sqlalchemy.orm import relationship, from database import Base. Representative commands: shipping_address = Column(Text).
- `backend/schemas.py`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 105 lines. Primary symbol: Token. Key imports: from pydantic import BaseModel, EmailStr, ConfigDict, Field, from typing import List, Optional, from datetime import datetime, from decimal import Decimal. Representative commands: shipping_address: str.
- `frontend/src/pages/DoctorProfile.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 133 lines. Primary symbol: DoctorProfile. Key imports: import { useState, useEffect } from 'react', import { useParams, useNavigate } from 'react-router-dom', import { getDoctor, getDoctorSlots, createAppointment } from '../api/endpoints.js', import Navbar from '../components/Navbar.jsx', import DoctorInfo from '../components/DoctorInfo.jsx'.
- `frontend/src/pages/Home.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 125 lines. Primary symbol: Home. Key imports: import { useState, useEffect } from 'react', import { useNavigate } from 'react-router-dom', import { getSpecialties, getDoctors } from '../api/endpoints.js', import Navbar from '../components/Navbar.jsx', import HeroSearch from '../components/HeroSearch.jsx'.
- `frontend/src/pages/Pharmacy.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 72 lines. Primary symbol: Pharmacy. Key imports: import { useState, useEffect } from 'react', import { getMedicines, createOrder } from '../api/endpoints.js', import Navbar from '../components/Navbar.jsx', import MedicineCard from '../components/MedicineCard.jsx', import CartDrawer from '../components/CartDrawer.jsx'.
- `frontend/src/pages/TeleconsultationRoom.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 33 lines. Primary symbol: TeleconsultationRoom. Key imports: import { useState } from 'react', import { useParams } from 'react-router-dom', import { useAuth } from '../hooks/useAuth.js', import { createPrescription } from '../api/endpoints.js', import Navbar from '../components/Navbar.jsx'.
- `backend/routers/prescriptions.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 63 lines. Primary symbol: list_user_prescriptions. Key imports: from fastapi import APIRouter, Depends, HTTPException, from sqlalchemy.orm import Session, from typing import List, from database import get_db, from models import Prescription, User, Doctor.
- `frontend/src/pages/DoctorDirectory.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 113 lines. Primary symbol: DoctorDirectory. Key imports: import { useState, useEffect } from 'react', import { useSearchParams } from 'react-router-dom', import { getDoctors, getSpecialties } from '../api/endpoints.js', import Navbar from '../components/Navbar.jsx', import FilterSidebar from '../components/FilterSidebar.jsx'.
- `frontend/src/pages/PatientDashboard.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 172 lines. Primary symbol: PatientDashboard. Key imports: import { useState, useEffect } from 'react', import { getAppointments, getPrescriptions } from '../api/endpoints.js', import { useAuth } from '../hooks/useAuth.js', import Navbar from '../components/Navbar.jsx', import DashboardSidebar from '../components/DashboardSidebar.jsx'. Representative commands: Go to Login.
- `frontend/src/pages/Login.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 63 lines. Primary symbol: Login. Key imports: import { useState } from 'react', import { useNavigate } from 'react-router-dom', import { useAuth } from '../hooks/useAuth.js', import Navbar from '../components/Navbar.jsx'.
- `backend/routers/appointments.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 56 lines. Primary symbol: create_appointment. Key imports: from fastapi import APIRouter, Depends, HTTPException, from sqlalchemy.orm import Session, from typing import List, from database import get_db, from models import Appointment, Doctor, User.
- `backend/routers/medicines.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 15 lines. Primary symbol: list_medicines. Key imports: from fastapi import APIRouter, Depends, from sqlalchemy.orm import Session, from typing import List, from database import get_db, from models import Medicine.
- `backend/routers/orders.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 51 lines. Primary symbol: create_order. Key imports: from fastapi import APIRouter, Depends, HTTPException, from sqlalchemy.orm import Session, from datetime import datetime, from database import get_db, from models import Order, Medicine. Representative commands: shipping_address=order.shipping_address,.
- `backend/routers/specialties.py`: Routing or entrypoint module that wires screens, handlers, or navigation together. It has about 27 lines. Primary symbol: get_specialties. Key imports: from fastapi import APIRouter, Depends, from sqlalchemy.orm import Session, from sqlalchemy import func, from database import get_db, from models import Doctor.

## Project Instructions
- `.devhub/DEVHUB.md`

## Repo Tree
```text
Omnia/
|- .devhub/
|- frontend/
|- backend
|  |- routers
|  |  |- appointments.py
|  |  |- auth.py
|  |  |- doctors.py
|  |  |- medicines.py
|  |  |- orders.py
|  |  |- prescriptions.py
|  |  `- specialties.py
|  |- auth.py
|  |- database.py
|  |- main.py
|  |- models.py
|  |- requirements.txt
|  |- schemas.py
|  `- seed.py
`- frontend
   |- src
   |  |- api
   |  |  |- client.js
   |  |  `- endpoints.js
   |  |- components
   |  |  |- BookingModal.jsx
   |  |  |- CartDrawer.jsx
   |  |  |- ChatBox.jsx
   |  |  |- CheckoutModal.jsx
   |  |  |- DashboardSidebar.jsx
   |  |  |- DoctorCard.jsx
   |  |  |- DoctorInfo.jsx
   |  |  |- EPrescriptionForm.jsx
   |  |  |- FilterSidebar.jsx
   |  |  |- Footer.jsx
   |  |  |- HeroSearch.jsx
   |  |  |- MedicineCard.jsx
   |  |  |- Navbar.jsx
   |  |  |- PrescriptionCard.jsx
   |  |  |- SpecialtyGrid.jsx
   |  |  |- TimeSlotPicker.jsx
   |  |  |- TopDoctorsCarousel.jsx
   |  |  |- UpcomingAppointments.jsx
   |  |  `- VideoPlayerPlaceholder.jsx
   |  |- hooks
   |  |  `- useAuth.js
   |  |- pages
   |  |  |- DoctorDirectory.jsx
   |  |  |- DoctorProfile.jsx
   |  |  |- Home.jsx
   |  |  |- Login.jsx
   |  |  |- PatientDashboard.jsx
   |  |  |- Pharmacy.jsx
   |  |  `- TeleconsultationRoom.jsx
   |  |- App.jsx
   |  |- index.css
   |  `- main.jsx
   |- index.html
   |- package.json
   |- postcss.config.js
   |- tailwind.config.js
   `- vite.config.js
```