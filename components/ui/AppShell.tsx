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
    <div className="min-h-screen bg-white dark:bg-black">
      {/* Header with Navigation */}
      <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-lg dark:border-gray-800 dark:bg-black/80">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex h-16 items-center justify-between">
            {/* Logo */}
            <Link
              href="/"
              className="text-base font-semibold text-gray-900 hover:text-gray-600 dark:text-white dark:hover:text-gray-400"
            >
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
                    className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                      active
                        ? "bg-gray-100 text-gray-900 dark:bg-gray-900 dark:text-white"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-white"
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
          <div className="mb-8 flex items-start justify-between">
            <div className="flex-1">
              {title && (
                <h1 className="text-3xl font-semibold tracking-tight text-gray-900 dark:text-white">
                  {title}
                </h1>
              )}
              {description && (
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
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
