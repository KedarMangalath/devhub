import React from "react";

export function Separator({ orientation = "horizontal", className = "" }) {
  if (orientation === "vertical") {
    return <div className={`shrink-0 bg-border w-px h-full ${className}`} />;
  }
  return <div className={`shrink-0 bg-border h-px w-full ${className}`} />;
}
