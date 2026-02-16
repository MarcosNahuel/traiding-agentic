/**
 * Helper for launching background jobs via Vercel Background Functions.
 *
 * In Vercel, a Background Function is any API route that returns a response
 * immediately but continues executing. The pattern:
 *   1. Client POST /api/jobs/foo
 *   2. Route returns { jobId } immediately
 *   3. Actual work runs in the same invocation after response is sent
 *
 * For local dev, jobs run synchronously.
 */

import { type NextRequest, NextResponse } from "next/server";

export interface JobResult {
  jobId: string;
  status: "queued" | "completed" | "error";
  result?: unknown;
  error?: string;
}

/**
 * Wrap an async job handler in a background-compatible API route.
 * Returns a 202 Accepted immediately, then runs the job.
 */
export function createBackgroundJob(
  handler: (req: NextRequest) => Promise<unknown>
) {
  return async function POST(req: NextRequest) {
    const jobId = crypto.randomUUID();

    // Fire-and-forget: run the handler without awaiting
    // In Vercel, the function continues after response is sent
    handler(req).catch((error) => {
      console.error(`[background-job:${jobId}] Error:`, error);
    });

    return NextResponse.json(
      { jobId, status: "queued" } satisfies JobResult,
      { status: 202 }
    );
  };
}
