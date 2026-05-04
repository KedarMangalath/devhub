import { Check } from 'lucide-react'
import { cn } from '../../utils/cn'

export default function StepIndicator({ currentStep = 0, steps = [] }) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="w-full py-4 pb-12">
      <div className="flex items-center justify-between w-full">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep;
          const isActive = index === currentStep;
          const isUpcoming = index > currentStep;

          return (
            <div key={step} className="flex items-center w-full last:w-auto">
              {/* Step Node */}
              <div className="relative flex flex-col items-center">
                <div
                  className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center border-2 font-semibold text-sm transition-all duration-300 z-10 bg-white shadow-sm",
                    isCompleted && "bg-[#1d4ed8] border-[#1d4ed8] text-white",
                    isActive && "border-[#1d4ed8] text-[#1d4ed8] ring-4 ring-blue-50",
                    isUpcoming && "border-slate-200 text-slate-400 bg-slate-50"
                  )}
                  aria-current={isActive ? "step" : undefined}
                >
                  {isCompleted ? (
                    <Check className="w-5 h-5 text-white" strokeWidth={3} />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>
                
                {/* Label */}
                <div
                  className={cn(
                    "absolute top-14 left-1/2 -translate-x-1/2 text-xs md:text-sm font-medium text-center w-28 md:w-32 transition-colors duration-300",
                    isCompleted ? "text-slate-700" : isActive ? "text-[#0F172A] font-bold" : "text-slate-400"
                  )}
                >
                  {step}
                </div>
              </div>

              {/* Connecting Line */}
              {index < steps.length - 1 && (
                <div
                  className={cn(
                    "flex-auto h-0.5 mx-2 md:mx-4 transition-colors duration-300 rounded-full",
                    index < currentStep ? "bg-[#1d4ed8]" : "bg-slate-200"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}