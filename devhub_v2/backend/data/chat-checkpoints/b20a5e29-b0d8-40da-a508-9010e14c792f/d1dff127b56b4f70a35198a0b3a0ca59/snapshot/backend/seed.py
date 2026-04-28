from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import User, Doctor, Medicine, Appointment, Prescription
from auth import get_password_hash
from datetime import datetime, timedelta

def seed_database():
    print("Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    
    try:
        print("Seeding Patients...")
        patient1 = User(
            email="patient1@example.com",
            password_hash=get_password_hash("password123"),
            full_name="John Doe",
            role="patient",
            phone="1234567890",
            created_at=datetime.utcnow()
        )
        patient2 = User(
            email="patient2@example.com",
            password_hash=get_password_hash("password123"),
            full_name="Jane Smith",
            role="patient",
            phone="0987654321",
            created_at=datetime.utcnow()
        )
        db.add_all([patient1, patient2])
        db.commit()
        db.refresh(patient1)
        db.refresh(patient2)

        print("Seeding Doctors...")
        doc_data = [
            ("Dr. Alice Heart", "Cardiology", 15, 150.00, "Expert in cardiovascular health and preventive cardiology."),
            ("Dr. Bob Beat", "Cardiology", 10, 120.00, "Specializes in arrhythmias and heart failure management."),
            ("Dr. Carol Skin", "Dermatology", 8, 100.00, "Treats all skin conditions with a focus on acne and eczema."),
            ("Dr. Dave Derma", "Dermatology", 12, 130.00, "Cosmetic and medical dermatology, including skin cancer screening."),
            ("Dr. Eve Brain", "Neurology", 20, 200.00, "Renowned neurologist specializing in stroke and epilepsy."),
            ("Dr. Frank Nerve", "Neurology", 5, 90.00, "Focuses on peripheral neuropathy and movement disorders."),
            ("Dr. Grace Child", "Pediatrics", 14, 110.00, "Friendly pediatrician dedicated to newborn and toddler care."),
            ("Dr. Hank Kid", "Pediatrics", 7, 95.00, "Specializes in childhood development and adolescent medicine."),
            ("Dr. Ivy Mind", "Psychiatry", 18, 160.00, "Compassionate psychiatric care for anxiety and depression."),
            ("Dr. Jack Soul", "Psychiatry", 11, 140.00, "Expert in cognitive behavioral therapy and mood disorders.")
        ]
        
        doctors = []
        for i, (name, spec, exp, fee, bio) in enumerate(doc_data):
            u = User(
                email=f"doctor{i+1}@example.com",
                password_hash=get_password_hash("password123"),
                full_name=name,
                role="doctor",
                phone=f"555000{i:04d}",
                created_at=datetime.utcnow()
            )
            db.add(u)
            db.commit()
            db.refresh(u)
            
            d = Doctor(
                user_id=u.id,
                specialty=spec,
                experience_years=exp,
                consultation_fee=fee,
                bio=bio,
                image_url=f"https://picsum.photos/seed/doc{i+1}/300/200"
            )
            db.add(d)
            db.commit()
            db.refresh(d)
            doctors.append(d)

        print("Seeding Medicines...")
        med_data = [
            ("Aspirin 81mg", "Low dose aspirin for heart health.", 5.99, False, 100),
            ("Lisinopril 10mg", "ACE inhibitor for high blood pressure.", 15.50, True, 50),
            ("Amoxicillin 500mg", "Antibiotic for bacterial infections.", 12.00, True, 200),
            ("Ibuprofen 200mg", "Pain reliever and fever reducer.", 8.99, False, 300),
            ("Metformin 500mg", "Medication for type 2 diabetes.", 10.00, True, 150),
            ("Atorvastatin 20mg", "Statin to lower cholesterol.", 25.00, True, 80),
            ("Omeprazole 20mg", "Proton pump inhibitor for acid reflux.", 14.99, False, 120),
            ("Sertraline 50mg", "SSRI antidepressant.", 20.00, True, 60),
            ("Albuterol Inhaler", "Bronchodilator for asthma.", 35.00, True, 40),
            ("Loratadine 10mg", "Non-drowsy antihistamine for allergies.", 9.50, False, 250),
            ("Hydrochlorothiazide 25mg", "Diuretic for high blood pressure.", 11.00, True, 90),
            ("Gabapentin 300mg", "Nerve pain medication.", 18.00, True, 70),
            ("Amlodipine 5mg", "Calcium channel blocker for hypertension.", 13.50, True, 110),
            ("Levothyroxine 50mcg", "Thyroid hormone replacement.", 16.00, True, 130),
            ("Acetaminophen 500mg", "Pain reliever and fever reducer.", 7.99, False, 400)
        ]
        
        for i, (name, desc, price, req_rx, stock) in enumerate(med_data):
            m = Medicine(
                name=name,
                description=desc,
                price=price,
                requires_prescription=req_rx,
                stock=stock,
                image_url=f"https://picsum.photos/seed/med{i+1}/300/200"
            )
            db.add(m)
        db.commit()

        print("Seeding Appointments...")
        now = datetime.utcnow()
        
        past_appts = []
        for i in range(5):
            a = Appointment(
                patient_id=patient1.id if i % 2 == 0 else patient2.id,
                doctor_id=doctors[i].id,
                appointment_date=now - timedelta(days=10 - i),
                status="completed",
                consultation_type="video" if i % 2 == 0 else "in-person",
                notes=f"Routine checkup {i+1}. Patient reported mild symptoms."
            )
            db.add(a)
            past_appts.append(a)
        
        upcoming_appts = []
        for i in range(2):
            a = Appointment(
                patient_id=patient1.id if i == 0 else patient2.id,
                doctor_id=doctors[i+5].id,
                appointment_date=now + timedelta(days=i + 2),
                status="scheduled",
                consultation_type="video",
                notes=f"Follow-up consultation {i+1} regarding previous test results."
            )
            db.add(a)
            upcoming_appts.append(a)
            
        db.commit()
        for a in past_appts:
            db.refresh(a)

        print("Seeding Prescriptions...")
        for i in range(3):
            appt = past_appts[i]
            p = Prescription(
                appointment_id=appt.id,
                doctor_id=appt.doctor_id,
                patient_id=appt.patient_id,
                medications="Amoxicillin 500mg, Take 1 tablet twice daily for 7 days.\nIbuprofen 200mg, Take 1 tablet as needed for pain.",
                instructions="Take with food. Drink plenty of water. Avoid alcohol during the course of antibiotics.",
                created_at=appt.appointment_date + timedelta(hours=1)
            )
            db.add(p)
        db.commit()

        print("Database seeded successfully!")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()