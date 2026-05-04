import React, { useState, useRef, useEffect } from "react";

export function Select({ value, onValueChange, children, placeholder = "Select..." }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const items = React.Children.toArray(children).filter(
    (c) => React.isValidElement(c) && c.type === SelectItem
  );
  const selected = items.find((c) => c.props.value === value);

  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-2 text-sm
          shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className={selected ? "" : "text-muted-foreground"}>
          {selected ? selected.props.children : placeholder}
        </span>
        <svg className="h-4 w-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md animate-in fade-in-0 zoom-in-95">
          <div className="p-1">
            {items.map((item) =>
              React.cloneElement(item, {
                _onSelect: (v) => { onValueChange && onValueChange(v); setOpen(false); },
                _selected: item.props.value === value,
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function SelectItem({ value, children, _onSelect, _selected }) {
  return (
    <div
      onClick={() => _onSelect && _onSelect(value)}
      className={`relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none
        hover:bg-accent hover:text-accent-foreground
        ${_selected ? "bg-accent text-accent-foreground font-medium" : ""}`}
    >
      {children}
    </div>
  );
}
