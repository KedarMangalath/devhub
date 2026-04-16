@echo off
echo Starting DevHub servers...

:: Start the Django backend
start "DevHub Backend" cmd /k ".\devhub_v2\venv\Scripts\activate && cd devhub_v2\backend && python manage.py runserver"

:: Start the React frontend
start "DevHub Frontend" cmd /k "cd devhub_v2\frontend && npm run dev"

echo Successfully started backend and frontend in separate windows!
