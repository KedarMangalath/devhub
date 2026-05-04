import { useState } from 'react'
import { testimonials } from '../../mockData'
import { ChevronLeft, ChevronRight, Quote } from 'lucide-react'

export default function TestimonialCarousel() {
  const [currentIndex, setCurrentIndex] = useState(0);

  // Fallback data ensures zero empty states even if mockData is incomplete
  const carouselData = testimonials && testimonials.length > 0 ? testimonials : [
    {
      id: 'test-1',
      quote: "I was afraid to report the bribe requested for my land registration. The anonymous WhatsApp bot made it safe and easy. The officer was suspended within weeks.",
      author: "Anonymous Citizen",
      role: "Ernakulam District"
    },
    {
      id: 'test-2',
      quote: "The blockchain tracking gave me confidence that my complaint couldn't be deleted or altered by powerful individuals. Transparency at its best.",
      author: "Verified User #8842",
      role: "Small Business Owner"
    },
    {
      id: 'test-3',
      quote: "Seeing the AI credibility score instantly validate my evidence made me feel heard. The vigilance department acted faster than I ever expected.",
      author: "Citizen #9102",
      role: "Thiruvananthapuram"
    },
    {
      id: 'test-4',
      quote: "The predictive alerts flagged a suspicious tender in our municipality before funds were released. This system is actively saving public money.",
      author: "Internal Auditor",
      role: "Local Self Government Dept"
    }
  ];

  const nextSlide = () => {
    setCurrentIndex((prev) => (prev + 1) % carouselData.length);
  };

  const prevSlide = () => {
    setCurrentIndex((prev) => (prev - 1 + carouselData.length) % carouselData.length);
  };

  const goToSlide = (index) => {
    setCurrentIndex(index);
  };

  return (
    <section className="py-24 bg-slate-50 relative overflow-hidden">
      {/* Decorative background elements */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-emerald-100 rounded-full mix-blend-multiply filter blur-3xl opacity-50"></div>
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-amber-100 rounded-full mix-blend-multiply filter blur-3xl opacity-50"></div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-3xl md:text-4xl font-display font-bold text-slate-900 mb-4 tracking-tight">
            Voices of Trust
          </h2>
          <p className="text-lg text-slate-600 font-body">
            Real stories from citizens and officials who stood up against corruption, empowered by secure and anonymous reporting.
          </p>
        </div>

        <div className="relative max-w-5xl mx-auto">
          {/* Carousel Track */}
          <div className="overflow-hidden rounded-2xl bg-white shadow-xl border border-slate-100">
            <div 
              className="flex transition-transform duration-500 ease-in-out"
              style={{ transform: `translateX(-${currentIndex * 100}%)` }}
            >
              {carouselData.map((testimonial) => (
                <div 
                  key={testimonial.id} 
                  className="w-full flex-shrink-0 p-8 md:p-16 flex flex-col items-center text-center"
                >
                  <Quote className="w-12 h-12 text-emerald-500 mb-8 opacity-50" />
                  
                  <blockquote className="text-xl md:text-2xl font-body text-slate-800 leading-relaxed mb-8 max-w-3xl">
                    "{testimonial.quote || testimonial.text}"
                  </blockquote>
                  
                  <div className="mt-auto">
                    <div className="w-12 h-1 bg-emerald-500 mx-auto mb-4 rounded-full"></div>
                    <cite className="not-italic block font-display font-semibold text-slate-900 text-lg">
                      {testimonial.author || testimonial.name}
                    </cite>
                    <span className="block text-sm text-slate-500 font-body mt-1">
                      {testimonial.role || testimonial.designation}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Navigation Buttons */}
          <button 
            onClick={prevSlide}
            className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-4 md:-translate-x-6 w-12 h-12 bg-white rounded-full shadow-lg border border-slate-100 flex items-center justify-center text-slate-600 hover:text-emerald-600 hover:scale-110 transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 z-20"
            aria-label="Previous testimonial"
          >
            <ChevronLeft className="w-6 h-6" />
          </button>
          
          <button 
            onClick={nextSlide}
            className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-4 md:translate-x-6 w-12 h-12 bg-white rounded-full shadow-lg border border-slate-100 flex items-center justify-center text-slate-600 hover:text-emerald-600 hover:scale-110 transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 z-20"
            aria-label="Next testimonial"
          >
            <ChevronRight className="w-6 h-6" />
          </button>

          {/* Pagination Dots */}
          <div className="flex justify-center space-x-3 mt-8">
            {carouselData.map((_, index) => (
              <button
                key={index}
                onClick={() => goToSlide(index)}
                className={`w-3 h-3 rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 ${
                  index === currentIndex 
                    ? 'bg-emerald-600 w-8' 
                    : 'bg-slate-300 hover:bg-emerald-400'
                }`}
                aria-label={`Go to slide ${index + 1}`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}