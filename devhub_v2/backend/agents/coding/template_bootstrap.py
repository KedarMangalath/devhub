"""
TemplateBootstrapper — copies pre-baked UI primitive templates into a project.

Templates are embedded as Python strings so no external files are needed.
They are written BEFORE the LLM codegen runs so FileCodeAgent can import them.

Supported framework families:
  react / nextjs / react_ts  → shadcn-style Tailwind + tailwind-merge primitives (.tsx)
  vue                        → Vue 3 SFC primitives (.vue)
  svelte                     → Svelte 4 primitives (.svelte)
  vanilla                    → plain CSS utility classes + tiny JS components

The LLM writes pages/domain-components that compose these primitives.
It must NEVER rewrite the primitives themselves (they are frozen).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# React / Next.js primitives  (tsx, tailwind-merge, no cva dependency)
# ---------------------------------------------------------------------------

_REACT_LIB_UTILS = '''"use strict";
// cn — merge Tailwind class strings, later wins
export function cn(...inputs) {
  return inputs
    .filter(Boolean)
    .join(" ")
    .split(" ")
    .reduce((acc, cls) => {
      if (!cls) return acc;
      const base = cls.replace(/^(hover:|focus:|active:|disabled:|sm:|md:|lg:|xl:|2xl:)/, "");
      acc[base] = cls;
      return acc;
    }, {});
}

// Simplified cn without tailwind-merge dep — good enough for generated apps
export function classes(...args) {
  return args.filter(Boolean).join(" ");
}
'''

_REACT_UTILS_TS = '''import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
'''

_REACT_BUTTON = '''import React from "react";

const variants = {
  default: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm",
  destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
  outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
  secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
  ghost: "hover:bg-accent hover:text-accent-foreground",
  link: "text-primary underline-offset-4 hover:underline",
};

const sizes = {
  default: "h-9 px-4 py-2 text-sm",
  sm: "h-7 rounded-md px-3 text-xs",
  lg: "h-11 rounded-md px-8 text-base",
  icon: "h-9 w-9",
};

export function Button({
  children,
  variant = "default",
  size = "default",
  className = "",
  disabled,
  onClick,
  type = "button",
  href,
  ...props
}) {
  const base =
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-medium " +
    "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
    "disabled:pointer-events-none disabled:opacity-50 cursor-pointer";
  const cls = [base, variants[variant] || variants.default, sizes[size] || sizes.default, className]
    .filter(Boolean)
    .join(" ");

  if (href) {
    return (
      <a href={href} className={cls} {...props}>
        {children}
      </a>
    );
  }
  return (
    <button type={type} className={cls} disabled={disabled} onClick={onClick} {...props}>
      {children}
    </button>
  );
}
'''

_REACT_CARD = '''import React from "react";

export function Card({ children, className = "", onClick, ...props }) {
  return (
    <div
      className={`rounded-xl border bg-card text-card-foreground shadow-sm ${className}`}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = "" }) {
  return <div className={`flex flex-col space-y-1.5 p-6 ${className}`}>{children}</div>;
}

export function CardTitle({ children, className = "" }) {
  return (
    <h3 className={`font-semibold leading-none tracking-tight text-lg ${className}`}>
      {children}
    </h3>
  );
}

export function CardDescription({ children, className = "" }) {
  return <p className={`text-sm text-muted-foreground ${className}`}>{children}</p>;
}

export function CardContent({ children, className = "" }) {
  return <div className={`p-6 pt-0 ${className}`}>{children}</div>;
}

export function CardFooter({ children, className = "" }) {
  return (
    <div className={`flex items-center p-6 pt-0 ${className}`}>{children}</div>
  );
}
'''

_REACT_BADGE = '''import React from "react";

const variants = {
  default: "bg-primary text-primary-foreground hover:bg-primary/80",
  secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
  destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/80",
  outline: "text-foreground border border-input",
  success: "bg-emerald-100 text-emerald-800",
  warning: "bg-amber-100 text-amber-800",
  info: "bg-sky-100 text-sky-800",
};

export function Badge({ children, variant = "default", className = "" }) {
  return (
    <div
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors ${
        variants[variant] || variants.default
      } ${className}`}
    >
      {children}
    </div>
  );
}
'''

_REACT_INPUT = '''import React from "react";

export const Input = React.forwardRef(function Input(
  { className = "", type = "text", ...props },
  ref
) {
  return (
    <input
      type={type}
      ref={ref}
      className={`flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors
        file:border-0 file:bg-transparent file:text-sm file:font-medium
        placeholder:text-muted-foreground
        focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
        disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      {...props}
    />
  );
});
'''

_REACT_LABEL = '''import React from "react";

export function Label({ children, htmlFor, className = "" }) {
  return (
    <label
      htmlFor={htmlFor}
      className={`text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 ${className}`}
    >
      {children}
    </label>
  );
}
'''

_REACT_TEXTAREA = '''import React from "react";

export const Textarea = React.forwardRef(function Textarea(
  { className = "", ...props },
  ref
) {
  return (
    <textarea
      ref={ref}
      className={`flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm
        placeholder:text-muted-foreground
        focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
        disabled:cursor-not-allowed disabled:opacity-50 resize-none ${className}`}
      {...props}
    />
  );
});
'''

_REACT_SEPARATOR = '''import React from "react";

export function Separator({ orientation = "horizontal", className = "" }) {
  if (orientation === "vertical") {
    return <div className={`shrink-0 bg-border w-px h-full ${className}`} />;
  }
  return <div className={`shrink-0 bg-border h-px w-full ${className}`} />;
}
'''

_REACT_AVATAR = '''import React, { useState } from "react";

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
'''

_REACT_SKELETON = '''import React from "react";

export function Skeleton({ className = "" }) {
  return (
    <div className={`animate-pulse rounded-md bg-muted ${className}`} />
  );
}
'''

_REACT_PROGRESS = '''import React from "react";

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
'''

_REACT_TABS = '''import React, { useState } from "react";

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
'''

_REACT_SELECT = '''import React, { useState, useRef, useEffect } from "react";

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
'''

_REACT_DIALOG = '''import React from "react";

export function Dialog({ open, onOpenChange, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange && onOpenChange(false)}
      />
      <div className="relative z-50 w-full max-w-lg">{children}</div>
    </div>
  );
}

export function DialogContent({ children, className = "" }) {
  return (
    <div className={`relative bg-background rounded-xl border shadow-xl p-6 ${className}`}>
      {children}
    </div>
  );
}

export function DialogHeader({ children, className = "" }) {
  return <div className={`flex flex-col space-y-1.5 text-center sm:text-left mb-4 ${className}`}>{children}</div>;
}

export function DialogTitle({ children, className = "" }) {
  return <h2 className={`text-lg font-semibold leading-none tracking-tight ${className}`}>{children}</h2>;
}

export function DialogDescription({ children, className = "" }) {
  return <p className={`text-sm text-muted-foreground ${className}`}>{children}</p>;
}

export function DialogFooter({ children, className = "" }) {
  return (
    <div className={`flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-6 ${className}`}>
      {children}
    </div>
  );
}
'''

_REACT_SHEET = '''import React from "react";

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
'''

_REACT_INDEX_CSS_VARS = '''/* Design tokens — override with spec palette */
:root {
  --background: 0 0% 100%;
  --foreground: 224 71.4% 4.1%;
  --card: 0 0% 100%;
  --card-foreground: 224 71.4% 4.1%;
  --popover: 0 0% 100%;
  --popover-foreground: 224 71.4% 4.1%;
  --primary: 220.9 39.3% 11%;
  --primary-foreground: 210 20% 98%;
  --secondary: 220 14.3% 95.9%;
  --secondary-foreground: 220.9 39.3% 11%;
  --muted: 220 14.3% 95.9%;
  --muted-foreground: 220 8.9% 46.1%;
  --accent: 220 14.3% 95.9%;
  --accent-foreground: 220.9 39.3% 11%;
  --destructive: 0 84.2% 60.2%;
  --destructive-foreground: 210 20% 98%;
  --border: 220 13% 91%;
  --input: 220 13% 91%;
  --ring: 224 71.4% 4.1%;
  --radius: 0.5rem;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--font-body, system-ui, sans-serif); background: hsl(var(--background)); color: hsl(var(--foreground)); }
'''

# ---------------------------------------------------------------------------
# Vue primitives (simplified, script setup)
# ---------------------------------------------------------------------------

_VUE_BUTTON = '''<script setup>
defineProps({
  variant: { type: String, default: 'default' },
  size: { type: String, default: 'default' },
  disabled: { type: Boolean, default: false },
  href: { type: String, default: null },
})
const variants = {
  default: 'bg-primary text-white hover:bg-primary/90',
  outline: 'border border-input hover:bg-accent hover:text-accent-foreground',
  ghost: 'hover:bg-accent hover:text-accent-foreground',
  secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  destructive: 'bg-red-500 text-white hover:bg-red-600',
}
const sizes = { default: 'h-9 px-4 py-2 text-sm', sm: 'h-7 px-3 text-xs', lg: 'h-11 px-8 text-base' }
</script>
<template>
  <component
    :is="href ? 'a' : 'button'"
    :href="href"
    :disabled="disabled"
    :class="['inline-flex items-center justify-center rounded-md font-medium transition-colors gap-2',
             'focus-visible:outline-none focus-visible:ring-2',
             'disabled:pointer-events-none disabled:opacity-50',
             variants[variant] || variants.default,
             sizes[size] || sizes.default]"
  >
    <slot />
  </component>
</template>
'''

_VUE_CARD = '''<script setup>
defineProps({ class: { type: String, default: '' } })
</script>
<template>
  <div :class="['rounded-xl border bg-card text-card-foreground shadow-sm', $props.class]">
    <slot />
  </div>
</template>
'''

_VUE_BADGE = '''<script setup>
defineProps({ variant: { type: String, default: 'default' } })
const variants = {
  default: 'bg-primary text-white',
  secondary: 'bg-secondary text-secondary-foreground',
  outline: 'border border-input',
  success: 'bg-emerald-100 text-emerald-800',
}
</script>
<template>
  <span :class="['inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold', variants[variant]]">
    <slot />
  </span>
</template>
'''

# ---------------------------------------------------------------------------
# Svelte primitives (minimal set)
# ---------------------------------------------------------------------------

_SVELTE_BUTTON = '''<script>
  export let variant = 'default';
  export let size = 'default';
  export let disabled = false;
  export let href = null;
  const variants = {
    default: 'bg-primary text-white hover:bg-primary/90',
    outline: 'border border-input hover:bg-accent',
    ghost: 'hover:bg-accent hover:text-accent-foreground',
  };
  const sizes = { default: 'h-9 px-4 py-2 text-sm', sm: 'h-7 px-3 text-xs', lg: 'h-11 px-8 text-base' };
  $: cls = ['inline-flex items-center justify-center rounded-md font-medium transition-colors gap-2 cursor-pointer', variants[variant], sizes[size]].filter(Boolean).join(' ');
</script>
{#if href}
  <a {href} class={cls}><slot /></a>
{:else}
  <button {disabled} class={cls}><slot /></button>
{/if}
'''

_SVELTE_CARD = '''<script>
  export let className = '';
</script>
<div class="rounded-xl border bg-card text-card-foreground shadow-sm {className}">
  <slot />
</div>
'''

# ---------------------------------------------------------------------------
# Framework template map
# ---------------------------------------------------------------------------

def _react_templates(src_prefix: str, ext: str = ".jsx") -> dict[str, str]:
    """Returns {relative_path: content} for the React primitive set."""
    ui = f"{src_prefix}components/ui/"
    lib = f"{src_prefix}lib/"
    return {
        f"{lib}utils{'.ts' if ext in ('.tsx', '.ts') else '.js'}": _REACT_UTILS_TS if ext in ('.tsx', '.ts') else _REACT_LIB_UTILS,
        f"{ui}button{ext}": _REACT_BUTTON,
        f"{ui}card{ext}": _REACT_CARD,
        f"{ui}badge{ext}": _REACT_BADGE,
        f"{ui}input{ext}": _REACT_INPUT,
        f"{ui}label{ext}": _REACT_LABEL,
        f"{ui}textarea{ext}": _REACT_TEXTAREA,
        f"{ui}separator{ext}": _REACT_SEPARATOR,
        f"{ui}avatar{ext}": _REACT_AVATAR,
        f"{ui}skeleton{ext}": _REACT_SKELETON,
        f"{ui}progress{ext}": _REACT_PROGRESS,
        f"{ui}tabs{ext}": _REACT_TABS,
        f"{ui}select{ext}": _REACT_SELECT,
        f"{ui}dialog{ext}": _REACT_DIALOG,
        f"{ui}sheet{ext}": _REACT_SHEET,
    }


def _vue_templates(src_prefix: str) -> dict[str, str]:
    ui = f"{src_prefix}components/ui/"
    return {
        f"{ui}Button.vue": _VUE_BUTTON,
        f"{ui}Card.vue": _VUE_CARD,
        f"{ui}Badge.vue": _VUE_BADGE,
    }


def _svelte_templates(src_prefix: str) -> dict[str, str]:
    ui = f"{src_prefix}lib/components/ui/"
    return {
        f"{ui}Button.svelte": _SVELTE_BUTTON,
        f"{ui}Card.svelte": _SVELTE_CARD,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_template_files(conventions: dict, design_tokens: dict | None = None) -> dict[str, str]:
    """
    Return {path: content} for the design-system primitives matching conventions.
    Paths are relative to the project root.
    """
    frontend_fw = (conventions.get("frontend_framework") or "").lower()
    frontend_dir = conventions.get("frontend_dir") or "."
    file_exts = conventions.get("file_extensions") or {}
    comp_ext = file_exts.get("components", ".jsx")

    prefix = "" if frontend_dir in (".", None) else f"{frontend_dir.strip('/')}/"
    src_prefix = f"{prefix}src/"

    templates: dict[str, str] = {}

    if any(x in frontend_fw for x in ("react", "next", "vite")):
        templates.update(_react_templates(src_prefix, comp_ext))
    elif "vue" in frontend_fw:
        templates.update(_vue_templates(src_prefix))
    elif "svelte" in frontend_fw:
        templates.update(_svelte_templates(src_prefix))
    # else: vanilla — no template primitives needed

    return templates


def get_frozen_paths(conventions: dict) -> set[str]:
    """Paths that belong to the template and must not be overwritten by codegen."""
    return set(get_template_files(conventions).keys())


def write_templates(conventions: dict, project_root: Path, design_tokens: dict | None = None) -> list[str]:
    """Write template files to disk. Returns list of written paths."""
    files = get_template_files(conventions, design_tokens)
    written = []
    for rel_path, content in files.items():
        target = project_root / rel_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(rel_path)
        except Exception as exc:
            logger.warning("Failed to write template %s: %s", rel_path, exc)
    logger.info("Template bootstrap: wrote %d primitives", len(written))
    return written
