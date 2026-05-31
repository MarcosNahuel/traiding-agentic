"""Bot de Telegram: front-end del asesor. Long-polling, allowlist de un solo chat.

- Mensajes de texto -> Advisor.ask -> respuesta.
- Órdenes pendientes -> mensaje con botones Confirmar/Cancelar -> resuelve el broker.
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..config import Settings
from ..security.gate import ApprovalBroker

log = logging.getLogger("asesor.telegram")


class TelegramAdvisorBot:
    def __init__(self, settings: Settings, broker: ApprovalBroker) -> None:
        self._s = settings
        self._broker = broker
        self.advisor = None  # se setea después de construir (wiring en main)
        self._app: Application = (
            Application.builder().token(settings.telegram_bot_token).build()
        )
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message)
        )
        self._app.add_handler(CallbackQueryHandler(self._on_button))

    def _authorized(self, chat_id: int | None) -> bool:
        return chat_id == self._s.telegram_allowed_chat_id

    async def _on_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        if not self._authorized(chat.id if chat else None):
            log.warning("Mensaje de chat no autorizado: %s", chat.id if chat else "?")
            return
        if self.advisor is None or not update.message or not update.message.text:
            return
        await ctx.bot.send_chat_action(chat_id=chat.id, action="typing")
        try:
            reply = await self.advisor.ask(update.message.text)
        except Exception as e:  # nunca dejar al usuario sin respuesta
            log.exception("Error procesando mensaje")
            reply = f"⚠️ Hubo un error procesando tu mensaje: {e}"
        await update.message.reply_text(reply)

    async def _on_button(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        if q is None:
            return
        chat = update.effective_chat
        if not self._authorized(chat.id if chat else None):
            await q.answer("No autorizado.")
            return
        await q.answer()
        action, _, order_id = (q.data or "").partition(":")
        approved = action == "ok"
        resolved = self._broker.resolve(order_id, approved)
        if not resolved:
            await q.edit_message_text("⏱️ Esa orden ya expiró o no existe.")
            return
        await q.edit_message_text(
            "✅ Confirmada. Ejecutando…" if approved else "❌ Cancelada. No se ejecutó."
        )

    async def send_confirmation(self, order_id: str, summary: str) -> None:
        """Inyectado en el gate: muestra la orden pendiente con botones."""
        kb = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Confirmar", callback_data=f"ok:{order_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"no:{order_id}"),
            ]]
        )
        await self._app.bot.send_message(
            chat_id=self._s.telegram_allowed_chat_id, text=summary, reply_markup=kb
        )

    def run(self) -> None:
        log.info("Asesor IOL — bot de Telegram iniciado (long-polling).")
        self._app.run_polling()
