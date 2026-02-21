import { NextRequest, NextResponse } from "next/server";
import { chat } from "@/lib/agents/chat-agent";

const TELEGRAM_API = "https://api.telegram.org";
const CHAT_TIMEOUT_MS = 12000;
const MAX_TELEGRAM_TEXT_CHARS = 3800;

type TelegramUpdate = {
  update_id?: number;
  message?: {
    message_id?: number;
    text?: string;
    chat?: { id?: number | string; type?: string };
    from?: { id?: number | string; is_bot?: boolean; first_name?: string };
  };
  edited_message?: {
    message_id?: number;
    text?: string;
    chat?: { id?: number | string; type?: string };
    from?: { id?: number | string; is_bot?: boolean; first_name?: string };
  };
};

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`${label} timeout after ${timeoutMs}ms`)),
      timeoutMs
    );
    promise
      .then((value) => {
        clearTimeout(timer);
        resolve(value);
      })
      .catch((error) => {
        clearTimeout(timer);
        reject(error);
      });
  });
}

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function buildFallbackAnswer(message: string): string {
  return [
    "No pude consultar Gemini ahora mismo.",
    "El bot sigue activo en modo degradado.",
    "",
    `Tu pregunta: "${message}"`,
    "",
    "Accion recomendada: revisar/rotar GOOGLE_AI_API_KEY.",
  ].join("\n");
}

function trimForTelegram(input: string): string {
  if (input.length <= MAX_TELEGRAM_TEXT_CHARS) return input;
  return `${input.slice(0, MAX_TELEGRAM_TEXT_CHARS - 3)}...`;
}

async function sendTelegramMessage(chatId: string, text: string): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) {
    throw new Error("Missing TELEGRAM_BOT_TOKEN");
  }

  const url = `${TELEGRAM_API}/bot${token}/sendMessage`;
  const payload = {
    chat_id: chatId,
    text: trimForTelegram(text),
    parse_mode: "HTML",
    disable_web_page_preview: true,
  };

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Telegram sendMessage failed (${response.status}): ${error}`);
  }
}

export async function POST(req: NextRequest) {
  try {
    const expectedSecret = process.env.TELEGRAM_WEBHOOK_SECRET;
    if (expectedSecret) {
      const providedSecret = req.headers.get("x-telegram-bot-api-secret-token");
      if (providedSecret !== expectedSecret) {
        return NextResponse.json({ ok: false, error: "Invalid webhook secret" }, { status: 401 });
      }
    }

    const update = (await req.json()) as TelegramUpdate;
    const msg = update.message ?? update.edited_message;

    const rawText = msg?.text?.trim();
    const chatId = msg?.chat?.id != null ? String(msg.chat.id) : null;

    if (!rawText || !chatId) {
      return NextResponse.json({ ok: true, ignored: "no_text_or_chat" });
    }

    const allowedChatId = process.env.TELEGRAM_CHAT_ID;
    if (allowedChatId && chatId !== allowedChatId) {
      await sendTelegramMessage(
        chatId,
        escapeHtml("Este bot no esta autorizado para este chat.")
      );
      return NextResponse.json({ ok: true, blocked: true });
    }

    if (rawText === "/start" || rawText === "/help") {
      const help = [
        "<b>Trading Agentic Bot</b>",
        "",
        "Escribime una pregunta y respondo con el mismo Gemini del sistema.",
        "Comandos:",
        "- /help",
        "- /ping",
      ].join("\n");
      await sendTelegramMessage(chatId, help);
      return NextResponse.json({ ok: true, command: "help" });
    }

    if (rawText === "/ping") {
      await sendTelegramMessage(chatId, "<b>pong</b>");
      return NextResponse.json({ ok: true, command: "ping" });
    }

    let answer = "";
    let fallback = false;
    let fallbackReason: string | null = null;

    try {
      const response = await withTimeout(chat({ message: rawText }), CHAT_TIMEOUT_MS, "chat_agent");
      answer = response.answer;
    } catch (error) {
      fallback = true;
      fallbackReason = error instanceof Error ? error.message : String(error);
      answer = buildFallbackAnswer(rawText);
    }

    await sendTelegramMessage(chatId, escapeHtml(answer));

    return NextResponse.json({
      ok: true,
      fallback,
      ...(fallbackReason ? { fallbackReason } : {}),
    });
  } catch (error) {
    console.error("Error in POST /api/telegram/webhook:", error);
    // Return 200 to prevent Telegram infinite retry storms on transient issues.
    return NextResponse.json({
      ok: true,
      fallback: true,
      error: error instanceof Error ? error.message : String(error),
    });
  }
}
