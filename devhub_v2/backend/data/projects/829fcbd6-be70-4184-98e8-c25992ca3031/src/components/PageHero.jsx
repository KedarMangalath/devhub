import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

/**
 * PageHero Component
 * 
 * A reusable, highly visual hero section for inner pages (Explore, Report, Dashboard, etc.).
 * Features a dark, authoritative aesthetic with subtle grid patterns and emerald glows
 * to align with the Vigilance C3MS design system.
 * 
 * @param {string} title - Main heading text
 * @param {string} sub - Secondary descriptive text
 * @param {Array} cta - Array of call-to-action objects { label, href, onClick, primary, icon }
 * @param {Array} breadcrumbs - Array of breadcrumb objects { label, href }
 * @param {string} image - Optional background image URL
 * @param {Object|string} badge - Optional badge text or object { text, icon }
 */
export default function PageHero({
  title,
  sub,
  cta = [],
  breadcrumbs = [],
  image,
  badge
}) {
  // Helper to render the badge content safely whether it's a string or object
  const renderBadge = () => {
    if (!badge) return null;
    
    const badgeText = typeof badge === 'string' ? badge : badge.text;
    const BadgeIcon = typeof badge === 'object' && badge.icon ? badge.icon : null;

    return (
      <div className="mb-6 inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-sm font-medium text-emerald-300 backdrop-blur-sm animate-in fade-in slide-in-from-bottom-4 duration-700">
        {BadgeIcon && <BadgeIcon className="mr-2 h-4 w-4" />}
        {badgeText}
      </div>
    );
  };

  return (
    <div className="relative isolate overflow-hidden bg-slate-950 py-16 sm:py-24 lg:py-32 border-b border-slate-800">
      {/* Background Layer */}
      {image ? (
        <>
          <img
            src={image}
            alt="Hero background"
            className="absolute inset-0 -z-20 h-full w-full object-cover opacity-20 mix-blend-luminosity"
          />
          <div className="absolute inset-0 -z-10 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent" />
        </>
      ) : (
        <>
          {/* Architectural Grid Pattern */}
          <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>
          
          {/* Emerald Glow Effect */}
          <div
            className="absolute left-1/2 top-0 -z-10 -translate-x-1/2 blur-3xl xl:-top-6"
            aria-hidden="true"
          >
            <div
              className="aspect-[1155/678] w-[72.1875rem] bg-gradient-to-tr from-[#059669] to-[#0f172a] opacity-20"
              style={{
                clipPath:
                  'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)',
              }}
            />
          </div>
        </>
      )}

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="mx-auto max-w-3xl lg:mx-0">
          
          {/* Breadcrumbs Navigation */}
          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav className="flex mb-8" aria-label="Breadcrumb">
              <ol className="flex items-center space-x-2 text-sm text-slate-400">
                <li>
                  <Link to="/" className="hover:text-white transition-colors flex items-center">
                    <Home className="w-4 h-4" />
                    <span className="sr-only">Home</span>
                  </Link>
                </li>
                {breadcrumbs.map((crumb, index) => {
                  const isLast = index === breadcrumbs.length - 1;
                  return (
                    <li key={index} className="flex items-center">
                      <ChevronRight className="w-4 h-4 mx-1 flex-shrink-0 text-slate-600" />
                      {isLast ? (
                        <span className="text-slate-200 font-medium" aria-current="page">
                          {crumb.label}
                        </span>
                      ) : (
                        <Link to={crumb.href} className="hover:text-white transition-colors">
                          {crumb.label}
                        </Link>
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
          )}

          {/* Optional Badge */}
          {renderBadge()}

          {/* Main Typography */}
          <h1 className="font-display text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl animate-in fade-in slide-in-from-bottom-6 duration-700 delay-100 fill-mode-both">
            {title}
          </h1>
          
          {sub && (
            <p className="mt-6 max-w-2xl font-body text-lg leading-8 text-slate-300 animate-in fade-in slide-in-from-bottom-6 duration-700 delay-200 fill-mode-both">
              {sub}
            </p>
          )}

          {/* Call to Action Buttons */}
          {cta && cta.length > 0 && (
            <div className="mt-10 flex flex-wrap items-center gap-4 animate-in fade-in slide-in-from-bottom-6 duration-700 delay-300 fill-mode-both">
              {cta.map((btn, idx) => {
                const BtnIcon = btn.icon;
                const baseClasses = "inline-flex items-center justify-center rounded-md px-6 py-3 text-sm font-semibold shadow-sm transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";
                const primaryClasses = "bg-emerald-600 text-white hover:bg-emerald-500 focus-visible:outline-emerald-600";
                const secondaryClasses = "bg-white/10 text-white hover:bg-white/20 ring-1 ring-inset ring-white/20 backdrop-blur-sm";
                
                const className = `${baseClasses} ${btn.primary ? primaryClasses : secondaryClasses}`;

                if (btn.href) {
                  return (
                    <Link key={idx} to={btn.href} className={className}>
                      {BtnIcon && <BtnIcon className="mr-2 -ml-1 h-5 w-5" />}
                      {btn.label}
                    </Link>
                  );
                }

                return (
                  <button key={idx} onClick={btn.onClick} type="button" className={className}>
                    {BtnIcon && <BtnIcon className="mr-2 -ml-1 h-5 w-5" />}
                    {btn.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}