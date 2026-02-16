/**
 * Home page - Dashboard
 */

import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-16">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-white mb-4">
            🤖 Trading Research AI
          </h1>
          <p className="text-xl text-slate-300">
            Sistema agéntico de investigación de estrategias de trading
          </p>
        </div>

        {/* Main Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <ActionCard
            title="Agregar Paper"
            description="Evaluar un nuevo paper académico o artículo"
            href="/sources/new"
            icon="➕"
            color="bg-gradient-to-br from-blue-500 to-blue-700"
          />

          <ActionCard
            title="Ver Sources"
            description="Explorar papers evaluados y aprobados"
            href="/sources"
            icon="📚"
            color="bg-gradient-to-br from-green-500 to-green-700"
          />

          <ActionCard
            title="Estrategias"
            description="Ver todas las estrategias extraídas"
            href="/strategies"
            icon="⚡"
            color="bg-gradient-to-br from-purple-500 to-purple-700"
          />

          <ActionCard
            title="Trading Guide"
            description="Guía de trading sintetizada"
            href="/guides"
            icon="📖"
            color="bg-gradient-to-br from-orange-500 to-orange-700"
          />

          <ActionCard
            title="Chat AI"
            description="Hacer preguntas sobre la investigación"
            href="/chat"
            icon="💬"
            color="bg-gradient-to-br from-pink-500 to-pink-700"
          />

          <ActionCard
            title="Agent Logs"
            description="Ver actividad de los agentes"
            href="/logs"
            icon="📊"
            color="bg-gradient-to-br from-cyan-500 to-cyan-700"
          />
        </div>

        {/* Pipeline Info */}
        <div className="bg-slate-800 rounded-lg p-8">
          <h2 className="text-2xl font-bold text-white mb-6">
            🔄 Pipeline del Sistema
          </h2>
          <div className="space-y-4">
            <PipelineStep
              number={1}
              title="Source Agent"
              description="Evalúa papers y filtra por calidad/relevancia"
              status="ready"
            />
            <PipelineStep
              number={2}
              title="Reader Agent"
              description="Extrae estrategias concretas de papers aprobados"
              status="ready"
            />
            <PipelineStep
              number={3}
              title="Synthesis Agent"
              description="Combina hallazgos en guías estructuradas"
              status="ready"
            />
            <PipelineStep
              number={4}
              title="Chat Agent"
              description="Responde preguntas sobre la investigación (RAG)"
              status="ready"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="mt-16 text-center text-slate-400">
          <p>Powered by Claude Sonnet 4.5 & Gemini 2.5 Flash</p>
          <p className="text-sm mt-2">
            All agents operational • Cost per paper: ~$0.002
          </p>
        </div>
      </div>
    </div>
  );
}

function ActionCard({
  title,
  description,
  href,
  icon,
  color,
}: {
  title: string;
  description: string;
  href: string;
  icon: string;
  color: string;
}) {
  return (
    <Link href={href}>
      <div
        className={`${color} rounded-lg p-6 h-full hover:scale-105 transition-transform cursor-pointer shadow-lg`}
      >
        <div className="text-4xl mb-4">{icon}</div>
        <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
        <p className="text-white/80 text-sm">{description}</p>
      </div>
    </Link>
  );
}

function PipelineStep({
  number,
  title,
  description,
  status,
}: {
  number: number;
  title: string;
  description: string;
  status: "ready" | "pending";
}) {
  return (
    <div className="flex items-start gap-4">
      <div className="flex-shrink-0">
        <div className="w-10 h-10 rounded-full bg-purple-500 text-white flex items-center justify-center font-bold">
          {number}
        </div>
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-3 mb-1">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <span
            className={`text-xs px-2 py-1 rounded ${status === "ready" ? "bg-green-500" : "bg-yellow-500"} text-white`}
          >
            {status === "ready" ? "✓ Ready" : "Pending"}
          </span>
        </div>
        <p className="text-slate-400 text-sm">{description}</p>
      </div>
    </div>
  );
}
