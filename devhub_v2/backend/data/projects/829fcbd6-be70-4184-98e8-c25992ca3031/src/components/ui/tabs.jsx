import React, { useState } from "react";

export function Tabs({ children, defaultValue, className = "" }) {
  const [active, setActive] = useState(defaultValue || "");
  return (
    <div className={className} data-active={active}>
      {React.Children.map(children, (child) =>
        React.isValidElement(child)
          ? React.cloneElement(child, { _active: active, _setActive: setActive })
          : child
      )}
    </div>
  );
}

export function TabsList({ children, className = "", _active, _setActive }) {
  return (
    <div className={`inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground ${className}`}>
      {React.Children.map(children, (child) =>
        React.isValidElement(child)
          ? React.cloneElement(child, { _active, _setActive })
          : child
      )}
    </div>
  );
}

export function TabsTrigger({ value, children, className = "", _active, _setActive }) {
  const isActive = _active === value;
  return (
    <button
      onClick={() => _setActive && _setActive(value)}
      className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium
        ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2
        disabled:pointer-events-none disabled:opacity-50
        ${isActive ? "bg-background text-foreground shadow" : "hover:text-foreground/80"}
        ${className}`}
    >
      {children}
    </button>
  );
}

export function TabsContent({ value, children, className = "", _active }) {
  if (_active !== value) return null;
  return (
    <div className={`mt-2 ring-offset-background focus-visible:outline-none ${className}`}>
      {children}
    </div>
  );
}
