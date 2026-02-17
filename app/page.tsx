/**
 * Home page - Trading Research AI Dashboard
 */

import Link from "next/link";
import {
  LayoutDashboard,
  FileText,
  Bot,
  ScrollText,
  GitBranch,
  BarChart3,
  Settings,
  ShieldCheck,
  Zap,
  Activity,
  Layers,
  Cpu,
  ArrowRight,
} from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-transparent">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-slate-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/20">
              <Activity className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">
                Trading Agentic
              </h1>
              <p className="text-xs font-medium text-slate-400">
                Research & Execution
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 backdrop-blur-md">
              <div className="h-2 w-2 animate-pulse rounded-full bg-emerald-500"></div>
              <span className="text-xs font-medium text-emerald-500">
                System Active
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-6 py-12">
        {/* Trading Section */}
        <section className="mb-12">
          <SectionHeader
            icon={<BarChart3 className="h-5 w-5 text-emerald-400" />}
            title="Trading System"
            description="Live market operations and portfolio management"
          />
          <div className="grid gap-6 sm:grid-cols-2">
            <NavCard
              href="/portfolio"
              title="Portfolio Command"
              description="Real-time performance metrics, asset allocation, and risk analysis dashboard."
              icon={<LayoutDashboard className="h-6 w-6 text-white" />}
              gradient="from-emerald-500/20 to-teal-500/5"
            />
            <NavCard
              href="/trades"
              title="Trade Proposals"
              description="AI-generated trade opportunities requiring human validation and execution."
              icon={<GitBranch className="h-6 w-6 text-white" />}
              gradient="from-blue-500/20 to-indigo-500/5"
            />
          </div>
        </section>

        {/* Research Section */}
        <section className="mb-12">
          <SectionHeader
            icon={<Bot className="h-5 w-5 text-indigo-400" />}
            title="Research & Intelligence"
            description="Automated analysis of academic papers and market strategies"
          />
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <NavCard
              href="/sources/new"
              title="Ingest Research"
              description="Submit new academic papers or articles for AI analysis and extraction."
              icon={<FileText className="h-6 w-6 text-white" />}
              gradient="from-indigo-500/20 to-violet-500/5"
            />
            <NavCard
              href="/sources"
              title="Knowledge Base"
              description="Archive of analyzed papers, validated concepts, and research notes."
              icon={<ScrollText className="h-6 w-6 text-white" />}
            />
            <NavCard
              href="/strategies"
              title="Strategy Bank"
              description="Extracted trading strategies ready for backtesting and deployment."
              icon={<Layers className="h-6 w-6 text-white" />}
              gradient="from-amber-500/20 to-orange-500/5"
            />
            <NavCard
              href="/guides"
              title="Protocol Guide"
              description="Synthesized best practices and operating procedures."
              icon={<ShieldCheck className="h-6 w-6 text-white" />}
            />
            <NavCard
              href="/chat"
              title="Neural Chat"
              description="Interactive dialogue with the research engine for deep insights."
              icon={<Bot className="h-6 w-6 text-white" />}
              gradient="from-pink-500/20 to-rose-500/5"
            />
            <NavCard
              href="/logs"
              title="System Logs"
              description="Granular activity logs of all agentic operations and state changes."
              icon={<Cpu className="h-6 w-6 text-white" />}
            />
          </div>
        </section>

        {/* Pipeline Status */}
        <section>
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-md">
            <div className="border-b border-white/5 bg-white/5 px-6 py-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <Zap className="h-4 w-4 text-amber-400" />
                Pipeline Status
              </h3>
            </div>
            <div className="p-6">
              <div className="grid gap-4 md:grid-cols-4">
                <PipelineStep
                  number={1}
                  title="Source Agent"
                  status="ready"
                  description="Monitoring feeds"
                />
                <PipelineStep
                  number={2}
                  title="Reader Agent"
                  status="ready"
                  description="Processing queue"
                />
                <PipelineStep
                  number={3}
                  title="Synthesis Agent"
                  status="ready"
                  description="Generating insights"
                />
                <PipelineStep
                  number={4}
                  title="Chat Agent"
                  status="ready"
                  description="Standing by"
                />
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 bg-slate-950/50 py-8 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <p>Trading Agentic System v1.0.0</p>
            <p className="flex items-center gap-2">
              Powered by <span className="text-slate-400">Claude 3.5 Sonnet</span> &{" "}
              <span className="text-slate-400">Gemini 2.0 Flash</span>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function SectionHeader({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-6 flex items-end justify-between border-b border-white/10 pb-4">
      <div>
        <h2 className="flex items-center gap-2 text-xl font-semibold text-white">
          {icon}
          {title}
        </h2>
        <p className="mt-1 text-sm text-slate-400">{description}</p>
      </div>
    </div>
  );
}

function NavCard({
  href,
  title,
  description,
  icon,
  gradient = "from-slate-800/50 to-slate-900/50",
}: {
  href: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  gradient?: string;
}) {
  return (
    <Link
      href={href}
      className={`group relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br ${gradient} p-6 transition-all hover:border-emerald-500/30 hover:shadow-lg hover:shadow-emerald-500/10 hover:-translate-y-1`}
    >
      <div className="absolute right-0 top-0 -mr-6 -mt-6 h-24 w-24 opacity-10 blur-2xl transition-all group-hover:bg-emerald-500 group-hover:opacity-20" />
      
      <div className="relative mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-white/10 text-white backdrop-blur-md transition-colors group-hover:bg-emerald-500/20">
        {icon}
      </div>
      
      <h3 className="mb-2 text-lg font-semibold text-white group-hover:text-emerald-400">
        {title}
      </h3>
      <p className="text-sm leading-relaxed text-slate-400 group-hover:text-slate-300">
        {description}
      </p>

      <div className="mt-4 flex items-center text-xs font-medium text-slate-500 transition-colors group-hover:text-emerald-500">
        Access Module <ArrowRight className="ml-1 h-3 w-3" />
      </div>
    </Link>
  );
}

function PipelineStep({
  number,
  title,
  status,
  description,
}: {
  number: number;
  title: string;
  status: "ready" | "pending";
  description: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-white/5 bg-white/5 p-4 transition-all hover:bg-white/10">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs font-bold text-slate-400">
          {number}
        </div>
        <div
          className={`flex h-2 w-2 rounded-full ${
            status === "ready"
              ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
              : "bg-amber-500"
          }`}
        />
      </div>
      <div className="mb-1 text-sm font-medium text-slate-200">{title}</div>
      <div className="text-xs text-slate-500">{description}</div>
    </div>
  );
}
