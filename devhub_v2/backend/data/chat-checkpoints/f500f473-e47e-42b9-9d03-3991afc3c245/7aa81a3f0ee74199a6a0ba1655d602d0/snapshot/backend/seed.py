import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'omnia_backend.settings')
django.setup()

from api.models import Doctor, Service

def seed():
    Doctor.objects.all().delete()
    Service.objects.all().delete()

    Doctor.objects.create(name="Dr. Sarah Jenkins", specialty="Cardiology", experience_years=12, image_url="https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=300&h=300")
    Doctor.objects.create(name="Dr. Michael Chen", specialty="Dermatology", experience_years=8, image_url="https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&q=80&w=300&h=300")
    Doctor.objects.create(name="Dr. Emily Rodriguez", specialty="Pediatrics", experience_years=15, image_url="https://images.unsplash.com/photo-1594824476967-48c8b964273f?auto=format&fit=crop&q=80&w=300&h=300")
    Doctor.objects.create(name="Dr. James Wilson", specialty="Orthopedics", experience_years=20, image_url="https://images.unsplash.com/photo-1622253692010-333f2da6031d?auto=format&fit=crop&q=80&w=300&h=300")
    Doctor.objects.create(name="Dr. Olivia Parker", specialty="Neurology", experience_years=10, image_url="https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&q=80&w=300&h=300")
    Doctor.objects.create(name="Dr. William Davis", specialty="Oncology", experience_years=18, image_url="https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&q=80&w=300&h=300")
    Doctor.objects.create(name="Dr. Sophia Martinez", specialty="Psychiatry", experience_years=14, image_url="https://images.unsplash.com/photo-1594824476967-48c8b964273f?auto=format&fit=crop&q=80&w=300&h=300")
    Doctor.objects.create(name="Dr. Alexander White", specialty="General Surgery", experience_years=22, image_url="https://images.unsplash.com/photo-1622253692010-333f2da6031d?auto=format&fit=crop&q=80&w=300&h=300")

    Service.objects.create(name="Video Consultation", description="Consult with top doctors from the comfort of your home.", icon_name="Video")
    Service.objects.create(name="In-Clinic Visit", description="Book appointments at our state-of-the-art facilities.", icon_name="Building2")
    Service.objects.create(name="Lab Tests", description="Home sample collection for all major pathology tests.", icon_name="TestTube")
    Service.objects.create(name="Medicines", description="Get medicines delivered to your doorstep within 2 hours.", icon_name="Pill")
    Service.objects.create(name="Health Checkups", description="Comprehensive health packages for you and your family.", icon_name="ShieldPlus")
    Service.objects.create(name="Dental Care", description="Expert dental services and treatments.", icon_name="Star")

    print("Database seeded successfully!")

if __name__ == '__main__':
    seed()
