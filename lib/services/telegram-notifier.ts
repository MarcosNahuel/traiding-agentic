/**
 * Telegram Notification Service
 *
 * Sends notifications to Telegram for:
 * - Trade proposals requiring approval
 * - Trade executions
 * - Risk alerts
 * - Position updates
 */

const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

// ============================================================================
// TYPES
// ============================================================================

interface TelegramMessage {
  text: string;
  parseMode?: "HTML" | "Markdown";
  disableNotification?: boolean;
  replyMarkup?: any;
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function isConfigured(): boolean {
  return !!(TELEGRAM_BOT_TOKEN && TELEGRAM_CHAT_ID);
}

async function sendMessage(message: TelegramMessage): Promise<boolean> {
  if (!isConfigured()) {
    console.warn(
      "Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
    );
    return false;
  }

  try {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: TELEGRAM_CHAT_ID,
        text: message.text,
        parse_mode: message.parseMode || "HTML",
        disable_notification: message.disableNotification || false,
        reply_markup: message.replyMarkup,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      console.error("Telegram API error:", error);
      return false;
    }

    return true;
  } catch (error) {
    console.error("Failed to send Telegram message:", error);
    return false;
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ============================================================================
// NOTIFICATION FUNCTIONS
// ============================================================================

/**
 * Notify about new trade proposal requiring approval
 */
export async function notifyTradeProposal(proposal: {
  id: string;
  type: "buy" | "sell";
  symbol: string;
  quantity: number;
  price?: number;
  notional: number;
  riskScore: number;
  reasoning?: string;
  autoApproved: boolean;
}): Promise<boolean> {
  if (!isConfigured()) return false;

  const emoji = proposal.type === "buy" ? "🟢" : "🔴";
  const status = proposal.autoApproved
    ? "✅ <b>AUTO-APPROVED</b>"
    : "⚠️ <b>REQUIRES APPROVAL</b>";

  const text = `
${emoji} <b>New Trade Proposal</b>

${status}

<b>Symbol:</b> ${proposal.symbol}
<b>Type:</b> ${proposal.type.toUpperCase()}
<b>Quantity:</b> ${proposal.quantity}
${proposal.price ? `<b>Price:</b> $${proposal.price.toLocaleString()}` : "<b>Type:</b> MARKET"}
<b>Notional:</b> $${proposal.notional.toFixed(2)}
<b>Risk Score:</b> ${proposal.riskScore}/100

${proposal.reasoning ? `<b>Reasoning:</b>\n${escapeHtml(proposal.reasoning.substring(0, 200))}${proposal.reasoning.length > 200 ? "..." : ""}` : ""}

<b>Proposal ID:</b> <code>${proposal.id}</code>
  `.trim();

  // Add inline buttons for approval if not auto-approved
  let replyMarkup;
  if (!proposal.autoApproved) {
    replyMarkup = {
      inline_keyboard: [
        [
          {
            text: "✅ Approve",
            callback_data: `approve_${proposal.id}`,
          },
          {
            text: "❌ Reject",
            callback_data: `reject_${proposal.id}`,
          },
        ],
      ],
    };
  }

  return sendMessage({
    text,
    parseMode: "HTML",
    replyMarkup,
  });
}

/**
 * Notify about executed trade
 */
export async function notifyTradeExecuted(execution: {
  proposalId: string;
  type: "buy" | "sell";
  symbol: string;
  orderId: number;
  executedPrice: number;
  executedQuantity: number;
  commission: number;
  commissionAsset?: string;
}): Promise<boolean> {
  if (!isConfigured()) return false;

  const emoji = execution.type === "buy" ? "🟢" : "🔴";
  const notional = execution.executedPrice * execution.executedQuantity;

  const text = `
${emoji} <b>Trade Executed</b>

<b>Symbol:</b> ${execution.symbol}
<b>Type:</b> ${execution.type.toUpperCase()}
<b>Quantity:</b> ${execution.executedQuantity}
<b>Price:</b> $${execution.executedPrice.toLocaleString()}
<b>Total:</b> $${notional.toFixed(2)}
<b>Commission:</b> ${execution.commission.toFixed(4)} ${execution.commissionAsset || "USDT"}

<b>Order ID:</b> <code>${execution.orderId}</code>
  `.trim();

  return sendMessage({
    text,
    parseMode: "HTML",
  });
}

/**
 * Notify about position closure with P&L
 */
export async function notifyPositionClosed(position: {
  symbol: string;
  side: "long" | "short";
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  realizedPnL: number;
  realizedPnLPercent: number;
  durationHours: number;
}): Promise<boolean> {
  if (!isConfigured()) return false;

  const isProfit = position.realizedPnL >= 0;
  const emoji = isProfit ? "💰" : "📉";
  const profitEmoji = isProfit ? "✅" : "❌";

  const text = `
${emoji} <b>Position Closed</b>

<b>Symbol:</b> ${position.symbol}
<b>Side:</b> ${position.side.toUpperCase()}
<b>Entry:</b> $${position.entryPrice.toLocaleString()}
<b>Exit:</b> $${position.exitPrice.toLocaleString()}
<b>Quantity:</b> ${position.quantity}

${profitEmoji} <b>P&L:</b> ${isProfit ? "+" : ""}$${position.realizedPnL.toFixed(2)} (${isProfit ? "+" : ""}${position.realizedPnLPercent.toFixed(2)}%)
<b>Duration:</b> ${position.durationHours.toFixed(1)}h
  `.trim();

  return sendMessage({
    text,
    parseMode: "HTML",
  });
}

/**
 * Notify about risk alert
 */
export async function notifyRiskAlert(alert: {
  eventType: string;
  severity: "info" | "warning" | "critical";
  message: string;
  details?: any;
}): Promise<boolean> {
  if (!isConfigured()) return false;

  const emojiMap = {
    info: "ℹ️",
    warning: "⚠️",
    critical: "🚨",
  };

  const emoji = emojiMap[alert.severity];

  const text = `
${emoji} <b>${alert.severity.toUpperCase()} ALERT</b>

<b>Type:</b> ${alert.eventType}
<b>Message:</b> ${escapeHtml(alert.message)}

${alert.details ? `<b>Details:</b>\n<code>${JSON.stringify(alert.details, null, 2).substring(0, 300)}</code>` : ""}
  `.trim();

  return sendMessage({
    text,
    parseMode: "HTML",
    disableNotification: alert.severity === "info",
  });
}

/**
 * Notify daily portfolio summary
 */
export async function notifyDailySummary(summary: {
  date: string;
  totalBalance: number;
  dailyPnL: number;
  dailyPnLPercent: number;
  openPositions: number;
  closedToday: number;
  winningTrades: number;
  losingTrades: number;
  currentDrawdown: number;
  currentDrawdownPercent: number;
}): Promise<boolean> {
  if (!isConfigured()) return false;

  const isProfit = summary.dailyPnL >= 0;
  const emoji = isProfit ? "📈" : "📉";

  const text = `
📊 <b>Daily Summary - ${summary.date}</b>

💰 <b>Balance:</b> $${summary.totalBalance.toLocaleString()}
${emoji} <b>Daily P&L:</b> ${isProfit ? "+" : ""}$${summary.dailyPnL.toFixed(2)} (${isProfit ? "+" : ""}${summary.dailyPnLPercent.toFixed(2)}%)

📂 <b>Positions:</b> ${summary.openPositions} open
📝 <b>Trades Today:</b> ${summary.closedToday}
${summary.closedToday > 0 ? `  ✅ Won: ${summary.winningTrades}\n  ❌ Lost: ${summary.losingTrades}` : ""}

📉 <b>Drawdown:</b> $${summary.currentDrawdown.toFixed(2)} (${summary.currentDrawdownPercent.toFixed(2)}%)
  `.trim();

  return sendMessage({
    text,
    parseMode: "HTML",
  });
}

/**
 * Notify system status
 */
export async function notifySystemStatus(status: {
  message: string;
  healthy: boolean;
  details?: any;
}): Promise<boolean> {
  if (!isConfigured()) return false;

  const emoji = status.healthy ? "✅" : "🔴";

  const text = `
${emoji} <b>System Status</b>

${escapeHtml(status.message)}

${status.details ? `<code>${JSON.stringify(status.details, null, 2).substring(0, 300)}</code>` : ""}
  `.trim();

  return sendMessage({
    text,
    parseMode: "HTML",
  });
}

// ============================================================================
// EXPORT ALL
// ============================================================================

export const TelegramNotifier = {
  notifyTradeProposal,
  notifyTradeExecuted,
  notifyPositionClosed,
  notifyRiskAlert,
  notifyDailySummary,
  notifySystemStatus,
  isConfigured,
};
