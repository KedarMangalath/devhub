import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Mail, Lock, Shield } from 'lucide-react'

export default function RegistrationForm() {
  const navigate = useNavigate()
  const [role, setRole] = useState('citizen')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [kycAccepted, setKycAccepted] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!kycAccepted) return
    
    setIsSubmitting(true)
    // Simulate network delay for realistic UX
    setTimeout(() => {
      setIsSubmitting(false)
      // Route based on selected role for demo purposes
      if (role === 'investigator') {
        navigate('/InvestigatorDashboard')
      } else {
        navigate('/Dashboard')
      }
    }, 800)
  }

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="mb-8 text-center">
        <h2 className="text-2xl font-display font-bold text-foreground mb-2">Create an Account</h2>
        <p className="text-muted-foreground font-body text-sm">
          Join the Vigilance C3MS platform to report or investigate securely.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 font-body">
        {/* Role Selection */}
        <div className="space-y-3">
          <label className="block text-sm font-medium text-foreground">I am registering as a:</label>
          <div className="grid grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => setRole('citizen')}
              className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all duration-200 ${
                role === 'citizen'
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:border-primary/30 hover:bg-secondary/50'
              }`}
            >
              <User className={`w-6 h-6 mb-2 ${role === 'citizen' ? 'text-primary' : 'text-muted-foreground'}`} />
              <span className="font-medium text-sm">Citizen</span>
            </button>
            
            <button
              type="button"
              onClick={() => setRole('investigator')}
              className={`flex flex-col items-center justify-center p-4 rounded-xl border-2 transition-all duration-200 ${
                role === 'investigator'
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:border-primary/30 hover:bg-secondary/50'
              }`}
            >
              <Shield className={`w-6 h-6 mb-2 ${role === 'investigator' ? 'text-primary' : 'text-muted-foreground'}`} />
              <span className="font-medium text-sm">Investigator</span>
            </button>
          </div>
        </div>

        {/* Input Fields */}
        <div className="space-y-4">
          <div className="relative">
            <label htmlFor="name" className="sr-only">Full Name</label>
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <User className="h-5 w-5 text-muted-foreground" />
            </div>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="block w-full pl-10 pr-3 py-3 border border-border rounded-lg bg-card text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-shadow"
              placeholder="Full Name (as per Govt ID)"
            />
          </div>

          <div className="relative">
            <label htmlFor="email" className="sr-only">Email Address</label>
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Mail className="h-5 w-5 text-muted-foreground" />
            </div>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="block w-full pl-10 pr-3 py-3 border border-border rounded-lg bg-card text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-shadow"
              placeholder="Email Address"
            />
          </div>

          <div className="relative">
            <label htmlFor="password" className="sr-only">Password</label>
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Lock className="h-5 w-5 text-muted-foreground" />
            </div>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="block w-full pl-10 pr-3 py-3 border border-border rounded-lg bg-card text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-shadow"
              placeholder="Create Password"
            />
          </div>
        </div>

        {/* KYC Notice */}
        <div className="flex items-start bg-secondary/30 p-4 rounded-lg border border-border/50">
          <div className="flex items-center h-5">
            <input
              id="kyc"
              type="checkbox"
              required
              checked={kycAccepted}
              onChange={(e) => setKycAccepted(e.target.checked)}
              className="w-4 h-4 text-primary bg-card border-border rounded focus:ring-primary focus:ring-2"
            />
          </div>
          <div className="ml-3 text-sm">
            <label htmlFor="kyc" className="font-medium text-foreground cursor-pointer">
              Mandatory KYC Verification
            </label>
            <p className="text-muted-foreground mt-1">
              I understand that to prevent misuse, my identity will be verified via Aadhaar/Govt ID. My identity will remain strictly confidential and encrypted on the blockchain.
            </p>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={!kycAccepted || isSubmitting}
          className={`w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors ${
            (!kycAccepted || isSubmitting) ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {isSubmitting ? 'Creating Account...' : 'Create Secure Account'}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-sm text-muted-foreground font-body">
          Already have an account?{' '}
          <button 
            onClick={() => navigate('/Login')}
            className="font-medium text-primary hover:text-primary/80 transition-colors"
          >
            Sign in here
          </button>
        </p>
      </div>
    </div>
  )
}