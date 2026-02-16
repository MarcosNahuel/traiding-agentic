/**
 * Minimal Telegram Bot API wrapper for notifications.
 *
 * Environment variables:
 *   TELEGRAM_BOT_TOKEN - Bot token from @BotFather
 *   TELEGRAM_CHAT_ID   - Chat ID of the operator
 */

const TELEGRAM_API = "https://api.telegram.org";

function getToken(): string {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) throw new Error("Missing TELEGRAM_BOT_TOKEN");
  return token;
}

function getOperatorChatId(): string {
  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!chatId) throw new Error("Missing TELEGRAM_CHAT_ID");
  return chatId;
}

interface TelegramResponse {
  ok: boolean;
  description?: string;
}

export async function sendMessage(
  chatId: string,
  text: string,
  parseMode: "HTML" | "Markdown" | "MarkdownV2" = "HTML"
): Promise<TelegramResponse> {
  const token = getToken();
  const url = `${TELEGRAM_API}/bot${token}/sendMessage`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: parseMode,
    }),
  });

  const data = (await response.json()) as TelegramResponse;

  if (!data.ok) {
    throw new Error(`Telegram API error: ${data.description}`);
  }

  return data;
}

/**
 * Send an alert message to the operator's chat.
 */
export async function sendAlert(text: string): Promise<TelegramResponse> {
  return sendMessage(getOperatorChatId(), text);
}
