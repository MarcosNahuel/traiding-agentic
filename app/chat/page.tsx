"use client";

import { FormEvent, useMemo, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";

type Role = "user" | "assistant" | "system";

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
}

const SUGGESTED_QUESTIONS = [
  "Que estrategia parece mas robusta para mercado lateral?",
  "Compara momentum vs mean reversion con lo que hay cargado.",
  "Que indicadores aparecen con mayor frecuencia?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: crypto.randomUUID(),
      role: "system",
      content:
        "Interfaz de chat lista. Si el endpoint /api/chat no existe, se mostrara el error para que puedas validarlo rapido.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const canSend = useMemo(() => input.trim().length > 0 && !sending, [input, sending]);

  const pushMessage = (role: Role, content: string) => {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role, content }]);
  };

  const send = async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || sending) return;

    pushMessage("user", trimmed);
    setInput("");
    setSending(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      const text = await res.text();
      let parsed: unknown = null;
      try {
        parsed = text ? JSON.parse(text) : null;
      } catch {
        parsed = null;
      }

      if (!res.ok) {
        const apiError =
          parsed && typeof parsed === "object" && "error" in parsed
            ? String((parsed as { error?: unknown }).error)
            : `HTTP ${res.status}`;

        pushMessage(
          "assistant",
          `No se pudo completar el chat (${apiError}). Si el status es 404, falta implementar /api/chat.`
        );
        return;
      }

      const answer =
        parsed && typeof parsed === "object" && "answer" in parsed
          ? String((parsed as { answer?: unknown }).answer)
          : parsed && typeof parsed === "object" && "response" in parsed
            ? String((parsed as { response?: unknown }).response)
            : text || "Respuesta vacia del servidor.";

      pushMessage("assistant", answer);
    } catch (err) {
      pushMessage(
        "assistant",
        `Error de red: ${err instanceof Error ? err.message : "Error inesperado"}`
      );
    } finally {
      setSending(false);
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await send(input);
  };

  return (
    <AppShell
      title="Chat"
      description="Interfaz conversacional conectada al endpoint /api/chat cuando este disponible."
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <aside className="rounded-xl border border-white/10 bg-black/30 p-4 lg:col-span-4">
          <h2 className="text-sm uppercase tracking-wide text-slate-300">
            Preguntas sugeridas
          </h2>
          <div className="mt-3 space-y-2">
            {SUGGESTED_QUESTIONS.map((question) => (
              <button
                key={question}
                onClick={() => void send(question)}
                disabled={sending}
                className="w-full rounded-md border border-white/15 bg-white/5 px-3 py-2 text-left text-sm text-slate-200 transition hover:bg-white/10 disabled:opacity-60"
              >
                {question}
              </button>
            ))}
          </div>
        </aside>

        <section className="rounded-xl border border-white/10 bg-black/30 p-4 lg:col-span-8">
          <div className="mb-4 max-h-[58vh] space-y-3 overflow-auto rounded-md border border-white/10 bg-slate-950/70 p-3">
            {messages.map((message) => (
              <MessageBubble key={message.id} role={message.role} content={message.content} />
            ))}
          </div>

          <form onSubmit={onSubmit} className="flex gap-2">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Escribe tu pregunta..."
              className="flex-1 rounded-md border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
            />
            <button
              type="submit"
              disabled={!canSend}
              className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
            >
              {sending ? "Enviando..." : "Enviar"}
            </button>
          </form>
        </section>
      </div>
    </AppShell>
  );
}

function MessageBubble({ role, content }: { role: Role; content: string }) {
  const style =
    role === "user"
      ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-100"
      : role === "assistant"
        ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
        : "border-slate-400/30 bg-slate-500/10 text-slate-100";

  const label = role === "user" ? "Tu" : role === "assistant" ? "AI" : "Sistema";

  return (
    <div className={`rounded-md border p-3 text-sm ${style}`}>
      <p className="mb-1 text-xs uppercase tracking-wide opacity-80">{label}</p>
      <p className="whitespace-pre-wrap">{content}</p>
    </div>
  );
}

