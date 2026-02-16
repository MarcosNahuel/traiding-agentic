/**
 * Text chunking utilities for papers
 */

export interface Chunk {
  content: string;
  chunkIndex: number;
  sectionTitle?: string;
  pageNumber?: number;
  metadata?: Record<string, unknown>;
}

export interface ChunkingOptions {
  maxChunkSize: number; // Maximum characters per chunk
  overlap: number; // Overlap between chunks in characters
  preserveParagraphs: boolean; // Try to keep paragraphs intact
}

const DEFAULT_OPTIONS: ChunkingOptions = {
  maxChunkSize: 1000,
  overlap: 200,
  preserveParagraphs: true,
};

/**
 * Split text into overlapping chunks
 */
export function chunkText(
  text: string,
  options: Partial<ChunkingOptions> = {}
): Chunk[] {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const chunks: Chunk[] = [];

  // Clean up text
  const cleanText = text
    .replace(/\r\n/g, "\n") // Normalize line endings
    .replace(/\n{3,}/g, "\n\n") // Remove excessive newlines
    .trim();

  if (cleanText.length === 0) {
    return [];
  }

  // If text is smaller than max chunk size, return as single chunk
  if (cleanText.length <= opts.maxChunkSize) {
    return [
      {
        content: cleanText,
        chunkIndex: 0,
      },
    ];
  }

  // Split by paragraphs if requested
  const paragraphs = opts.preserveParagraphs
    ? cleanText.split(/\n\n+/)
    : [cleanText];

  let currentChunk = "";
  let chunkIndex = 0;

  for (let i = 0; i < paragraphs.length; i++) {
    const paragraph = paragraphs[i].trim();

    if (!paragraph) continue;

    // If adding this paragraph would exceed max size
    if (currentChunk.length + paragraph.length + 2 > opts.maxChunkSize) {
      // Save current chunk if it has content
      if (currentChunk.length > 0) {
        chunks.push({
          content: currentChunk.trim(),
          chunkIndex,
        });
        chunkIndex++;

        // Start new chunk with overlap from previous chunk
        const words = currentChunk.split(/\s+/);
        const overlapWords = Math.ceil(opts.overlap / 6); // Approximate words for overlap
        currentChunk =
          words.slice(-overlapWords).join(" ") + "\n\n" + paragraph;
      } else {
        // Paragraph itself is too long, split it
        const words = paragraph.split(/\s+/);
        let wordChunk = "";

        for (const word of words) {
          if (wordChunk.length + word.length + 1 > opts.maxChunkSize) {
            if (wordChunk.length > 0) {
              chunks.push({
                content: wordChunk.trim(),
                chunkIndex,
              });
              chunkIndex++;

              // Add overlap
              const chunkWords = wordChunk.split(/\s+/);
              const overlapWords = Math.ceil(opts.overlap / 6);
              wordChunk = chunkWords.slice(-overlapWords).join(" ") + " " + word;
            } else {
              // Single word is too long (rare), just add it
              chunks.push({
                content: word,
                chunkIndex,
              });
              chunkIndex++;
              wordChunk = "";
            }
          } else {
            wordChunk += (wordChunk ? " " : "") + word;
          }
        }

        currentChunk = wordChunk;
      }
    } else {
      // Add paragraph to current chunk
      currentChunk += (currentChunk ? "\n\n" : "") + paragraph;
    }
  }

  // Add final chunk
  if (currentChunk.trim().length > 0) {
    chunks.push({
      content: currentChunk.trim(),
      chunkIndex,
    });
  }

  return chunks;
}

/**
 * Extract section title from chunk content
 * Looks for common heading patterns
 */
export function extractSectionTitle(content: string): string | undefined {
  // Look for common heading patterns
  const lines = content.split("\n");
  for (const line of lines.slice(0, 3)) {
    // Check first 3 lines
    const trimmed = line.trim();

    // Pattern 1: All caps (INTRODUCTION, METHODOLOGY, etc.)
    if (trimmed.length > 3 && trimmed.length < 50 && trimmed === trimmed.toUpperCase()) {
      return trimmed;
    }

    // Pattern 2: Numbered sections (1. Introduction, 2.1 Methods, etc.)
    const numberedMatch = trimmed.match(/^(\d+\.)+\s*([A-Z][A-Za-z\s]+)$/);
    if (numberedMatch) {
      return numberedMatch[2].trim();
    }

    // Pattern 3: Title Case headings
    if (
      trimmed.length > 3 &&
      trimmed.length < 50 &&
      /^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$/.test(trimmed)
    ) {
      return trimmed;
    }
  }

  return undefined;
}

/**
 * Chunk paper content with section detection
 */
export function chunkPaper(
  content: string,
  options: Partial<ChunkingOptions> = {}
): Chunk[] {
  const chunks = chunkText(content, options);

  // Extract section titles
  return chunks.map((chunk) => ({
    ...chunk,
    sectionTitle: extractSectionTitle(chunk.content),
  }));
}
