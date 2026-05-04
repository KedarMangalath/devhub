import React, { useState } from "react";

export function Avatar({ src, alt = "", fallback = "", size = "md", className = "" }) {
  const [error, setError] = useState(false);
  const sizes = { sm: "h-8 w-8 text-xs", md: "h-10 w-10 text-sm", lg: "h-14 w-14 text-base", xl: "h-20 w-20 text-xl" };
  const sz = sizes[size] || sizes.md;
  const initials = fallback || alt.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() || "?";

  return (
    <span className={`relative inline-flex shrink-0 overflow-hidden rounded-full ${sz} ${className}`}>
      {!error && src ? (
        <img src={src} alt={alt} onError={() => setError(true)} className="aspect-square h-full w-full object-cover" />
      ) : (
        <span className="flex h-full w-full items-center justify-center rounded-full bg-muted font-medium text-muted-foreground">
          {initials}
        </span>
      )}
    </span>
  );
}
