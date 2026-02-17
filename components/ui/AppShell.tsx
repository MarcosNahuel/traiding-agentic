"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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
  { href: "/trades", label: "Trades" },
  { href: "/quant", label: "Quant" },
  { href: "/sources", label: "Sources" },
  { href: "/strategies", label: "Strategies" },
  { href: "/guides", label: "Guides" },
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
  const showPageHeader = Boolean(title || description || actions);

  return (
    <div className="min-h-screen bg-transparent">
      {/* Header with Navigation */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link
              href="/"
              className="flex items-center gap-2 text-base font-semibold text-white hover:text-emerald-400 transition-colors"
            >
              <div className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
              Trading AI
            </Link>

            {/* Navigation */}
            <nav className="flex items-center gap-1">
              {NAV_LINKS.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
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
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto w-full max-w-7xl px-6 py-8">
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
