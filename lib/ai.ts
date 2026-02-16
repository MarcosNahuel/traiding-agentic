import { createGoogleGenerativeAI } from "@ai-sdk/google";

// Lazy getter for google instance
function getGoogle() {
  return createGoogleGenerativeAI({
    apiKey: process.env.GOOGLE_AI_API_KEY || process.env.GOOGLE_GENERATIVE_AI_API_KEY,
  });
}

// Export the getter as google
export const google = getGoogle();

export const gemini = google("gemini-2.5-flash");

export const embeddingModel = google.embedding("gemini-embedding-001");
