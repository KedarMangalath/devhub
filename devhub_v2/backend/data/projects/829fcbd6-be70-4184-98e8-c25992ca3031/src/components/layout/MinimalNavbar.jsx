import React from 'react'
import { Link } from 'react-router-dom'
import { Shield, ArrowLeft } from 'lucide-react'

export default function MinimalNavbar() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo Section */}
          <div className="flex-shrink-0">
            <Link 
              to="/" 
              className="flex items-center gap-2.5 transition-opacity hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-lg"
              aria-label="Go to Vigilance C3MS Home"
            >
              <div className="flex items-center justify-center w-8 h-8 rounded-md bg-primary shadow-sm">
                <Shield className="w-5 h-5 text-white" aria-hidden="true" />
              </div>
              <span className="font-display font-bold text-xl tracking-tight text-foreground hidden sm:block">
                Vigilance <span className="text-primary">C3MS</span>
              </span>
            </Link>
          </div>

          {/* Navigation Action */}
          <div className="flex items-center">
            <Link
              to="/"
              className="group flex items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground transition-all duration-200 rounded-md hover:text-foreground hover:bg-secondary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
            >
              <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" aria-hidden="true" />
              <span>Back to Home</span>
            </Link>
          </div>
        </div>
      </div>
    </header>
  )
}