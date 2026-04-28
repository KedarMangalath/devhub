export const patient_profile = {
  id: "pat_01H9X",
  name: "Alex Carter",
  email: "alex.carter@example.com",
  phone: "+1 (555) 284-8921",
  dob: "1988-04-15",
  gender: "Male",
  blood_type: "O+",
  height: "180 cm",
  weight: "78 kg",
  health_score: 88,
  avatar: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=300&q=80",
  allergies: ["Penicillin", "Peanuts"],
  current_medications: [
    { name: "Lisinopril", dosage: "10mg", frequency: "Daily" },
    { name: "Vitamin D3", dosage: "2000 IU", frequency: "Daily" }
  ],
  member_since: "2022-11-01T00:00:00Z"
};

export const dashboard_summary = {
  upcoming_appointments: 2,
  unread_insights: 3,
  health_score_trend: "+2.4%",
  active_prescriptions: 2,
  recent_activity: [
    { id: "act_1", type: "appointment_booked", text: "Booked consultation with Dr. Emily Chen", date: "2024-05-18T14:30:00Z" },
    { id: "act_2", type: "insight_generated", text: "New AI health insight available", date: "2024-05-17T09:15:00Z" },
    { id: "act_3", type: "medication_refill", text: "Lisinopril prescription refilled", date: "2024-05-10T11:00:00Z" }
  ]
};

export const specialties = [
  { id: "spec_gp", name: "General Practice", icon: "Stethoscope", doctor_count: 142, description: "Primary care and general health concerns." },
  { id: "spec_cardio", name: "Cardiology", icon: "Heart", doctor_count: 45, description: "Heart and cardiovascular system specialists." },
  { id: "spec_derma", name: "Dermatology", icon: "Sparkles", doctor_count: 38, description: "Skin, hair, and nail conditions." },
  { id: "spec_neuro", name: "Neurology", icon: "Brain", doctor_count: 29, description: "Brain, spinal cord, and nervous system." },
  { id: "spec_pedia", name: "Pediatrics", icon: "Baby", doctor_count: 86, description: "Medical care for infants, children, and adolescents." },
  { id: "spec_psych", name: "Psychiatry", icon: "BrainCircuit", doctor_count: 52, description: "Mental health, emotional and behavioral disorders." },
  { id: "spec_ortho", name: "Orthopedics", icon: "Bone", doctor_count: 41, description: "Musculoskeletal system, bones, and joints." },
  { id: "spec_gyne", name: "Gynecology", icon: "Activity", doctor_count: 63, description: "Women's reproductive health." },
  { id: "spec_endo", name: "Endocrinology", icon: "Dna", doctor_count: 22, description: "Hormones and metabolic disorders." },
  { id: "spec_onco", name: "Oncology", icon: "Microscope", doctor_count: 18, description: "Cancer diagnosis and treatment." }
];

export const doctors = [
  {
    id: "doc_01",
    name: "Dr. Emily Chen",
    specialty_id: "spec_cardio",
    specialty_name: "Cardiology",
    rating: 4.9,
    reviews_count: 342,
    next_available: "2024-05-22T09:00:00Z",
    avatar: "https://images.unsplash.com/photo-1559839734-2b71ea197ec2?auto=format&fit=crop&w=300&q=80",
    bio: "Board-certified cardiologist with over 15 years of experience specializing in preventive cardiology and heart failure management.",
    education: "Harvard Medical School",
    experience_years: 15,
    consultation_fee: 150,
    languages: ["English", "Mandarin"]
  },
  {
    id: "doc_02",
    name: "Dr. Marcus Johnson",
    specialty_id: "spec_gp",
    specialty_name: "General Practice",
    rating: 4.8,
    reviews_count: 512,
    next_available: "2024-05-20T14:30:00Z",
    avatar: "https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?auto=format&fit=crop&w=300&q=80",
    bio: "Dedicated general practitioner focused on comprehensive family medicine and holistic patient care.",
    education: "Johns Hopkins University",
    experience_years: 12,
    consultation_fee: 90,
    languages: ["English", "Spanish"]
  },
  {
    id: "doc_03",
    name: "Dr. Sarah Al-Fayed",
    specialty_id: "spec_neuro",
    specialty_name: "Neurology",
    rating: 4.9,
    reviews_count: 215,
    next_available: "2024-05-25T10:00:00Z",
    avatar: "https://images.unsplash.com/photo-1594824436998-058a23116fc7?auto=format&fit=crop&w=300&q=80",
    bio: "Expert neurologist specializing in migraine management, epilepsy, and neurodegenerative disorders.",
    education: "Oxford University",
    experience_years: 18,
    consultation_fee: 200,
    languages: ["English", "Arabic"]
  },
  {
    id: "doc_04",
    name: "Dr. James Wilson",
    specialty_id: "spec_ortho",
    specialty_name: "Orthopedics",
    rating: 4.7,
    reviews_count: 189,
    next_available: "2024-05-21T11:15:00Z",
    avatar: "https://images.unsplash.com/photo-1622253692010-333f2da6031d?auto=format&fit=crop&w=300&q=80",
    bio: "Orthopedic surgeon with a focus on sports injuries, joint replacement, and minimally invasive arthroscopy.",
    education: "Stanford University",
    experience_years: 20,
    consultation_fee: 180,
    languages: ["English"]
  },
  {
    id: "doc_05",
    name: "Dr. Aisha Patel",
    specialty_id: "spec_pedia",
    specialty_name: "Pediatrics",
    rating: 5.0,
    reviews_count: 420,
    next_available: "2024-05-20T08:30:00Z",
    avatar: "https://images.unsplash.com/photo-1614608682850-e0d6ed316d47?auto=format&fit=crop&w=300&q=80",
    bio: "Compassionate pediatrician dedicated to child wellness, developmental monitoring, and pediatric nutrition.",
    education: "University of Pennsylvania",
    experience_years: 10,
    consultation_fee: 110,
    languages: ["English", "Hindi", "Gujarati"]
  },
  {
    id: "doc_06",
    name: "Dr. Robert Kim",
    specialty_id: "spec_psych",
    specialty_name: "Psychiatry",
    rating: 4.8,
    reviews_count: 156,
    next_available: "2024-05-23T15:00:00Z",
    avatar: "https://images.unsplash.com/photo-1537368910025-700350fe46c7?auto=format&fit=crop&w=300&q=80",
    bio: "Psychiatrist specializing in anxiety, depression, and cognitive behavioral therapy approaches.",
    education: "Yale School of Medicine",
    experience_years: 14,
    consultation_fee: 160,
    languages: ["English", "Korean"]
  },
  {
    id: "doc_07",
    name: "Dr. Elena Rodriguez",
    specialty_id: "spec_derma",
    specialty_name: "Dermatology",
    rating: 4.9,
    reviews_count: 310,
    next_available: "2024-05-24T13:45:00Z",
    avatar: "https://images.unsplash.com/photo-1527613426441-4da17471b66d?auto=format&fit=crop&w=300&q=80",
    bio: "Expert in medical and cosmetic dermatology, focusing on acne treatment, skin cancer screening, and anti-aging.",
    education: "UCLA Medical Center",
    experience_years: 9,
    consultation_fee: 140,
    languages: ["English", "Spanish"]
  },
  {
    id: "doc_08",
    name: "Dr. Michael Chang",
    specialty_id: "spec_endo",
    specialty_name: "Endocrinology",
    rating: 4.6,
    reviews_count: 128,
    next_available: "2024-05-28T09:30:00Z",
    avatar: "https://images.unsplash.com/photo-1605684954998-685c79d6a018?auto=format&fit=crop&w=300&q=80",
    bio: "Specialist in diabetes management, thyroid disorders, and metabolic syndrome.",
    education: "University of Chicago",
    experience_years: 16,
    consultation_fee: 175,
    languages: ["English"]
  },
  {
    id: "doc_09",
    name: "Dr. William Davies",
    specialty_id: "spec_onco",
    specialty_name: "Oncology",
    rating: 4.9,
    reviews_count: 89,
    next_available: "2024-05-30T10:00:00Z",
    avatar: "https://images.unsplash.com/photo-1582750433449-648ed127c09e?auto=format&fit=crop&w=300&q=80",
    bio: "Leading oncologist with expertise in targeted therapies and personalized cancer treatment plans.",
    education: "Duke University",
    experience_years: 22,
    consultation_fee: 250,
    languages: ["English"]
  },
  {
    id: "doc_10",
    name: "Dr. Olivia Martinez",
    specialty_id: "spec_gyne",
    specialty_name: "Gynecology",
    rating: 4.8,
    reviews_count: 275,
    next_available: "2024-05-22T14:00:00Z",
    avatar: "https://images.unsplash.com/photo-1550831107-1553da8c8464?auto=format&fit=crop&w=300&q=80",
    bio: "Dedicated to women's health, offering comprehensive gynecological care, family planning, and menopause management.",
    education: "Columbia University",
    experience_years: 11,
    consultation_fee: 130,
    languages: ["English", "Spanish"]
  },
  {
    id: "doc_11",
    name: "Dr. David Thompson",
    specialty_id: "spec_cardio",
    specialty_name: "Cardiology",
    rating: 4.7,
    reviews_count: 198,
    next_available: "2024-05-26T11:00:00Z",
    avatar: "https://picsum.photos/seed/doc11/300/300",
    bio: "Interventional cardiologist specializing in minimally invasive procedures and structural heart disease.",
    education: "University of Michigan",
    experience_years: 19,
    consultation_fee: 160,
    languages: ["English"]
  },
  {
    id: "doc_12",
    name: "Dr. Sophia Lee",
    specialty_id: "spec_derma",
    specialty_name: "Dermatology",
    rating: 4.9,
    reviews_count: 412,
    next_available: "2024-05-21T09:15:00Z",
    avatar: "https://picsum.photos/seed/doc12/300/300",
    bio: "Renowned dermatologist with a passion for treating complex skin conditions and pediatric dermatology.",
    education: "NYU Grossman School of Medicine",
    experience_years: 13,
    consultation_fee: 145,
    languages: ["English", "Korean"]
  },
  {
    id: "doc_13",
    name: "Dr. Richard Wright",
    specialty_id: "spec_gp",
    specialty_name: "General Practice",
    rating: 4.5,
    reviews_count: 320,
    next_available: "2024-05-19T16:00:00Z",
    avatar: "https://picsum.photos/seed/doc13/300/300",
    bio: "Experienced family physician providing comprehensive care for patients of all ages.",
    education: "University of Washington",
    experience_years: 25,
    consultation_fee: 85,
    languages: ["English"]
  },
  {
    id: "doc_14",
    name: "Dr. Isabella Rossi",
    specialty_id: "spec_pedia",
    specialty_name: "Pediatrics",
    rating: 4.8,
    reviews_count: 245,
    next_available: "2024-05-23T10:30:00Z",
    avatar: "https://picsum.photos/seed/doc14/300/300",
    bio: "Pediatrician with a special interest in childhood asthma, allergies, and immunology.",
    education: "Boston University",
    experience_years: 8,
    consultation_fee: 115,
    languages: ["English", "Italian"]
  },
  {
    id: "doc_15",
    name: "Dr. Thomas Anderson",
    specialty_id: "spec_neuro",
    specialty_name: "Neurology",
    rating: 4.7,
    reviews_count: 167,
    next_available: "2024-05-27T13:00:00Z",
    avatar: "https://picsum.photos/seed/doc15/300/300",
    bio: "Neurologist focused on stroke prevention, recovery, and neuromuscular disorders.",
    education: "Northwestern University",
    experience_years: 17,
    consultation_fee: 190,
    languages: ["English"]
  }
];

export const appointments = [
  {
    id: "apt_01",
    doctor_id: "doc_01",
    date: "2024-05-22T09:00:00Z",
    status: "upcoming",
    type: "video",
    reason: "Routine heart checkup",
    ai_summary: null,
    notes: null
  },
  {
    id: "apt_02",
    doctor_id: "doc_07",
    date: "2024-05-24T13:45:00Z",
    status: "upcoming",
    type: "in-person",
    reason: "Skin rash consultation",
    ai_summary: null,
    notes: null
  },
  {
    id: "apt_03",
    doctor_id: "doc_02",
    date: "2024-04-15T10:00:00Z",
    status: "completed",
    type: "video",
    reason: "Annual physical follow-up",
    ai_summary: "Patient reported mild fatigue. Blood pressure is normal (118/76). Recommended increasing water intake and maintaining current Lisinopril dosage. Scheduled next follow-up in 6 months.",
    notes: "Patient doing well. No new complaints."
  },
  {
    id: "apt_04",
    doctor_id: "doc_04",
    date: "2024-03-10T14:30:00Z",
    status: "completed",
    type: "in-person",
    reason: "Knee pain",
    ai_summary: "Diagnosis of mild osteoarthritis in right knee. Prescribed physical therapy exercises and topical anti-inflammatory gel. Advised to avoid high-impact sports for 4 weeks.",
    notes: "X-rays show mild joint space narrowing."
  },
  {
    id: "apt_05",
    doctor_id: "doc_06",
    date: "2024-02-20T11:00:00Z",
    status: "completed",
    type: "video",
    reason: "Anxiety management",
    ai_summary: "Patient reports improved sleep and reduced anxiety levels. Continuing current CBT techniques. No medication changes required.",
    notes: "Progressing well with mindfulness exercises."
  },
  {
    id: "apt_06",
    doctor_id: "doc_08",
    date: "2024-01-05T09:15:00Z",
    status: "completed",
    type: "in-person",
    reason: "Thyroid screening",
    ai_summary: "TSH levels are within normal range. No signs of hypothyroidism. Advised to maintain a balanced diet rich in iodine.",
    notes: "Lab results reviewed with patient."
  },
  {
    id: "apt_07",
    doctor_id: "doc_01",
    date: "2023-11-12T15:45:00Z",
    status: "completed",
    type: "video",
    reason: "Blood pressure review",
    ai_summary: "Blood pressure slightly elevated (135/85). Adjusted Lisinopril dosage to 10mg daily. Emphasized low-sodium diet.",
    notes: "Patient to monitor BP at home weekly."
  },
  {
    id: "apt_08",
    doctor_id: "doc_10",
    date: "2024-05-10T10:30:00Z",
    status: "cancelled",
    type: "in-person",
    reason: "Scheduling conflict",
    ai_summary: null,
    notes: "Patient cancelled via app."
  },
  {
    id: "apt_09",
    doctor_id: "doc_03",
    date: "2023-09-28T13:00:00Z",
    status: "completed",
    type: "video",
    reason: "Migraine consultation",
    ai_summary: "Patient experiencing 2-3 migraines per month. Identified stress and lack of sleep as primary triggers. Prescribed Sumatriptan for acute attacks.",
    notes: "Provided migraine diary template."
  },
  {
    id: "apt_10",
    doctor_id: "doc_13",
    date: "2023-08-14T08:45:00Z",
    status: "completed",
    type: "in-person",
    reason: "Flu symptoms",
    ai_summary: "Diagnosed with viral upper respiratory infection. Recommended rest, hydration, and OTC symptom relief. No antibiotics prescribed.",
    notes: "Rapid flu test negative."
  },
  {
    id: "apt_11",
    doctor_id: "doc_05",
    date: "2023-06-22T14:15:00Z",
    status: "completed",
    type: "video",
    reason: "Pediatric consultation (Child)",
    ai_summary: "Child is meeting all developmental milestones. Discussed introduction of solid foods and sleep training techniques.",
    notes: "Weight and height in 75th percentile."
  },
  {
    id: "apt_12",
    doctor_id: "doc_12",
    date: "2023-05-05T11:30:00Z",
    status: "completed",
    type: "in-person",
    reason: "Mole check",
    ai_summary: "Full body skin exam completed. Two benign nevi noted on back. No suspicious lesions. Advised daily sunscreen use.",
    notes: "Photos taken for baseline."
  },
  {
    id: "apt_13",
    doctor_id: "doc_02",
    date: "2024-06-05T10:00:00Z",
    status: "upcoming",
    type: "video",
    reason: "Medication refill review",
    ai_summary: null,
    notes: null
  },
  {
    id: "apt_14",
    doctor_id: "doc_09",
    date: "2023-03-18T09:00:00Z",
    status: "completed",
    type: "in-person",
    reason: "Oncology screening",
    ai_summary: "Routine screening completed. All markers are negative. Patient is in good health.",
    notes: "Next screening in 5 years."
  },
  {
    id: "apt_15",
    doctor_id: "doc_15",
    date: "2023-01-25T15:30:00Z",
    status: "completed",
    type: "video",
    reason: "Numbness in fingers",
    ai_summary: "Symptoms consistent with mild carpal tunnel syndrome. Recommended ergonomic workspace adjustments and wrist splints at night.",
    notes: "Nerve conduction study not required at this time."
  },
  {
    id: "apt_16",
    doctor_id: "doc_11",
    date: "2022-12-10T14:00:00Z",
    status: "completed",
    type: "in-person",
    reason: "Echocardiogram review",
    ai_summary: "Echo results are normal. Ejection fraction is 60%. No structural abnormalities detected.",
    notes: "Patient relieved with results."
  },
  {
    id: "apt_17",
    doctor_id: "doc_14",
    date: "2022-10-05T10:45:00Z",
    status: "completed",
    type: "video",
    reason: "Allergy consultation",
    ai_summary: "Patient experiencing seasonal allergic rhinitis. Prescribed daily Cetirizine and Fluticasone nasal spray.",
    notes: "Discussed allergen avoidance strategies."
  },
  {
    id: "apt_18",
    doctor_id: "doc_04",
    date: "2024-06-15T13:00:00Z",
    status: "upcoming",
    type: "in-person",
    reason: "Knee follow-up",
    ai_summary: null,
    notes: null
  },
  {
    id: "apt_19",
    doctor_id: "doc_06",
    date: "2024-05-01T16:00:00Z",
    status: "cancelled",
    type: "video",
    reason: "Forgot appointment",
    ai_summary: null,
    notes: "No-show."
  },
  {
    id: "apt_20",
    doctor_id: "doc_07",
    date: "2022-08-20T09:30:00Z",
    status: "completed",
    type: "in-person",
    reason: "Acne treatment",
    ai_summary: "Started patient on topical tretinoin and clindamycin. Discussed expected purging phase and importance of moisturization.",
    notes: "Follow-up in 12 weeks."
  }
];

export const ai_insights = [
  {
    id: "ins_01",
    type: "alert",
    title: "Blood Pressure Trend",
    description: "Your recent readings show a slight upward trend in your blood pressure. Consider scheduling a follow-up with Dr. Chen.",
    date: "2024-05-17T09:15:00Z",
    severity: "medium",
    action_link: "/booking?doctor=doc_01"
  },
  {
    id: "ins_02",
    type: "reminder",
    title: "Annual Checkup Due",
    description: "It's been almost a year since your last comprehensive physical. Time to book your annual checkup.",
    date: "2024-05-15T10:00:00Z",
    severity: "low",
    action_link: "/booking?specialty=spec_gp"
  },
  {
    id: "ins_03",
    type: "tip",
    title: "Vitamin D Optimization",
    description: "Based on your recent fatigue reports and the current season, ensuring adequate Vitamin D intake could boost your energy levels.",
    date: "2024-05-10T14:20:00Z",
    severity: "low",
    action_link: null
  },
  {
    id: "ins_04",
    type: "milestone",
    title: "Activity Goal Reached!",
    description: "Great job! You've maintained your daily step goal of 10,000 steps for 14 consecutive days. This significantly supports your cardiovascular health.",
    date: "2024-05-08T18:00:00Z",
    severity: "low",
    action_link: null
  },
  {
    id: "ins_05",
    type: "reminder",
    title: "Medication Refill",
    description: "Your Lisinopril prescription is running low. Request a refill to ensure no interruption in your treatment.",
    date: "2024-05-05T08:00:00Z",
    severity: "high",
    action_link: "/dashboard"
  },
  {
    id: "ins_06",
    type: "alert",
    title: "Sleep Pattern Irregularity",
    description: "Your connected wearable indicates irregular sleep patterns over the last week. Consistent sleep is crucial for recovery.",
    date: "2024-04-28T07:30:00Z",
    severity: "medium",
    action_link: null
  },
  {
    id: "ins_07",
    type: "tip",
    title: "Hydration Reminder",
    description: "The local weather forecast predicts high temperatures this week. Remember to increase your water intake to stay hydrated.",
    date: "2024-04-20T12:00:00Z",
    severity: "low",
    action_link: null
  },
  {
    id: "ins_08",
    type: "recommendation",
    title: "Specialist Match",
    description: "Based on your recurring notes about joint stiffness, Omnia AI recommends consulting an Orthopedic specialist.",
    date: "2024-04-10T11:45:00Z",
    severity: "medium",
    action_link: "/directory?specialty=spec_ortho"
  }
];

export const testimonials = [
  {
    id: "test_01",
    author: "Michael T.",
    rating: 5,
    text: "Dr. Chen is phenomenal. The AI summary after my visit was incredibly detailed. I finally understand my treatment plan.",
    doctor_id: "doc_01",
    date: "2024-04-12T00:00:00Z"
  },
  {
    id: "test_02",
    author: "Sarah W.",
    rating: 5,
    text: "Dr. Johnson was attentive and the video quality was perfect. Highly recommend Omnia for quick consultations.",
    doctor_id: "doc_02",
    date: "2024-03-28T00:00:00Z"
  },
  {
    id: "test_03",
    author: "David L.",
    rating: 4,
    text: "Very knowledgeable and took the time to explain my MRI results in plain English.",
    doctor_id: "doc_03",
    date: "2024-02-15T00:00:00Z"
  },
  {
    id: "test_04",
    author: "Emma R.",
    rating: 5,
    text: "My knee feels 100% better after following Dr. Wilson's physical therapy plan. Great bedside manner.",
    doctor_id: "doc_04",
    date: "2024-01-20T00:00:00Z"
  },
  {
    id: "test_05",
    author: "James P.",
    rating: 5,
    text: "Dr. Patel is amazing with kids. My daughter actually looks forward to her checkups now!",
    doctor_id: "doc_05",
    date: "2023-12-10T00:00:00Z"
  },
  {
    id: "test_06",
    author: "Linda K.",
    rating: 4,
    text: "Very empathetic and provided practical strategies for managing my anxiety. The platform is very easy to use.",
    doctor_id: "doc_06",
    date: "2023-11-05T00:00:00Z"
  },
  {
    id: "test_07",
    author: "Robert B.",
    rating: 5,
    text: "Cleared up my skin issues in just a few weeks. Dr. Rodriguez really knows her stuff.",
    doctor_id: "doc_07",
    date: "2023-10-18T00:00:00Z"
  },
  {
    id: "test_08",
    author: "Jennifer M.",
    rating: 5,
    text: "Thorough and professional. I appreciate the holistic approach to managing my diabetes.",
    doctor_id: "doc_08",
    date: "2023-09-22T00:00:00Z"
  },
  {
    id: "test_09",
    author: "William H.",
    rating: 5,
    text: "An exceptional oncologist. Compassionate, clear, and incredibly supportive throughout my treatment.",
    doctor_id: "doc_09",
    date: "2023-08-30T00:00:00Z"
  },
  {
    id: "test_10",
    author: "Amanda C.",
    rating: 4,
    text: "Made me feel very comfortable during my visit. Answered all my questions without rushing.",
    doctor_id: "doc_10",
    date: "2023-07-14T00:00:00Z"
  },
  {
    id: "test_11",
    author: "Thomas G.",
    rating: 5,
    text: "The AI insights on the app combined with Dr. Chen's expertise have completely transformed my heart health.",
    doctor_id: "doc_01",
    date: "2023-06-05T00:00:00Z"
  },
  {
    id: "test_12",
    author: "Jessica F.",
    rating: 5,
    text: "Booking was a breeze and the consultation started exactly on time. Excellent service.",
    doctor_id: "doc_02",
    date: "2023-05-12T00:00:00Z"
  }
];

// Helper Functions
export const getPatientProfile = () => patient_profile;

export const getDashboardSummary = () => dashboard_summary;

export const getAllSpecialties = () => specialties;

export const getAllDoctors = () => doctors;

export const getDoctorById = (id) => doctors.find(doc => doc.id === id);

export const getDoctorsBySpecialty = (specialtyId) => doctors.filter(doc => doc.specialty_id === specialtyId);

export const getAllAppointments = () => {
  return appointments.map(apt => ({
    ...apt,
    doctor: getDoctorById(apt.doctor_id)
  })).sort((a, b) => new Date(b.date) - new Date(a.date));
};

export const getAppointmentsByStatus = (status) => {
  return getAllAppointments().filter(apt => apt.status === status);
};

export const getUpcomingAppointments = () => getAppointmentsByStatus('upcoming');

export const getPastAppointments = () => getAppointmentsByStatus('completed');

export const getAllInsights = () => {
  return [...ai_insights].sort((a, b) => new Date(b.date) - new Date(a.date));
};

export const getDoctorReviews = (doctorId) => {
  return testimonials.filter(test => test.doctor_id === doctorId).sort((a, b) => new Date(b.date) - new Date(a.date));
};