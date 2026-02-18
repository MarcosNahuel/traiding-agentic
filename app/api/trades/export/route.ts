import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const from = searchParams.get("from");
  const to = searchParams.get("to");
  const status = searchParams.get("status");

  try {
    const supabase = createServerClient();
    let query = supabase
      .from("trade_proposals")
      .select("*")
      .order("created_at", { ascending: false });

    if (from) query = query.gte("created_at", from);
    if (to) query = query.lte("created_at", to);
    if (status) query = query.eq("status", status);

    const { data, error } = await query.limit(1000);
    if (error) throw error;

    const rows = data || [];
    if (rows.length === 0) {
      return new Response("No data found", { status: 404 });
    }

    // Build CSV
    const headers = [
      "id", "type", "symbol", "quantity", "price", "order_type",
      "status", "retry_count", "error_message", "binance_order_id",
      "executed_price", "executed_quantity", "commission", "commission_asset",
      "risk_score", "reasoning", "strategy_id",
      "created_at", "executed_at", "updated_at",
    ];

    const csvLines = [headers.join(",")];
    for (const row of rows) {
      const values = headers.map((h) => {
        const val = row[h];
        if (val === null || val === undefined) return "";
        const str = String(val).replace(/"/g, '""');
        return str.includes(",") || str.includes('"') || str.includes("\n")
          ? `"${str}"`
          : str;
      });
      csvLines.push(values.join(","));
    }

    const csv = csvLines.join("\n");
    return new Response(csv, {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": `attachment; filename="trades_${new Date().toISOString().slice(0, 10)}.csv"`,
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
