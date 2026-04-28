import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  // Clear existing data
  await prisma.appointment.deleteMany();
  await prisma.doctor.deleteMany();
  await prisma.patient.deleteMany();

  // Create Patient
  const patient = await prisma.patient.create({
    data: {
      name: 'Alex Johnson',
      email: 'alex.johnson@example.com',
    },
  });

  // Create Doctors
  const doctors = await Promise.all([
    prisma.doctor.create({ data: { name: 'Dr. Sarah Jenkins', specialty: 'Cardiology', rating: 4.9, imageUrl: 'https://picsum.photos/seed/dr1/200' } }),
    prisma.doctor.create({ data: { name: 'Dr. Michael Chen', specialty: 'Neurology', rating: 4.8, imageUrl: 'https://picsum.photos/seed/dr2/200' } }),
    prisma.doctor.create({ data: { name: 'Dr. Emily Rodriguez', specialty: 'Pediatrics', rating: 4.9, imageUrl: 'https://picsum.photos/seed/dr3/200' } }),
    prisma.doctor.create({ data: { name: 'Dr. James Wilson', specialty: 'General Practice', rating: 4.7, imageUrl: 'https://picsum.photos/seed/dr4/200' } }),
    prisma.doctor.create({ data: { name: 'Dr. Olivia Taylor', specialty: 'Dermatology', rating: 4.9, imageUrl: 'https://picsum.photos/seed/dr5/200' } }),
  ]);

  // Create Appointments
  await prisma.appointment.create({
    data: {
      date: new Date(new Date().getTime() + 24 * 60 * 60 * 1000), // Tomorrow
      status: 'SCHEDULED',
      doctorId: doctors[0].id,
      patientId: patient.id,
    },
  });

  await prisma.appointment.create({
    data: {
      date: new Date(new Date().getTime() - 48 * 60 * 60 * 1000), // 2 days ago
      status: 'COMPLETED',
      doctorId: doctors[3].id,
      patientId: patient.id,
    },
  });

  console.log('Database seeded successfully!');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
