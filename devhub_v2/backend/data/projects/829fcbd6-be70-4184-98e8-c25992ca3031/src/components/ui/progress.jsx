import React from "react";

export function Progress({ value = 0, max = 100, className = "" }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={`relative h-2 w-full overflow-hidden rounded-full bg-secondary ${className}`}>
      <div
        className="h-full bg-primary transition-all duration-300 ease-in-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
