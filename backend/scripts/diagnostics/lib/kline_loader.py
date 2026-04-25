"""Helper to load and slice klines from the diagnostic parquet."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


class KlineLoader:
    def __init__(self, parquet_path: str | Path):
        self.path = Path(parquet_path)
        if not self.path.exists():
            raise FileNotFoundError(f"klines parquet not found at {self.path}")
        self._df = pd.read_parquet(self.path)
        # ensure UTC tz-aware
        if self._df["open_time"].dt.tz is None:
            self._df["open_time"] = self._df["open_time"].dt.tz_localize("UTC")
        if self._df["close_time"].dt.tz is None:
            self._df["close_time"] = self._df["close_time"].dt.tz_localize("UTC")
        self._df = self._df.sort_values(["symbol", "interval", "open_time"])

    @property
    def symbols(self) -> list[str]:
        return sorted(self._df["symbol"].unique().tolist())

    @property
    def intervals(self) -> list[str]:
        return sorted(self._df["interval"].unique().tolist())

    def slice(
        self,
        symbol: str,
        interval: str,
        start: datetime | pd.Timestamp | None = None,
        end: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Return klines for (symbol, interval) within [start, end] inclusive on open_time."""
        df = self._df[(self._df["symbol"] == symbol) & (self._df["interval"] == interval)]
        if start is not None:
            df = df[df["open_time"] >= pd.Timestamp(start, tz="UTC") if pd.Timestamp(start).tz is None else df["open_time"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["open_time"] <= pd.Timestamp(end, tz="UTC") if pd.Timestamp(end).tz is None else df["open_time"] <= pd.Timestamp(end)]
        return df.reset_index(drop=True)

    def kline_at(
        self,
        symbol: str,
        interval: str,
        ts: datetime | pd.Timestamp,
    ) -> pd.Series | None:
        """Return the single kline whose [open_time, close_time] contains ts.
        Returns None if no kline covers the timestamp."""
        ts_pd = pd.Timestamp(ts)
        if ts_pd.tz is None:
            ts_pd = ts_pd.tz_localize("UTC")
        df = self._df[(self._df["symbol"] == symbol) & (self._df["interval"] == interval)]
        df = df[(df["open_time"] <= ts_pd) & (df["close_time"] >= ts_pd)]
        if df.empty:
            return None
        return df.iloc[0]

    def coverage(self) -> dict[tuple[str, str], tuple[pd.Timestamp, pd.Timestamp, int]]:
        out: dict = {}
        for (sym, iv), g in self._df.groupby(["symbol", "interval"]):
            out[(sym, iv)] = (g["open_time"].min(), g["open_time"].max(), len(g))
        return out
