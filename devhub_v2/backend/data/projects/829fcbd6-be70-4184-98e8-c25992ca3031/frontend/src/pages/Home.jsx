import { Link } from 'react-router-dom';
import { ShieldAlert, Search, Lock, BrainCircuit } from 'lucide-react';

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="text-center py-12 px-4 sm:px-6 lg:px-8 bg-white rounded-2xl shadow-sm border border-gray-100">
        <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight sm:text-5xl">
          Citizen-Centric Anti-Corruption
          <span className="block text-vacb-600">Complaint Management System</span>
        </h1>
        <p className="mt-4 max-w-2xl text-xl text-gray-500 mx-auto">
          A secure, transparent, and AI-powered platform to report corruption in Kerala. Your identity is protected.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link to="/submit" className="px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-vacb-600 hover:bg-vacb-700 md:py-4 md:text-lg md:px-10 shadow-lg shadow-vacb-500/30">
            File a Complaint
          </Link>
          <Link to="/track" className="px-8 py-3 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 md:py-4 md:text-lg md:px-10">
            Track Status
          </Link>
        </div>
      </section>

      <section className="grid md:grid-cols-3 gap-8">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-lg flex items-center justify-center mb-4">
            <Lock size={24} />
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Secure & Anonymous</h3>
          <p className="text-gray-600">End-to-end encryption and optional anonymity ensure your identity is protected from retaliation.</p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="w-12 h-12 bg-purple-100 text-purple-600 rounded-lg flex items-center justify-center mb-4">
            <BrainCircuit size={24} />
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">AI-Powered Triage</h3>
          <p className="text-gray-600">Natural Language Processing automatically categorizes and prioritizes complaints for faster resolution.</p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="w-12 h-12 bg-green-100 text-green-600 rounded-lg flex items-center justify-center mb-4">
            <ShieldAlert size={24} />
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-2">Blockchain Audit</h3>
          <p className="text-gray-600">Tamper-proof audit logs ensure transparency and prevent manipulation of complaint records.</p>
        </div>
      </section>
    </div>
  );
}