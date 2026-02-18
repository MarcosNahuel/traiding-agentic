/**
 * Documentation page - Serves the HTML manual in an iframe
 */

import Link from "next/link";
import { ArrowLeft, BookOpen, Download, ExternalLink } from "lucide-react";

export default function DocsPage() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-950">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>
            <div className="h-4 w-px bg-white/10" />
            <div className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-cyan-400" />
              <h1 className="text-lg font-bold text-white">
                System Documentation
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="/manual-trading-agentic.html"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Open in new tab
            </a>
            <a
              href="/manual-trading-agentic.html"
              download
              className="flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-400 transition-colors hover:bg-cyan-500/20"
            >
              <Download className="h-3.5 w-3.5" />
              Download HTML
            </a>
          </div>
        </div>
      </header>

      {/* Manual iframe */}
      <main className="flex-1">
        <iframe
          src="/manual-trading-agentic.html"
          className="h-[calc(100vh-65px)] w-full border-0"
          title="Trading Agentic - Manual del Sistema"
        />
      </main>
    </div>
  );
}
