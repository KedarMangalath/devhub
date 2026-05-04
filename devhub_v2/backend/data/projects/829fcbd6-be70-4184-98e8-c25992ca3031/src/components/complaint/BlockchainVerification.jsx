import { Link as LinkIcon, Copy, Check } from 'lucide-react'
import { useState } from 'react'

export default function BlockchainVerification({ 
  hash = "0x8f2a9b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1", 
  timestamp = "2023-10-24T09:05:00Z" 
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(hash)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const formattedDate = new Date(timestamp).toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short'
  })

  return (
    <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <h3 className="font-display text-lg font-semibold text-foreground flex items-center gap-2">
          <div className="p-2 bg-primary/10 rounded-lg">
            <LinkIcon className="w-5 h-5 text-primary" />
          </div>
          Blockchain Audit Trail
        </h3>
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-700 border border-emerald-500/20">
          <Check className="w-3.5 h-3.5" />
          Verified on Chain
        </span>
      </div>

      <div className="space-y-5">
        <div>
          <p className="text-sm font-medium text-muted-foreground mb-1.5 font-body">
            Immutable Timestamp
          </p>
          <p className="text-sm text-foreground font-body font-medium">
            {formattedDate}
          </p>
        </div>

        <div>
          <p className="text-sm font-medium text-muted-foreground mb-1.5 font-body">
            Transaction Hash
          </p>
          <div className="flex items-stretch gap-2">
            <div className="flex-1 bg-secondary/50 border border-border rounded-lg p-3 overflow-x-auto flex items-center">
              <code className="text-sm font-mono text-foreground break-all">
                {hash}
              </code>
            </div>
            <button
              onClick={handleCopy}
              className="px-4 rounded-lg border border-border bg-secondary hover:bg-secondary/80 transition-colors text-muted-foreground hover:text-foreground flex-shrink-0 flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-primary/50"
              title="Copy Hash"
              aria-label="Copy blockchain hash"
            >
              {copied ? (
                <Check className="w-4 h-4 text-emerald-600" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
          </div>
          {copied && (
            <p className="text-xs text-emerald-600 mt-2 font-medium animate-in fade-in slide-in-from-top-1">
              Hash copied to clipboard!
            </p>
          )}
        </div>

        <div className="pt-5 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground font-body">
            <span>Network:</span>
            <span className="font-medium text-foreground bg-secondary px-2 py-0.5 rounded-md border border-border">
              GovChain Kerala (Hyperledger)
            </span>
          </div>
          <button className="text-primary hover:text-primary/80 font-medium inline-flex items-center gap-1.5 transition-colors focus:outline-none focus:underline">
            View in Block Explorer
            <LinkIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}