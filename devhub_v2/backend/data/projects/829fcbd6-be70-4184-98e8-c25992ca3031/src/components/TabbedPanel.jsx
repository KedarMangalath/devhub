import React, { useState, useEffect, useRef, useCallback } from 'react';
import * as LucideIcons from 'lucide-react';

/**
 * TabbedPanel Component
 * 
 * A highly accessible, animated tabbed interface designed for the Vigilance C3MS system.
 * Features an animated underline indicator, optional count badges, icon support,
 * and full keyboard navigation (Left/Right arrows).
 * 
 * @param {Array} tabs - Array of tab objects: { id, label, count?, icon?, disabled? }
 * @param {Object|Function} children - React nodes mapped by tab id, or a render function
 * @param {String} defaultTab - The id of the tab to open by default
 * @param {Function} onTabChange - Callback fired when a tab is selected
 * @param {String} className - Additional CSS classes for the container
 * @param {String} contentClassName - Additional CSS classes for the content area
 */
export default function TabbedPanel({
  tabs = [],
  children = {},
  defaultTab,
  onTabChange,
  className = '',
  contentClassName = ''
}) {
  // State
  const [activeTab, setActiveTab] = useState(() => {
    if (defaultTab && tabs.some(t => t.id === defaultTab)) return defaultTab;
    return tabs.length > 0 ? tabs[0].id : null;
  });
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0, opacity: 0 });
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Refs
  const tabListRef = useRef(null);
  const tabRefs = useRef(new Map());
  const contentRef = useRef(null);

  // Update indicator position and width
  const updateIndicator = useCallback(() => {
    if (!activeTab) return;
    
    const currentTabEl = tabRefs.current.get(activeTab);
    const listEl = tabListRef.current;
    
    if (currentTabEl && listEl) {
      // Calculate relative to the scrollable container
      const left = currentTabEl.offsetLeft;
      const width = currentTabEl.offsetWidth;
      
      setIndicatorStyle({
        left,
        width,
        opacity: 1
      });

      // Ensure the active tab is scrolled into view if in a scrollable container
      const scrollLeft = listEl.scrollLeft;
      const listWidth = listEl.offsetWidth;
      
      if (left < scrollLeft) {
        listEl.scrollTo({ left, behavior: 'smooth' });
      } else if (left + width > scrollLeft + listWidth) {
        listEl.scrollTo({ left: left + width - listWidth, behavior: 'smooth' });
      }
    }
  }, [activeTab]);

  // Handle window resize to keep indicator aligned
  useEffect(() => {
    updateIndicator();
    
    const handleResize = () => {
      // Use requestAnimationFrame to avoid thrashing during resize
      requestAnimationFrame(updateIndicator);
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [updateIndicator]);

  // Update indicator when tabs or active tab changes
  useEffect(() => {
    // Small delay to ensure DOM is painted before calculating widths
    const timer = setTimeout(updateIndicator, 50);
    return () => clearTimeout(timer);
  }, [activeTab, tabs, updateIndicator]);

  // Handle tab selection
  const handleTabClick = (id, disabled) => {
    if (disabled || id === activeTab) return;
    
    setIsTransitioning(true);
    setActiveTab(id);
    if (onTabChange) onTabChange(id);
    
    // Reset transition state after animation completes
    setTimeout(() => setIsTransitioning(false), 300);
  };

  // Keyboard navigation (Accessibility)
  const handleKeyDown = (e) => {
    const currentIndex = tabs.findIndex(t => t.id === activeTab);
    if (currentIndex === -1) return;

    let nextIndex = currentIndex;

    if (e.key === 'ArrowRight') {
      nextIndex = (currentIndex + 1) % tabs.length;
      e.preventDefault();
    } else if (e.key === 'ArrowLeft') {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
      e.preventDefault();
    } else if (e.key === 'Home') {
      nextIndex = 0;
      e.preventDefault();
    } else if (e.key === 'End') {
      nextIndex = tabs.length - 1;
      e.preventDefault();
    }

    if (nextIndex !== currentIndex) {
      const nextTab = tabs[nextIndex];
      if (!nextTab.disabled) {
        handleTabClick(nextTab.id, false);
        // Set focus to the new tab
        const nextTabEl = tabRefs.current.get(nextTab.id);
        if (nextTabEl) nextTabEl.focus();
      }
    }
  };

  // Render content based on children type
  const renderContent = () => {
    if (!activeTab) return null;

    let content = null;
    if (typeof children === 'function') {
      content = children(activeTab);
    } else if (typeof children === 'object' && children !== null) {
      content = children[activeTab];
    }

    return (
      <div 
        role="tabpanel"
        id={`panel-${activeTab}`}
        aria-labelledby={`tab-${activeTab}`}
        className={`
          transition-opacity duration-300 ease-in-out
          ${isTransitioning ? 'opacity-50' : 'opacity-100'}
        `}
      >
        {content || (
          <div className="p-8 text-center text-muted-foreground border-2 border-dashed border-border rounded-lg mt-4">
            No content available for this section.
          </div>
        )}
      </div>
    );
  };

  if (!tabs || tabs.length === 0) {
    return null;
  }

  return (
    <div className={`w-full flex flex-col ${className}`}>
      {/* Tab List Header */}
      <div className="relative border-b border-border">
        <div 
          ref={tabListRef}
          role="tablist"
          aria-orientation="horizontal"
          className="flex items-center overflow-x-auto hide-scrollbar scroll-smooth"
          onKeyDown={handleKeyDown}
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {tabs.map((tab) => {
            const Icon = tab.icon && LucideIcons[tab.icon] ? LucideIcons[tab.icon] : null;
            const isActive = activeTab === tab.id;
            const isDisabled = tab.disabled;

            return (
              <button
                key={tab.id}
                ref={(el) => {
                  if (el) tabRefs.current.set(tab.id, el);
                  else tabRefs.current.delete(tab.id);
                }}
                role="tab"
                id={`tab-${tab.id}`}
                aria-selected={isActive}
                aria-controls={`panel-${tab.id}`}
                aria-disabled={isDisabled}
                tabIndex={isActive ? 0 : -1}
                onClick={() => handleTabClick(tab.id, isDisabled)}
                className={`
                  relative flex items-center gap-2 px-5 py-3.5 text-sm font-medium transition-all duration-200 whitespace-nowrap outline-none
                  focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:rounded-sm
                  ${isDisabled 
                    ? 'opacity-50 cursor-not-allowed text-muted-foreground' 
                    : isActive 
                      ? 'text-primary' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/40'
                  }
                `}
              >
                {Icon && (
                  <Icon 
                    className={`w-4 h-4 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} 
                    aria-hidden="true" 
                  />
                )}
                
                <span className="font-body tracking-wide">{tab.label}</span>
                
                {tab.count !== undefined && (
                  <span 
                    className={`
                      inline-flex items-center justify-center min-w-[1.5rem] h-5 px-1.5 rounded-full text-[11px] font-bold transition-colors
                      ${isActive 
                        ? 'bg-primary/10 text-primary' 
                        : 'bg-secondary text-muted-foreground border border-border/50'
                      }
                    `}
                  >
                    {tab.count > 99 ? '99+' : tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Animated Underline Indicator */}
        <div
          className="absolute bottom-0 h-[2px] bg-primary rounded-t-full transition-all duration-300 ease-out pointer-events-none"
          style={{ 
            left: `${indicatorStyle.left}px`, 
            width: `${indicatorStyle.width}px`,
            opacity: indicatorStyle.opacity,
            transform: 'translateY(1px)' // Overlap the border slightly for a cleaner look
          }}
          aria-hidden="true"
        />
      </div>

      {/* Tab Content Area */}
      <div 
        ref={contentRef}
        className={`pt-6 ${contentClassName}`}
      >
        {renderContent()}
      </div>

      {/* Inject styles for hiding scrollbar if not present in global css */}
      <style dangerouslySetInnerHTML={{__html: `
        .hide-scrollbar::-webkit-scrollbar {
          display: none;
        }
      `}} />
    </div>
  );
}