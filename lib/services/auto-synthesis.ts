/**
 * Auto-trigger synthesis when N papers are processed
 */

import { createServerClient } from "@/lib/supabase";
import { synthesizeGuide } from "@/lib/agents/synthesis-agent";

interface AutoSynthesisConfig {
  threshold: number; // Number of papers to trigger synthesis
  enabled: boolean;
}

const DEFAULT_CONFIG: AutoSynthesisConfig = {
  threshold: 5, // Default: synthesize after 5 new papers
  enabled: true,
};

/**
 * Check if synthesis should be triggered and run it if needed
 */
export async function checkAndTriggerSynthesis(
  config: Partial<AutoSynthesisConfig> = {}
): Promise<{
  triggered: boolean;
  reason?: string;
}> {
  const supabase = createServerClient();
  const { threshold, enabled } = { ...DEFAULT_CONFIG, ...config };

  if (!enabled) {
    return { triggered: false, reason: "Auto-synthesis is disabled" };
  }

  // 1. Get the last synthesis timestamp
  const { data: lastSynthesis } = await supabase
    .from("synthesis_results")
    .select("created_at")
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  const lastSynthesisDate = lastSynthesis
    ? new Date(lastSynthesis.created_at)
    : new Date(0); // If no synthesis exists, use epoch

  // 2. Count processed papers since last synthesis
  const { data: processedPapers, count } = await supabase
    .from("sources")
    .select("id", { count: "exact", head: true })
    .eq("status", "processed")
    .gte("updated_at", lastSynthesisDate.toISOString());

  const newPapersCount = count || 0;

  console.log(
    `Auto-synthesis check: ${newPapersCount} new papers (threshold: ${threshold})`
  );

  // 3. Check if threshold is met
  if (newPapersCount < threshold) {
    return {
      triggered: false,
      reason: `Not enough papers (${newPapersCount}/${threshold})`,
    };
  }

  // 4. Trigger synthesis
  console.log(
    `🤖 Auto-triggering synthesis: ${newPapersCount} papers processed`
  );

  try {
    await synthesizeGuide({
      minConfidence: 6,
      minEvidenceStrength: "moderate",
    });

    return {
      triggered: true,
      reason: `Synthesized ${newPapersCount} new papers`,
    };
  } catch (error) {
    console.error("Auto-synthesis failed:", error);
    return {
      triggered: false,
      reason: `Failed: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

/**
 * Get current auto-synthesis status
 */
export async function getAutoSynthesisStatus(): Promise<{
  lastSynthesis?: Date;
  newPapersSinceLastSynthesis: number;
  threshold: number;
  readyToTrigger: boolean;
}> {
  const supabase = createServerClient();
  const threshold = DEFAULT_CONFIG.threshold;

  // Get last synthesis
  const { data: lastSynthesis } = await supabase
    .from("synthesis_results")
    .select("created_at")
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  const lastSynthesisDate = lastSynthesis
    ? new Date(lastSynthesis.created_at)
    : new Date(0);

  // Count new papers
  const { count } = await supabase
    .from("sources")
    .select("id", { count: "exact", head: true })
    .eq("status", "processed")
    .gte("updated_at", lastSynthesisDate.toISOString());

  const newPapersCount = count || 0;

  return {
    lastSynthesis: lastSynthesis ? lastSynthesisDate : undefined,
    newPapersSinceLastSynthesis: newPapersCount,
    threshold,
    readyToTrigger: newPapersCount >= threshold,
  };
}
