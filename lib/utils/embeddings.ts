/**
 * Embedding utilities
 */

/**
 * Truncate embedding to specified dimensions
 * Common practice when embedding model outputs more dimensions than needed
 */
export function truncateEmbedding(
  embedding: number[],
  targetDimensions: number
): number[] {
  if (embedding.length <= targetDimensions) {
    return embedding;
  }
  return embedding.slice(0, targetDimensions);
}

/**
 * Validate embedding dimensions
 */
export function validateEmbedding(
  embedding: number[],
  expectedDimensions: number
): boolean {
  return embedding.length === expectedDimensions;
}
