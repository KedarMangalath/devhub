# Repo Map: omnia

- Fingerprint: 1401e85c439fee3601631397e076b72298bc393a
- Indexed files: 22

## Top Directories
- `backend`: 13 files
- `frontend`: 9 files

## Important Files
- `backend/omnia_backend/urls.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 7 lines. Key imports: from django.contrib import admin, from django.urls import path, include.
- `frontend/vite.config.js`: Build or bundling configuration that tells the toolchain how to compile, package, or emit artifacts for this project. It has about 6 lines. Key imports: import { defineConfig } from 'vite', import react from '@vitejs/plugin-react'.
- `backend/manage.py`: Configuration file that controls tooling, runtime behavior, or project conventions. It has about 16 lines. Primary symbol: main. Top headings: !/usr/bin/env python. Key imports: import os, import sys, from django.core.management import execute_from_command_line.
- `backend/requirements.txt`: Configuration file that controls tooling, runtime behavior, or project conventions. It has about 3 lines.
- `frontend/package.json`: Node package manifest defining runtime metadata, scripts, dependencies, and package-manager behavior for the repo or workspace. It has about 24 lines. Top-level keys: name, private, version, type, scripts, dependencies.
- `frontend/src/App.jsx`: Reusable UI component responsible for part of the interface. It has about 200 lines. Primary symbol: API_BASE. Key imports: import React, { useState, useEffect } from 'react';, import axios from 'axios';, import { Search, MapPin, ShieldPlus, Video, Building2, TestTube, Pill, Star, ChevronRight } from 'lucide-react';, import AppointmentModal from './components/AppointmentModal';.
- `backend/api/urls.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 12 lines. Key imports: from django.urls import path, include, from rest_framework.routers import DefaultRouter, from .views import DoctorViewSet, ServiceViewSet, AppointmentViewSet.
- `frontend/src/main.jsx`: Reusable UI component responsible for part of the interface. It has about 10 lines. Key imports: import React from 'react', import ReactDOM from 'react-dom/client', import App from './App.jsx', import './index.css'.
- `backend/omnia_backend/settings.py`: Source file that contributes to the `backend/omnia_backend` area of the repository. It has about 66 lines. Key imports: import os, from pathlib import Path.
- `frontend/postcss.config.js`: Source file that contributes to the `frontend` area of the repository. It has about 6 lines.
- `frontend/tailwind.config.js`: Source file that contributes to the `frontend` area of the repository. It has about 21 lines.
- `backend/omnia_backend/wsgi.py`: Source file that contributes to the `backend/omnia_backend` area of the repository. It has about 4 lines. Key imports: import os, from django.core.wsgi import get_wsgi_application.
- `backend/api/models.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 30 lines. Primary symbol: Doctor. Key imports: from django.db import models.
- `backend/api/views.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 15 lines. Primary symbol: DoctorViewSet. Key imports: from rest_framework import viewsets, from .models import Doctor, Service, Appointment, from .serializers import DoctorSerializer, ServiceSerializer, AppointmentSerializer.
- `frontend/src/components/AppointmentModal.jsx`: Reusable UI component responsible for part of the interface. It has about 134 lines. Primary symbol: AppointmentModal. Key imports: import React, { useState } from 'react';, import axios from 'axios';, import { X, Calendar, Clock, User, Mail, FileText } from 'lucide-react';.
- `backend/api/apps.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 5 lines. Primary symbol: ApiConfig. Key imports: from django.apps import AppConfig.
- `backend/api/serializers.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 17 lines. Primary symbol: DoctorSerializer. Key imports: from rest_framework import serializers, from .models import Doctor, Service, Appointment.
- `backend/api/__init__.py`: API-facing module that defines endpoints, handlers, or service integration behavior. It has about 0 lines.
- `frontend/index.html`: Source file that contributes to the `frontend` area of the repository. It has about 12 lines.
- `frontend/src/index.css`: Source file that contributes to the `frontend/src` area of the repository. It has about 7 lines.
- `backend/seed.py`: Source file that contributes to the `backend` area of the repository. It has about 25 lines. Primary symbol: seed. Key imports: import os, import django, from api.models import Doctor, Service.
- `backend/omnia_backend/__init__.py`: Source file that contributes to the `backend/omnia_backend` area of the repository. It has about 0 lines.

## Project Instructions
- `.devhub/DEVHUB.md`

## Repo Tree
```text
omnia/
|- .devhub/
|- frontend/
|- backend
|  |- api
|  |  |- __init__.py
|  |  |- apps.py
|  |  |- models.py
|  |  |- serializers.py
|  |  |- urls.py
|  |  `- views.py
|  |- omnia_backend
|  |  |- __init__.py
|  |  |- settings.py
|  |  |- urls.py
|  |  `- wsgi.py
|  |- manage.py
|  |- requirements.txt
|  `- seed.py
`- frontend
   |- src
   |  |- components
   |  |  `- AppointmentModal.jsx
   |  |- App.jsx
   |  |- index.css
   |  `- main.jsx
   |- index.html
   |- package.json
   |- postcss.config.js
   |- tailwind.config.js
   `- vite.config.js
```