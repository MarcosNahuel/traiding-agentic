/**
 * Jina AI Reader integration for fetching content from URLs (including PDFs)
 * https://jina.ai/reader
 *
 * Free tier: 20 requests/hour
 * Converts any URL to clean markdown
 */

export interface JinaFetchResult {
  content: string;
  title: string;
  url: string;
  usage?: {
    tokens: number;
  };
}

export class JinaFetchError extends Error {
  constructor(
    message: string,
    public readonly code: string
  ) {
    super(message);
    this.name = "JinaFetchError";
  }
}

/**
 * Fetch content using Jina AI Reader
 * Simply prepend https://r.jina.ai/ to any URL
 */
export async function jinaFetch(url: string): Promise<JinaFetchResult> {
  try {
    // Validate URL
    const parsedUrl = new URL(url);
    if (!["http:", "https:"].includes(parsedUrl.protocol)) {
      throw new JinaFetchError(
        `Invalid protocol: ${parsedUrl.protocol}`,
        "INVALID_PROTOCOL"
      );
    }

    // Bloquear hosts privados/internos (SSRF prevention)
    const PRIVATE_HOST_PATTERNS = [
      /^localhost$/i,
      /^127\./,
      /^10\./,
      /^192\.168\./,
      /^172\.(1[6-9]|2\d|3[01])\./,
      /^169\.254\./,
      /^::1$/,
      /^0\.0\.0\.0$/,
    ];
    const hostname = parsedUrl.hostname;
    if (PRIVATE_HOST_PATTERNS.some((p) => p.test(hostname))) {
      throw new JinaFetchError(
        `Blocked private/internal host: ${hostname}`,
        "SSRF_BLOCKED"
      );
    }

    // Prepend Jina Reader URL
    const jinaUrl = `https://r.jina.ai/${url}`;

    // Fetch with timeout
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120_000); // 2 minutes

    try {
      const response = await fetch(jinaUrl, {
        signal: controller.signal,
        headers: {
          "Accept": "application/json",
          "X-Return-Format": "markdown",
        },
      });

      if (!response.ok) {
        throw new JinaFetchError(
          `Jina API error: ${response.status} ${response.statusText}`,
          "JINA_API_ERROR"
        );
      }

      // Verificar tamaño máximo de respuesta (SSRF / DoS prevention)
      const MAX_CONTENT_BYTES = 5 * 1024 * 1024; // 5MB
      const contentLength = parseInt(response.headers.get("content-length") || "0");
      if (contentLength > MAX_CONTENT_BYTES) {
        throw new JinaFetchError(
          `Content too large: ${contentLength} bytes`,
          "CONTENT_TOO_LARGE"
        );
      }

      // Jina can return plain text or JSON depending on headers
      const contentType = response.headers.get("content-type") || "";

      let result: JinaFetchResult;

      if (contentType.includes("application/json")) {
        const json = await response.json();
        result = {
          content: json.data?.content || json.content || "",
          title: json.data?.title || json.title || "",
          url: json.data?.url || json.url || url,
          usage: json.data?.usage || json.usage,
        };
      } else {
        // Plain text response
        const text = await response.text();
        result = {
          content: text,
          title: "", // Will be extracted from content
          url,
        };
      }

      // Validate content
      if (!result.content || result.content.length < 100) {
        throw new JinaFetchError(
          "Content too short or empty",
          "CONTENT_TOO_SHORT"
        );
      }

      return result;
    } catch (error) {
      if (error instanceof JinaFetchError) throw error;
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new JinaFetchError("Request timed out after 2 minutes", "TIMEOUT");
      }
      throw new JinaFetchError(
        `Fetch failed: ${error instanceof Error ? error.message : String(error)}`,
        "FETCH_ERROR"
      );
    } finally {
      clearTimeout(timeout);
    }
  } catch (error) {
    if (error instanceof JinaFetchError) throw error;
    throw new JinaFetchError(
      `Failed to fetch via Jina: ${error instanceof Error ? error.message : String(error)}`,
      "UNKNOWN_ERROR"
    );
  }
}
