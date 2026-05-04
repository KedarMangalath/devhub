import { useState } from 'react'
import { faqs } from '../../mockData'
import { ChevronDown, ChevronUp } from 'lucide-react'

export default function FAQAccordion() {
  const [openId, setOpenId] = useState(null)

  const toggleAccordion = (id) => {
    setOpenId(openId === id ? null : id)
  }

  return (
    <section className="py-24 bg-background border-t border-border relative overflow-hidden">
      {/* Subtle background decoration */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-full overflow-hidden pointer-events-none opacity-40">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-primary/5 rounded-full blur-3xl"></div>
        <div className="absolute top-1/2 -left-24 w-72 h-72 bg-accent/5 rounded-full blur-3xl"></div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center mb-16">
          <span className="inline-block py-1 px-3 rounded-full bg-primary/10 text-primary text-sm font-semibold font-body mb-4 tracking-wide uppercase">
            Support & Guidance
          </span>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-foreground mb-6 tracking-tight">
            Frequently Asked Questions
          </h2>
          <p className="text-lg text-muted-foreground font-body max-w-2xl mx-auto leading-relaxed">
            Everything you need to know about the Vigilance C3MS platform, how to report securely, and what happens after you submit a complaint.
          </p>
        </div>

        <div className="space-y-4">
          {faqs.map((faq) => {
            const isOpen = openId === faq.id
            return (
              <div
                key={faq.id}
                className={`bg-card border rounded-xl overflow-hidden transition-all duration-200 ${
                  isOpen 
                    ? 'border-primary/30 shadow-md shadow-primary/5' 
                    : 'border-border shadow-sm hover:shadow-md hover:border-border/80'
                }`}
              >
                <button
                  onClick={() => toggleAccordion(faq.id)}
                  className="w-full px-6 py-5 flex items-start sm:items-center justify-between text-left focus:outline-none focus:ring-2 focus:ring-primary focus:ring-inset group"
                  aria-expanded={isOpen}
                >
                  <span className={`text-lg font-semibold font-display pr-8 transition-colors ${
                    isOpen ? 'text-primary' : 'text-foreground group-hover:text-primary/80'
                  }`}>
                    {faq.question}
                  </span>
                  <span className={`flex-shrink-0 mt-1 sm:mt-0 transition-transform duration-200 ${
                    isOpen ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'
                  }`}>
                    {isOpen ? (
                      <ChevronUp className="w-5 h-5" />
                    ) : (
                      <ChevronDown className="w-5 h-5" />
                    )}
                  </span>
                </button>

                <div
                  className={`px-6 overflow-hidden transition-all duration-300 ease-in-out ${
                    isOpen ? 'max-h-[500px] pb-6 opacity-100' : 'max-h-0 opacity-0'
                  }`}
                >
                  <div className="w-full h-px bg-border/50 mb-4"></div>
                  <p className="text-muted-foreground font-body leading-relaxed text-base">
                    {faq.answer}
                  </p>
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-16 text-center bg-secondary/30 rounded-2xl p-8 sm:p-10 border border-border flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="text-left">
            <h3 className="text-xl font-display font-semibold text-foreground mb-2">
              Still have questions?
            </h3>
            <p className="text-muted-foreground font-body max-w-md">
              Our support team is available 24/7 to assist you with any concerns regarding the reporting process or platform security.
            </p>
          </div>
          <div className="flex-shrink-0 w-full sm:w-auto">
            <button className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-lg text-white bg-primary hover:bg-primary/90 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary focus:ring-offset-background">
              Contact Support
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}