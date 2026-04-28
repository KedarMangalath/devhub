# Repo Map: omnia

- Fingerprint: aaa28bfe5ea3bb30a42d496464b98400836a8bce
- Indexed files: 45

## Top Directories
- `src`: 24 files
- `frontend`: 12 files
- `backend`: 6 files
- `.`: 5 files

## Important Files
- `src/App.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 32 lines. Primary symbol: App. Key imports: import React from 'react', import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom', import LandingPage from './pages/LandingPage', import PatientDashboard from './pages/PatientDashboard', import DoctorDirectory from './pages/DoctorDirectory'.
- `backend/src/index.ts`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 126 lines. Primary symbol: app. Key imports: import express from 'express';, import cors from 'cors';, import { PrismaClient } from '@prisma/client';, import dotenv from 'dotenv';.
- `backend/tsconfig.json`: TypeScript compiler configuration that controls type-checking, module resolution, emitted output, and project references. It has about 10 lines. Top-level keys: compilerOptions.
- `frontend/tsconfig.json`: TypeScript compiler configuration that controls type-checking, module resolution, emitted output, and project references. It has about 26 lines. Top-level keys: compilerOptions, include, exclude.
- `vite.config.js`: Build or bundling configuration that tells the toolchain how to compile, package, or emit artifacts for this project. It has about 7 lines. Key imports: import { defineConfig } from 'vite', import react from '@vitejs/plugin-react'.
- `backend/package.json`: Node package manifest defining runtime metadata, scripts, dependencies, and package-manager behavior for the repo or workspace. It has about 27 lines. Top-level keys: name, version, main, scripts, dependencies, devDependencies.
- `frontend/package.json`: Node package manifest defining runtime metadata, scripts, dependencies, and package-manager behavior for the repo or workspace. It has about 28 lines. Top-level keys: name, version, private, scripts, dependencies, devDependencies.
- `package.json`: Node package manifest defining runtime metadata, scripts, dependencies, and package-manager behavior for the repo or workspace. It has about 13 lines. Top-level keys: name, version, private, scripts, dependencies.
- `src/main.jsx`: Reusable UI component responsible for part of the interface. It has about 10 lines. Key imports: import React from 'react', import ReactDOM from 'react-dom/client', import App from './App', import './index.css'.
- `frontend/postcss.config.js`: Source file that contributes to the `frontend` area of the repository. It has about 6 lines.
- `frontend/tailwind.config.ts`: Source file that contributes to the `frontend` area of the repository. It has about 24 lines. Key imports: import type { Config } from "tailwindcss";.
- `postcss.config.js`: Source file that contributes to the project root area of the repository. It has about 6 lines.
- `tailwind.config.js`: Source file that contributes to the project root area of the repository. It has about 33 lines.
- `src/components/AppShell.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 161 lines. Primary symbol: navItems. Key imports: import React from 'react';, import { Outlet, NavLink, Link, useLocation } from 'react-router-dom';, import { Menu, X, Activity, Home, Users, Calendar, FileText, Bell, User } from 'lucide-react';, import { cn } from '../utils/cn';, import { patient_profile } from '../mockData';.
- `src/components/layout/Navbar.jsx`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 162 lines. Primary symbol: Navbar. Key imports: import { useState } from 'react', import { Link, useLocation } from 'react-router-dom', import { Activity, User, Menu, X } from 'lucide-react', import { patient_profile } from '../../mockData', import Button from '../ui/Button'.
- `frontend/app/ai-symptom-checker/page.tsx`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 114 lines. Primary symbol: AIResponse. Key imports: import { useState } from 'react';, import axios from 'axios';, import { Bot, AlertCircle, Activity, ArrowRight } from 'lucide-react';.
- `frontend/app/appointments/page.tsx`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 175 lines. Primary symbol: Doctor. Key imports: import { useEffect, useState } from 'react';, import axios from 'axios';, import { format } from 'date-fns';, import { Calendar as CalendarIcon, Clock } from 'lucide-react';.
- `frontend/app/doctors/page.tsx`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 64 lines. Primary symbol: Doctor. Key imports: import { useEffect, useState } from 'react';, import axios from 'axios';, import { Star, MapPin } from 'lucide-react';.
- `frontend/app/page.tsx`: Data model or type-definition file describing the shapes the application stores, exchanges, or validates. It has about 101 lines. Primary symbol: Stats. Key imports: import { useEffect, useState } from 'react';, import axios from 'axios';, import { Users, CalendarCheck, ActivitySquare } from 'lucide-react';, import { format } from 'date-fns';.
- `src/pages/BookingWorkflow.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 355 lines. Primary symbol: steps. Key imports: import { useState } from 'react', import { useParams, useNavigate } from 'react-router-dom', import { CheckCircle, Calendar, Clock, CreditCard, FileText, ChevronRight, ChevronLeft } from 'lucide-react', import AppShell from '../components/layout/AppShell', import Button from '../components/ui/Button'. Representative commands: Go to Dashboard.
- `src/pages/DoctorDirectory.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 134 lines. Primary symbol: DoctorDirectory. Key imports: import { useState, useMemo } from 'react', import { Search, Filter, Sparkles } from 'lucide-react', import AppShell from '../components/layout/AppShell', import DoctorCard from '../components/domain/DoctorCard', import Button from '../components/ui/Button'.
- `src/pages/DoctorProfile.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 305 lines. Primary symbol: generateUpcomingDates. Key imports: import React, { useState, useEffect } from 'react', import { useParams, Link } from 'react-router-dom', import { Star, MapPin, Clock, Award, ShieldCheck } from 'lucide-react', import AppShell from '../components/layout/AppShell', import Button from '../components/ui/Button'.
- `src/pages/LandingPage.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 228 lines. Primary symbol: LandingPage. Key imports: import React from 'react', import { Link } from 'react-router-dom', import { ArrowRight, Shield, Clock, Video, Star } from 'lucide-react', import AppShell from '../components/layout/AppShell', import Button from '../components/ui/Button'.
- `src/pages/MedicalHistory.jsx`: Page-level UI module that usually composes other components and represents a route or large screen. It has about 142 lines. Primary symbol: MedicalHistory. Key imports: import { useState, useMemo } from 'react', import { Filter, Download, FileText } from 'lucide-react', import AppShell from '../components/layout/AppShell', import AppointmentCard from '../components/domain/AppointmentCard', import Button from '../components/ui/Button'. Representative commands: showSummary={true}.

## Project Instructions
- `.devhub/DEVHUB.md`

## Repo Tree
```text
omnia/
|- .devhub/
|- backend
|  |- prisma
|  |  `- seed.ts
|  |- src
|  |  `- index.ts
|  |- package.json
|  `- tsconfig.json
|- frontend
|  |- app
|  |  |- ai-symptom-checker
|  |  |  `- page.tsx
|  |  |- appointments
|  |  |  `- page.tsx
|  |  |- doctors
|  |  |  `- page.tsx
|  |  |- globals.css
|  |  |- layout.tsx
|  |  `- page.tsx
|  |- components
|  |  |- Navbar.tsx
|  |  `- Sidebar.tsx
|  |- package.json
|  |- postcss.config.js
|  |- tailwind.config.ts
|  `- tsconfig.json
|- src
|  |- components
|  |  |- domain
|  |  |  |- AIInsightCard.jsx
|  |  |  |- AppointmentCard.jsx
|  |  |  `- DoctorCard.jsx
|  |  |- layout
|  |  |  |- AppShell.jsx
|  |  |  |- Footer.jsx
|  |  |  `- Navbar.jsx
|  |  |- ui
|  |  |  |- Badge.jsx
|  |  |  |- Button.jsx
|  |  |  `- Card.jsx
|  |  |- AppShell.jsx
|  |  |- ItemCard.jsx
|  |  |- StatCard.jsx
|  |  |- TabbedPanel.jsx
|  |  `- TimelineList.jsx
|  |- pages
|  |  |- BookingWorkflow.jsx
|  |  |- DoctorDirectory.jsx
|  |  |- DoctorProfile.jsx
|  |  |- LandingPage.jsx
|  |  |- MedicalHistory.jsx
|  |  `- PatientDashboard.jsx
|  |- App.jsx
|  |- index.css
|  |- main.jsx
|  `- mockData.js
|- index.html
|- package.json
|- postcss.config.js
|- tailwind.config.js
`- vite.config.js
```