import React from "react";

export function Sheet({ open, onOpenChange, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange && onOpenChange(false)}
      />
      <div className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-sm sm:max-w-md">
        {children}
      </div>
    </div>
  );
}

export function SheetContent({ children, className = "" }) {
  return (
    <div className={`flex h-full flex-col bg-background border-l shadow-xl overflow-y-auto ${className}`}>
      {children}
    </div>
  );
}

export function SheetHeader({ children, className = "" }) {
  return <div className={`flex flex-col space-y-1.5 p-6 pb-0 ${className}`}>{children}</div>;
}

export function SheetTitle({ children, className = "" }) {
  return <h2 className={`text-lg font-semibold ${className}`}>{children}</h2>;
}
