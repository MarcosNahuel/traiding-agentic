/**
 * SSRF-safe URL content fetcher.
 *
 * - Only allows http/https
 * - Blocks private IPs (10.x, 172.16-31.x, 192.168.x, 169.254.x, 127.x)
 * - Blocks cloud metadata endpoints (169.254.169.254)
 * - 10s timeout
 * - Max 5MB response
 * - Content-type whitelist
 * - Max 3 redirects
 */

const MAX_RESPONSE_SIZE = 20 * 1024 * 1024; // 20MB (for academic papers)
const TIMEOUT_MS = 30_000; // 30 seconds
const MAX_REDIRECTS = 5;

const ALLOWED_CONTENT_TYPES = [
  "text/html",
  "text/plain",
  "application/pdf",
  "application/json",
];

const PRIVATE_IP_PATTERNS = [
  /^127\./,
  /^10\./,
  /^172\.(1[6-9]|2\d|3[01])\./,
  /^192\.168\./,
  /^169\.254\./,
  /^0\./,
  /^fc00:/i,
  /^fe80:/i,
  /^::1$/,
  /^localhost$/i,
];

function isPrivateHost(hostname: string): boolean {
  return PRIVATE_IP_PATTERNS.some((pattern) => pattern.test(hostname));
}

export class FetchError extends Error {
  constructor(
    message: string,
    public readonly code: string
  ) {
    super(message);
    this.name = "FetchError";
  }
}

export interface FetchResult {
  content: string;
  contentType: string;
  url: string;
  statusCode: number;
}

export async function safeFetch(urlString: string): Promise<FetchResult> {
  let url: URL;
  try {
    url = new URL(urlString);
  } catch {
    throw new FetchError("Invalid URL", "INVALID_URL");
  }

  // Protocol check
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new FetchError(
      `Blocked protocol: ${url.protocol}`,
      "BLOCKED_PROTOCOL"
    );
  }

  // Private IP check
  if (isPrivateHost(url.hostname)) {
    throw new FetchError(
      `Blocked private/internal host: ${url.hostname}`,
      "BLOCKED_HOST"
    );
  }

  let currentUrl = urlString;
  let redirectCount = 0;

  while (redirectCount <= MAX_REDIRECTS) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const response = await fetch(currentUrl, {
        signal: controller.signal,
        redirect: "manual",
        headers: {
          "User-Agent": "TradingAgentic/1.0 (research-bot)",
        },
      });

      // Handle redirects manually to validate each hop
      if ([301, 302, 303, 307, 308].includes(response.status)) {
        const location = response.headers.get("location");
        if (!location) {
          throw new FetchError("Redirect without location", "INVALID_REDIRECT");
        }

        const redirectUrl = new URL(location, currentUrl);
        if (isPrivateHost(redirectUrl.hostname)) {
          throw new FetchError(
            `Redirect to private host blocked: ${redirectUrl.hostname}`,
            "BLOCKED_REDIRECT"
          );
        }

        currentUrl = redirectUrl.toString();
        redirectCount++;
        continue;
      }

      if (!response.ok) {
        throw new FetchError(
          `HTTP ${response.status}: ${response.statusText}`,
          "HTTP_ERROR"
        );
      }

      // Content-type check
      const contentType = response.headers.get("content-type") || "";
      const baseType = contentType.split(";")[0].trim().toLowerCase();
      if (!ALLOWED_CONTENT_TYPES.some((t) => baseType.startsWith(t))) {
        throw new FetchError(
          `Blocked content-type: ${baseType}`,
          "BLOCKED_CONTENT_TYPE"
        );
      }

      // Size check
      const contentLength = response.headers.get("content-length");
      if (contentLength && parseInt(contentLength) > MAX_RESPONSE_SIZE) {
        throw new FetchError(
          `Response too large: ${contentLength} bytes`,
          "TOO_LARGE"
        );
      }

      const content = await response.text();
      if (content.length > MAX_RESPONSE_SIZE) {
        throw new FetchError(
          `Response body too large: ${content.length} bytes`,
          "TOO_LARGE"
        );
      }

      return {
        content,
        contentType: baseType,
        url: currentUrl,
        statusCode: response.status,
      };
    } catch (error) {
      if (error instanceof FetchError) throw error;
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new FetchError("Request timed out", "TIMEOUT");
      }
      throw new FetchError(
        `Fetch failed: ${error instanceof Error ? error.message : String(error)}`,
        "FETCH_ERROR"
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  throw new FetchError(
    `Too many redirects (max ${MAX_REDIRECTS})`,
    "TOO_MANY_REDIRECTS"
  );
}
