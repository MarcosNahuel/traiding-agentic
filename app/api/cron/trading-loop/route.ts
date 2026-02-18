/**
 * GET /api/cron/trading-loop - Automated trading loop
 *
 * This endpoint should be called periodically (e.g., every 5 minutes)
 * by Vercel Cron or external cron service.
 *
 * Flow:
 * 1. Evaluate all active strategies
 * 2. Generate trade signals
 * 3. Create proposals
 * 4. Execute auto-approved proposals
 * 5. Update portfolio metrics
 */

import { NextResponse } from "next/server";
import { runTradingLoop } from "@/lib/agents/trading-agent";
import { executeApprovedProposals } from "@/lib/trading/executor";
import { TelegramNotifier } from "@/lib/services/telegram-notifier";

export const maxDuration = 60; // 60 seconds for cron job

export async function GET() {
  const startTime = Date.now();

  // Kill switch: skip if trading is disabled
  const tradingEnabled = process.env.TRADING_ENABLED === "true";
  if (!tradingEnabled) {
    return NextResponse.json({
      success: true,
      skipped: true,
      reason: "TRADING_ENABLED is not true (kill switch)",
      timestamp: new Date().toISOString(),
    });
  }

  try {
    console.log("🔄 Trading loop started");

    // ========================================================================
    // STEP 1: Run Trading Agent (evaluate strategies)
    // ========================================================================

    const agentResult = await runTradingLoop();

    // ========================================================================
    // STEP 2: Execute Auto-Approved Proposals
    // ========================================================================

    const executionResult = await executeApprovedProposals();

    // ========================================================================
    // STEP 3: Log Results
    // ========================================================================

    const duration = ((Date.now() - startTime) / 1000).toFixed(2);

    const summary = {
      success: true,
      duration: `${duration}s`,
      agent: {
        signalsGenerated: agentResult.signalsGenerated,
        proposalsCreated: agentResult.proposalsCreated,
      },
      execution: {
        executed: executionResult.executed,
        failed: executionResult.failed,
      },
      timestamp: new Date().toISOString(),
    };

    console.log("✅ Trading loop completed:", summary);

    // ========================================================================
    // STEP 4: Send Telegram Notification (if configured)
    // ========================================================================

    if (
      TelegramNotifier.isConfigured() &&
      (agentResult.signalsGenerated > 0 || executionResult.executed > 0)
    ) {
      await TelegramNotifier.notifySystemStatus({
        healthy: true,
        message: `Trading Loop Complete\n\n📊 Signals: ${agentResult.signalsGenerated}\n📝 Proposals: ${agentResult.proposalsCreated}\n✅ Executed: ${executionResult.executed}`,
        details: summary,
      });
    }

    return NextResponse.json(summary);
  } catch (error) {
    console.error("❌ Trading loop error:", error);

    // Notify error via Telegram
    if (TelegramNotifier.isConfigured()) {
      await TelegramNotifier.notifySystemStatus({
        healthy: false,
        message: `Trading Loop Failed\n\n${error instanceof Error ? error.message : String(error)}`,
      });
    }

    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}
