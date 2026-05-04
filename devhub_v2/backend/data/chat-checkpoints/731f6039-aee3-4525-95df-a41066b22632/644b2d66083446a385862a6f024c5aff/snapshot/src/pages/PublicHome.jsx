import React from 'react'
import Navbar from '../components/shared/Navbar'
import Footer from '../components/shared/Footer'
import HeroSection from '../components/home/HeroSection'
import FeatureCards from '../components/home/FeatureCards'
import StatCounter from '../components/home/StatCounter'

export default function PublicHome() {
  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] font-sans text-[#0F172A] selection:bg-[#1d4ed8]/20 selection:text-[#1d4ed8]">
      <Navbar />
      
      <main className="flex-grow flex flex-col">
        <HeroSection />
        <StatCounter />
        <FeatureCards />
      </main>

      <Footer />
    </div>
  )
}