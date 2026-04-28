import express from 'express';
import cors from 'cors';
import { PrismaClient } from '@prisma/client';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
const prisma = new PrismaClient();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// --- Routes ---

// Get Dashboard Stats
app.get('/api/stats', async (req, res) => {
  try {
    const doctorCount = await prisma.doctor.count();
    const patientCount = await prisma.patient.count();
    const appointmentCount = await prisma.appointment.count();
    const recentAppointments = await prisma.appointment.findMany({
      take: 5,
      orderBy: { date: 'desc' },
      include: { doctor: true, patient: true }
    });

    res.json({
      doctorCount,
      patientCount,
      appointmentCount,
      recentAppointments
    });
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

// Get Doctors
app.get('/api/doctors', async (req, res) => {
  try {
    const doctors = await prisma.doctor.findMany();
    res.json(doctors);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch doctors' });
  }
});

// Get Appointments
app.get('/api/appointments', async (req, res) => {
  try {
    const appointments = await prisma.appointment.findMany({
      orderBy: { date: 'asc' },
      include: { doctor: true, patient: true }
    });
    res.json(appointments);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch appointments' });
  }
});

// Book Appointment
app.post('/api/appointments', async (req, res) => {
  try {
    const { doctorId, date } = req.body;
    
    // For scaffold, grab the first patient
    const patient = await prisma.patient.findFirst();
    if (!patient) return res.status(400).json({ error: 'No patient found in DB' });

    const appointment = await prisma.appointment.create({
      data: {
        doctorId,
        patientId: patient.id,
        date: new Date(date),
        status: 'SCHEDULED'
      },
      include: { doctor: true, patient: true }
    });

    res.json(appointment);
  } catch (error) {
    res.status(500).json({ error: 'Failed to book appointment' });
  }
});

// AI Symptom Checker (Mocked for scaffold)
app.post('/api/ai/symptom-check', async (req, res) => {
  try {
    const { symptoms } = req.body;
    const lowerSymptoms = symptoms.toLowerCase();
    
    let diagnosis = "Based on your symptoms, it is recommended to consult a General Practitioner for a proper evaluation.";
    let urgency = "Low";
    let department = "General Practice";

    if (lowerSymptoms.includes('headache') || lowerSymptoms.includes('migraine')) {
      diagnosis = "Possible tension headache or migraine. Ensure you are hydrated and resting.";
      department = "Neurology";
    } else if (lowerSymptoms.includes('chest pain') || lowerSymptoms.includes('heart')) {
      diagnosis = "Chest pain can be serious. Please seek immediate medical attention or visit an emergency room.";
      urgency = "High";
      department = "Cardiology";
    } else if (lowerSymptoms.includes('rash') || lowerSymptoms.includes('skin')) {
      diagnosis = "Possible allergic reaction or dermatitis. Keep the area clean and avoid scratching.";
      department = "Dermatology";
    }

    // Simulate AI processing delay
    setTimeout(() => {
      res.json({
        analysis: diagnosis,
        urgency,
        recommendedDepartment: department
      });
    }, 1500);

  } catch (error) {
    res.status(500).json({ error: 'AI analysis failed' });
  }
});

app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
});
