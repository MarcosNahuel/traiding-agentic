from asesor_iol.config import Settings


def make_settings(tmp_path, **over):
    base = dict(
        iol_username="u",
        iol_password="p",
        iol_api_base="https://api.test",
        anthropic_api_key="k",
        telegram_bot_token="t",
        telegram_allowed_chat_id=1,
        max_order_amount=2000.0,
        max_daily_amount=5000.0,
        allowed_symbols="SPY,AAPL",
        order_confirmation_timeout_min=0,
        state_db_path=str(tmp_path / "test.db"),
        market_context_path=str(tmp_path / "ctx.md"),
    )
    base.update(over)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]
