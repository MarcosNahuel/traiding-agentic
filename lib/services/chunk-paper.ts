/**
 * Service to chunk papers and generate embeddings
 */

import { embed } from "ai";
import { google } from "@/lib/ai";
import { createServerClient } from "@/lib/supabase";
import { chunkPaper } from "@/lib/utils/chunking";
import { truncateEmbedding } from "@/lib/utils/embeddings";

interface ChunkPaperParams {
  sourceId: string;
  content: string;
  maxChunkSize?: number;
  overlap?: number;
}

interface ChunkPaperResult {
  chunksCreated: number;
  totalCharacters: number;
  duration: number;
  cost: number;
}

export async function chunkAndEmbedPaper(
  params: ChunkPaperParams
): Promise<ChunkPaperResult> {
  const supabase = createServerClient();
  const { sourceId, content, maxChunkSize = 1000, overlap = 200 } = params;

  const startTime = Date.now();

  // 1. Chunk the paper
  const chunks = chunkPaper(content, {
    maxChunkSize,
    overlap,
    preserveParagraphs: true,
  });

  console.log(`Created ${chunks.length} chunks from paper`);

  // 2. Delete existing chunks for this source (if any)
  await supabase.from("paper_chunks").delete().eq("source_id", sourceId);

  // 3. Generate embeddings and insert chunks
  let totalCost = 0;

  for (const chunk of chunks) {
    // Generate embedding
    const { embedding: rawEmbedding } = await embed({
      model: google.embedding("gemini-embedding-001"),
      value: chunk.content,
    });

    // Truncate to 1024 dimensions
    const embedding = truncateEmbedding(rawEmbedding, 1024);

    // Insert into database
    const { error } = await supabase.from("paper_chunks").insert({
      source_id: sourceId,
      chunk_index: chunk.chunkIndex,
      content: chunk.content,
      section_title: chunk.sectionTitle,
      page_number: chunk.pageNumber,
      embedding: embedding,
      metadata: chunk.metadata || {},
    });

    if (error) {
      console.error(
        `Failed to insert chunk ${chunk.chunkIndex}:`,
        error.message
      );
      // Continue with next chunk
    }

    // Estimate cost (very rough - embedding API costs are minimal)
    totalCost += 0.00001; // ~$0.00001 per embedding
  }

  const duration = Date.now() - startTime;
  const totalCharacters = chunks.reduce((sum, c) => sum + c.content.length, 0);

  console.log(
    `Chunked and embedded paper in ${(duration / 1000).toFixed(1)}s (${chunks.length} chunks, ${totalCharacters} chars)`
  );

  return {
    chunksCreated: chunks.length,
    totalCharacters,
    duration,
    cost: totalCost,
  };
}
