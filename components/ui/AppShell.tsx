"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";

interface AppShellProps {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/daily", label: "Daily" },
  { href: "/trades", label: "Trades" },
  { href: "/quant", label: "Quant" },
  { href: "/sources", label: "Sources" },
  { href: "/strategies", label: "Strategies" },
  { href: "/guides", label: "Guides" },
  { href: "/history", label: "History" },
  { href: "/chat", label: "Chat" },
  { href: "/logs", label: "Logs" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({
  title,
  description,
  actions,
  children,
}: AppShellProps) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const showPageHeader = Boolean(title || description || actions);

  return (
    <div className="min-h-screen bg-transparent">
      {/* Header with Navigation */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="flex h-16 items-center justify-between gap-4">
            {/* Logo */}
            <Link
              href="/"
              className="flex flex-shrink-0 items-center gap-2 text-base font-semibold text-white hover:text-emerald-400 transition-colors"
            >
              <div className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
              Trading AI
            </Link>

            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center gap-1 overflow-x-auto scrollbar-none" aria-label="Navegación principal">
              {NAV_LINKS.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex-shrink-0 rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                      active
                        ? "bg-emerald-500/10 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.1)] border border-emerald-500/20"
                        : "text-slate-400 hover:bg-white/5 hover:text-white border border-transparent"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {/* Mobile hamburger button */}
            <button
              aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((v) => !v)}
              className="md:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-slate-400 hover:bg-white/5 hover:text-white transition-colors"
            >
              {menuOpen ? (
                /* X icon */
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                /* Hamburger icon */
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile dropdown menu */}
        {menuOpen && (
          <nav
            id="mobile-nav"
            aria-label="Navegación móvil"
            className="md:hidden border-t border-white/5 bg-slate-950/95 px-4 py-3"
          >
            <div className="grid grid-cols-3 gap-1.5">
              {NAV_LINKS.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className={`rounded-lg px-3 py-2 text-center text-xs font-medium transition-all ${
                      active
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : "text-slate-400 hover:bg-white/5 hover:text-white border border-transparent"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </nav>
        )}
      </header>

      {/* Main Content */}
      <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6">
        {showPageHeader && (
          <div className="mb-8 flex items-start justify-between border-b border-white/5 pb-6">
            <div className="flex-1">
              {title && (
                <h1 className="text-2xl font-bold tracking-tight text-white">
                  {title}
                </h1>
              )}
              {description && (
                <p className="mt-2 text-sm text-slate-400">
                  {description}
                </p>
              )}
            </div>
            {actions && <div className="ml-4 flex items-center gap-2">{actions}</div>}
          </div>
        )}

        {children}
      </main>
    </div>
  );
}
