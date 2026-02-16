"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AppShell } from "@/components/ui/AppShell";

const SOURCE_TYPES = ["paper", "article", "repo", "book", "video"];

export default function NewSourcePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [sourceType, setSourceType] = useState("paper");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!url.trim()) {
      setError("La URL es obligatoria.");
      return;
    }

    try {
      setSubmitting(true);
      const res = await fetch("/api/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: url.trim(),
          sourceType,
        }),
      });

      const payload = (await res.json()) as {
        error?: string;
        sourceId?: string;
        message?: string;
      };

      if (!res.ok) {
        throw new Error(payload.error ?? "No se pudo crear el source");
      }

      setSuccessMessage(
        payload.message ?? "Source creado. Se inicio la evaluacion automatica."
      );
      setUrl("");

      setTimeout(() => {
        router.push("/sources");
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell
      title="Agregar Source"
      description="Carga una URL para que el sistema la busque, evalúe y procese."
      actions={
        <Link
          href="/sources"
          className="rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10"
        >
          Volver a Sources
        </Link>
      }
    >
      <div className="mx-auto max-w-3xl rounded-xl border border-white/10 bg-black/30 p-6">
        <form onSubmit={onSubmit} className="space-y-5">
          <div>
            <label
              htmlFor="source-url"
              className="mb-2 block text-sm font-medium text-slate-200"
            >
              URL
            </label>
            <input
              id="source-url"
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://arxiv.org/abs/..."
              className="w-full rounded-md border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
              required
            />
          </div>

          <div>
            <label
              htmlFor="source-type"
              className="mb-2 block text-sm font-medium text-slate-200"
            >
              Tipo
            </label>
            <select
              id="source-type"
              value={sourceType}
              onChange={(event) => setSourceType(event.target.value)}
              className="w-full rounded-md border border-white/15 bg-slate-950/80 px-3 py-2 text-sm text-white outline-none ring-cyan-400 transition focus:ring-2"
            >
              {SOURCE_TYPES.map((type) => (
                <option key={type} value={type} className="bg-slate-900">
                  {type}
                </option>
              ))}
            </select>
          </div>

          {error ? (
            <div className="rounded-md border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-200">
              {error}
            </div>
          ) : null}

          {successMessage ? (
            <div className="rounded-md border border-emerald-400/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
              {successMessage}
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
            >
              {submitting ? "Enviando..." : "Crear Source"}
            </button>
            <Link
              href="/sources"
              className="rounded-md border border-white/20 px-4 py-2 text-sm text-white hover:bg-white/10"
            >
              Cancelar
            </Link>
          </div>
        </form>
      </div>
    </AppShell>
  );
}

