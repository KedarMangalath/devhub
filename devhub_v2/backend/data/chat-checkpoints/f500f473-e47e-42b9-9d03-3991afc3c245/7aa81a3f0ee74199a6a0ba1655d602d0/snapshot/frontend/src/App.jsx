import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, MapPin, ShieldPlus, Video, Building2, TestTube, Pill, Star, ChevronRight, CheckCircle, Activity, Heart, Users, Calendar, Phone, Mail, FileText, ArrowRight, Quote } from 'lucide-react';
import AppointmentModal from './components/AppointmentModal';

const API_BASE = 'http://localhost:8000/api';

const iconMap = {
  Video: Video,
  Building2: Building2,
  TestTube: TestTube,
  Pill: Pill,
  ShieldPlus: ShieldPlus,
  Star: Star
};

function App() {
  const [doctors, setDoctors] = useState([]);
  const [services, setServices] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedDoctor, setSelectedDoctor] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [docsRes, servRes] = await Promise.all([
          axios.get(`${API_BASE}/doctors/`),
          axios.get(`${API_BASE}/services/`)
        ]);
        setDoctors(docsRes.data);
        setServices(servRes.data);
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };
    fetchData();
  }, []);

  const openModal = (doctor) => {
    setSelectedDoctor(doctor);
    setIsModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="border-b border-gray-100 sticky top-0 bg-white z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-20 items-center">
            <div className="flex items-center gap-2">
              <ShieldPlus className="h-8 w-8 text-brand-600" />
              <span className="text-2xl font-bold text-gray-900 tracking-tight">Omnia</span>
            </div>
            <div className="hidden md:flex space-x-8">
              <a href="#" className="text-gray-600 hover:text-brand-600 font-medium">Find Doctors</a>
              <a href="#" className="text-gray-600 hover:text-brand-600 font-medium">Video Consult</a>
              <a href="#" className="text-gray-600 hover:text-brand-600 font-medium">Medicines</a>
              <a href="#" className="text-gray-600 hover:text-brand-600 font-medium">Lab Tests</a>
            </div>
            <div className="flex items-center space-x-4">
              <button className="text-gray-600 font-medium hover:text-gray-900">Login / Signup</button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="bg-brand-50 py-16 sm:py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 tracking-tight mb-6">
              Your Health, Our Priority
            </h1>
            <p className="text-lg text-gray-600 mb-10">
              Book appointments with the best doctors, consult online, and order medicines—all in one place.
            </p>
            
            {/* Search Bar */}
            <div className="bg-white p-2 rounded-full shadow-lg flex flex-col sm:flex-row items-center max-w-4xl mx-auto border border-gray-100">
              <div className="flex items-center flex-1 px-4 py-2 w-full sm:w-auto border-b sm:border-b-0 sm:border-r border-gray-200">
                <MapPin className="h-5 w-5 text-gray-400 mr-3" />
                <input type="text" placeholder="New York, NY" className="w-full outline-none text-gray-700 placeholder-gray-400" />
              </div>
              <div className="flex items-center flex-1 px-4 py-2 w-full sm:w-auto">
                <Search className="h-5 w-5 text-gray-400 mr-3" />
                <input type="text" placeholder="Search doctors, clinics, hospitals..." className="w-full outline-none text-gray-700 placeholder-gray-400" />
              </div>
              <button className="w-full sm:w-auto mt-2 sm:mt-0 bg-brand-600 text-white px-8 py-3 rounded-full font-semibold hover:bg-brand-700 transition-colors">
                Search
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Section */}
      <div className="bg-brand-600 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div className="text-white">
              <div className="text-4xl font-extrabold mb-2">10k+</div>
              <div className="text-brand-100 font-medium">Happy Patients</div>
            </div>
            <div className="text-white">
              <div className="text-4xl font-extrabold mb-2">500+</div>
              <div className="text-brand-100 font-medium">Expert Doctors</div>
            </div>
            <div className="text-white">
              <div className="text-4xl font-extrabold mb-2">50+</div>
              <div className="text-brand-100 font-medium">Specialties</div>
            </div>
            <div className="text-white">
              <div className="text-4xl font-extrabold mb-2">4.9/5</div>
              <div className="text-brand-100 font-medium">Average Rating</div>
            </div>
          </div>
        </div>
      </div>

      {/* Services Section */}
      <div className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-8">Our Services</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {services.map(service => {
              const IconComponent = iconMap[service.icon_name] || Building2;
              return (
                <div key={service.id} className="p-6 rounded-2xl border border-gray-100 hover:shadow-xl transition-shadow bg-white group cursor-pointer">
                  <div className="h-12 w-12 bg-brand-50 rounded-xl flex items-center justify-center mb-4 group-hover:bg-brand-600 transition-colors">
                    <IconComponent className="h-6 w-6 text-brand-600 group-hover:text-white transition-colors" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{service.name}</h3>
                  <p className="text-sm text-gray-500">{service.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* How it Works */}
      <div className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900">How Omnia Works</h2>
            <p className="text-gray-500 mt-4 max-w-2xl mx-auto">Get the care you need in three simple steps. We've made it easier than ever to connect with top healthcare professionals.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            <div className="hidden md:block absolute top-12 left-[16%] right-[16%] h-0.5 bg-brand-200 z-0"></div>
            <div className="relative z-10 flex flex-col items-center text-center">
              <div className="w-24 h-24 bg-white rounded-full border-4 border-brand-100 flex items-center justify-center mb-6 shadow-sm">
                <Search className="h-10 w-10 text-brand-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">1. Find a Doctor</h3>
              <p className="text-gray-500">Search by specialty, location, or doctor's name to find the perfect match for your needs.</p>
            </div>
            <div className="relative z-10 flex flex-col items-center text-center">
              <div className="w-24 h-24 bg-white rounded-full border-4 border-brand-100 flex items-center justify-center mb-6 shadow-sm">
                <Calendar className="h-10 w-10 text-brand-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">2. Book Appointment</h3>
              <p className="text-gray-500">Choose a convenient time slot and book your appointment instantly online.</p>
            </div>
            <div className="relative z-10 flex flex-col items-center text-center">
              <div className="w-24 h-24 bg-white rounded-full border-4 border-brand-100 flex items-center justify-center mb-6 shadow-sm">
                <Activity className="h-10 w-10 text-brand-600" />
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">3. Get Care</h3>
              <p className="text-gray-500">Consult with your doctor in-person or via video call and get your personalized treatment plan.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Doctors Section */}
      <div className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-end mb-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Top Specialists</h2>
              <p className="text-gray-500 mt-2">Book confirmed appointments with highly rated doctors</p>
            </div>
            <button className="hidden sm:flex items-center text-brand-600 font-medium hover:text-brand-700">
              View all <ChevronRight className="h-4 w-4 ml-1" />
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {doctors.map(doctor => (
              <div key={doctor.id} className="bg-white rounded-2xl overflow-hidden border border-gray-100 hover:shadow-lg transition-shadow">
                <img src={doctor.image_url} alt={doctor.name} className="w-full h-48 object-cover" />
                <div className="p-5">
                  <h3 className="text-lg font-bold text-gray-900">{doctor.name}</h3>
                  <p className="text-brand-600 font-medium text-sm mb-2">{doctor.specialty}</p>
                  <div className="flex items-center text-sm text-gray-500 mb-4">
                    <Star className="h-4 w-4 text-yellow-400 fill-current mr-1" />
                    <span className="font-medium text-gray-700 mr-2">4.9</span>
                    <span>• {doctor.experience_years} yrs exp</span>
                  </div>
                  <button 
                    onClick={() => openModal(doctor)}
                    className="w-full py-2.5 border-2 border-brand-600 text-brand-600 rounded-xl font-semibold hover:bg-brand-600 hover:text-white transition-colors"
                  >
                    Book Appointment
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Testimonials */}
      <div className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900">What Our Patients Say</h2>
            <p className="text-gray-500 mt-4">Real stories from people who found the right care through Omnia.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { name: "Sarah Johnson", text: "Finding a specialist was so easy. The video consultation saved me a trip to the clinic when I was feeling too sick to travel.", role: "Patient" },
              { name: "Mark Davis", text: "I've been using Omnia for all my family's healthcare needs. The medicine delivery is incredibly fast and reliable.", role: "Father of two" },
              { name: "Emily Chen", text: "The doctors here are top-notch. I got a second opinion that completely changed my treatment plan for the better.", role: "Patient" }
            ].map((testimonial, idx) => (
              <div key={idx} className="bg-brand-50 p-8 rounded-2xl relative">
                <Quote className="h-8 w-8 text-brand-200 absolute top-6 left-6" />
                <div className="relative z-10 pt-6">
                  <p className="text-gray-700 italic mb-6">"{testimonial.text}"</p>
                  <div className="flex items-center">
                    <div className="w-10 h-10 bg-brand-200 rounded-full flex items-center justify-center text-brand-700 font-bold mr-3">
                      {testimonial.name.charAt(0)}
                    </div>
                    <div>
                      <h4 className="font-bold text-gray-900">{testimonial.name}</h4>
                      <p className="text-sm text-gray-500">{testimonial.role}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Health Articles */}
      <div className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-end mb-8">
            <div>
              <h2 className="text-3xl font-bold text-gray-900">Health & Wellness</h2>
              <p className="text-gray-500 mt-2">Latest articles and tips from our medical experts</p>
            </div>
            <button className="hidden sm:flex items-center text-brand-600 font-medium hover:text-brand-700">
              Read all articles <ArrowRight className="h-4 w-4 ml-1" />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { title: "10 Tips for a Healthy Heart", category: "Cardiology", image: "https://images.unsplash.com/photo-1505576399279-565b52d4ac71?auto=format&fit=crop&q=80&w=400&h=250", date: "Oct 12, 2023" },
              { title: "Understanding Mental Health", category: "Psychiatry", image: "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&q=80&w=400&h=250", date: "Oct 10, 2023" },
              { title: "Nutrition Basics for Kids", category: "Pediatrics", image: "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&q=80&w=400&h=250", date: "Oct 08, 2023" }
            ].map((article, idx) => (
              <div key={idx} className="bg-white rounded-2xl overflow-hidden border border-gray-100 hover:shadow-lg transition-shadow cursor-pointer group">
                <div className="overflow-hidden h-48">
                  <img src={article.image} alt={article.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                </div>
                <div className="p-6">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-brand-600 bg-brand-50 px-3 py-1 rounded-full">{article.category}</span>
                    <span className="text-xs text-gray-500">{article.date}</span>
                  </div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-brand-600 transition-colors">{article.title}</h3>
                  <p className="text-gray-500 text-sm mb-4">Discover essential tips and insights from our leading specialists to help you maintain optimal health.</p>
                  <div className="flex items-center text-brand-600 font-medium text-sm">
                    Read more <ArrowRight className="h-4 w-4 ml-1" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Download App CTA */}
      <div className="bg-brand-600 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between">
            <div className="md:w-1/2 text-white mb-8 md:mb-0">
              <h2 className="text-3xl sm:text-4xl font-extrabold mb-4">Get the Omnia App</h2>
              <p className="text-brand-100 text-lg mb-8 max-w-lg">
                Book appointments, consult doctors online, and manage your health records on the go. Download our app today.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                <button className="bg-gray-900 text-white px-6 py-3 rounded-xl font-semibold hover:bg-black transition-colors flex items-center justify-center">
                  <span className="mr-2">App Store</span>
                </button>
                <button className="bg-white text-gray-900 px-6 py-3 rounded-xl font-semibold hover:bg-gray-50 transition-colors flex items-center justify-center">
                  <span className="mr-2">Google Play</span>
                </button>
              </div>
            </div>
            <div className="md:w-1/3">
              <div className="bg-brand-500 rounded-3xl p-8 shadow-2xl transform rotate-3">
                <div className="bg-white rounded-2xl p-4 shadow-inner">
                  <div className="flex items-center gap-3 mb-6">
                    <ShieldPlus className="h-8 w-8 text-brand-600" />
                    <span className="text-xl font-bold text-gray-900">Omnia</span>
                  </div>
                  <div className="space-y-4">
                    <div className="h-12 bg-gray-100 rounded-xl w-full"></div>
                    <div className="h-24 bg-gray-100 rounded-xl w-full"></div>
                    <div className="h-12 bg-gray-100 rounded-xl w-full"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-4 gap-8">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <ShieldPlus className="h-6 w-6 text-brand-500" />
              <span className="text-xl font-bold tracking-tight">Omnia</span>
            </div>
            <p className="text-gray-400 text-sm">Making quality healthcare accessible to everyone, everywhere.</p>
          </div>
          <div>
            <h4 className="font-semibold mb-4">For Patients</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><a href="#" className="hover:text-white">Search for Doctors</a></li>
              <li><a href="#" className="hover:text-white">Search for Clinics</a></li>
              <li><a href="#" className="hover:text-white">Book Diagnostic Tests</a></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold mb-4">For Providers</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li><a href="#" className="hover:text-white">Omnia Profile</a></li>
              <li><a href="#" className="hover:text-white">Omnia Consult</a></li>
              <li><a href="#" className="hover:text-white">Omnia Health Feed</a></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold mb-4">Contact</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li>support@omniahealth.com</li>
              <li>1-800-OMNIA-CARE</li>
            </ul>
          </div>
        </div>
      </footer>

      {isModalOpen && (
        <AppointmentModal 
          doctor={selectedDoctor} 
          onClose={() => setIsModalOpen(false)} 
          apiBase={API_BASE}
        />
      )}
    </div>
  );
}

export default App;
