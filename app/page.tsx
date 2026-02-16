/**
 * Home page - Trading Research AI Dashboard
 */

import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white dark:bg-black">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800">
        <div className="mx-auto max-w-7xl px-6 py-6">
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-white">
            Trading Research AI
          </h1>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Sistema agéntico de investigación y ejecución de estrategias
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-6 py-12">
        {/* Trading Section */}
        <section className="mb-16">
          <h2 className="mb-6 text-lg font-medium text-gray-900 dark:text-white">
            Trading System
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <NavCard
              href="/portfolio"
              title="Portfolio"
              description="Dashboard en tiempo real con métricas de performance"
            />
            <NavCard
              href="/trades"
              title="Trade Proposals"
              description="Gestión y aprobación de propuestas de trading"
            />
          </div>
        </section>

        {/* Research Section */}
        <section>
          <h2 className="mb-6 text-lg font-medium text-gray-900 dark:text-white">
            Research System
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <NavCard
              href="/sources/new"
              title="Agregar Paper"
              description="Evaluar nuevo paper académico o artículo"
            />
            <NavCard
              href="/sources"
              title="Sources"
              description="Papers evaluados y aprobados"
            />
            <NavCard
              href="/strategies"
              title="Estrategias"
              description="Estrategias extraídas de papers"
            />
            <NavCard
              href="/guides"
              title="Trading Guide"
              description="Guía sintetizada de mejores prácticas"
            />
            <NavCard
              href="/chat"
              title="Chat AI"
              description="Preguntas sobre la investigación"
            />
            <NavCard
              href="/logs"
              title="System Logs"
              description="Actividad de agentes y sistema"
            />
          </div>
        </section>

        {/* Pipeline Status */}
        <section className="mt-16">
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-6 dark:border-gray-800 dark:bg-gray-900">
            <h3 className="mb-4 text-sm font-medium text-gray-900 dark:text-white">
              Pipeline del Sistema
            </h3>
            <div className="space-y-3">
              <PipelineStep number={1} title="Source Agent" status="ready" />
              <PipelineStep number={2} title="Reader Agent" status="ready" />
              <PipelineStep number={3} title="Synthesis Agent" status="ready" />
              <PipelineStep number={4} title="Chat Agent" status="ready" />
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 dark:border-gray-800">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <p className="text-xs text-gray-500 dark:text-gray-500">
            Powered by Claude Sonnet 4.5 & Gemini 2.5 Flash
          </p>
        </div>
      </footer>
    </div>
  );
}

function NavCard({
  href,
  title,
  description,
}: {
  href: string;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-lg border border-gray-200 bg-white p-5 transition-all hover:border-gray-300 hover:bg-gray-50 dark:border-gray-800 dark:bg-black dark:hover:border-gray-700 dark:hover:bg-gray-900"
    >
      <h3 className="mb-1.5 font-medium text-gray-900 dark:text-white">
        {title}
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
    </Link>
  );
}

function PipelineStep({
  number,
  title,
  status,
}: {
  number: number;
  title: string;
  status: "ready" | "pending";
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
        {number}
      </div>
      <div className="flex-1">
        <span className="text-sm text-gray-700 dark:text-gray-300">{title}</span>
      </div>
      <div
        className={`text-xs ${
          status === "ready"
            ? "text-green-600 dark:text-green-500"
            : "text-yellow-600 dark:text-yellow-500"
        }`}
      >
        {status === "ready" ? "✓ Ready" : "Pending"}
      </div>
    </div>
  );
}
