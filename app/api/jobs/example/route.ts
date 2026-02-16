import { NextResponse } from "next/server";

/**
 * Example background job: demonstrates the pattern of
 * fetch URL → generate embedding → store in pgvector.
 *
 * This is a placeholder — actual implementation in Fase 1.
 */
export async function POST() {
  const jobId = crypto.randomUUID();

  // In production, the actual work would happen here after returning:
  // 1. safeFetch(url) to get content
  // 2. embed({ model: embeddingModel, value: content })
  // 3. supabase.from('paper_chunks').insert({ ... })

  return NextResponse.json(
    { jobId, status: "queued", message: "Example job — implement in Fase 1" },
    { status: 202 }
  );
}
