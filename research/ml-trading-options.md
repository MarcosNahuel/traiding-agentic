# Financial ML Trading Bot Strategy & Data Options Report

Generated: 2026-03-18  
Project: `traiding-agentic`  
Environment: Windows 10, Python 3.12, `pip`, FastAPI backend, Binance Spot Testnet  
Scope: Move the current rule-based 1h crypto bot toward a practical, ML-driven research and production pipeline for BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, and XRPUSDT.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Repo Snapshot and Constraints](#2-current-repo-snapshot-and-constraints)
3. [Historical Data Sources for Crypto](#3-historical-data-sources-for-crypto)
4. [ML Libraries and Frameworks for Time Series Financial Prediction](#4-ml-libraries-and-frameworks-for-time-series-financial-prediction)
5. [Feature Engineering: Complete Feature Set](#5-feature-engineering-complete-feature-set)
6. [Model Architecture Options](#6-model-architecture-options)
7. [Backtesting Frameworks](#7-backtesting-frameworks)
8. [Risk Management Improvements](#8-risk-management-improvements)
9. [Production Architecture for the Existing FastAPI Backend](#9-production-architecture-for-the-existing-fastapi-backend)
10. [Open Source Trading Bots with ML](#10-open-source-trading-bots-with-ml)
11. [Recommended Implementation Roadmap](#11-recommended-implementation-roadmap)
12. [Appendix A: Install Commands and Versions](#12-appendix-a-install-commands-and-versions)
13. [Appendix B: Code Snippets](#13-appendix-b-code-snippets)
14. [Appendix C: Source Links and References](#14-appendix-c-source-links-and-references)
15. [Appendix D: Data Quality and Leakage Checklists](#15-appendix-d-data-quality-and-leakage-checklists)
16. [Appendix E: Experiment Backlog and Search Grids](#16-appendix-e-experiment-backlog-and-search-grids)
17. [Appendix F: Production Runbooks and Alerts](#17-appendix-f-production-runbooks-and-alerts)
18. [Appendix G: Asset-Specific Notes for the Five-Symbol Universe](#18-appendix-g-asset-specific-notes-for-the-five-symbol-universe)
19. [Appendix H: Detailed Module Contracts and Storage Design](#19-appendix-h-detailed-module-contracts-and-storage-design)
20. [Appendix I: Metrics, Diagnostics, and Reporting Templates](#20-appendix-i-metrics-diagnostics-and-reporting-templates)

---

## 1. Executive Summary

### 1.1 Bottom Line

For your specific use case, the best free data stack is:

1. Bulk backfill from `data.binance.vision`
2. Incremental updates from Binance Spot REST `GET /api/v3/klines`
3. Optional `ccxt` only as a fallback abstraction layer, not as the primary source of truth

That combination is better than paid vendors for the first implementation because:

- It is venue-aligned with your execution venue
- It includes exactly the fields you already collect and can use for ML
- One year of 1h candles for five symbols is tiny by market-data standards
- It avoids paying for normalized enterprise feeds before you have a proven signal pipeline

### 1.2 Core Recommendation Stack

The recommended stack for the first production-quality ML iteration is:

| Layer | Recommendation | Why |
|---|---|---|
| Data | Binance archive + Binance REST | Free, exact venue match, enough depth, includes volume and trades count |
| Storage | Reuse current DB plus new feature/label/model tables | Minimal architecture disruption |
| Feature engineering | Start with 30 high-signal tabular features, expand to 60-80 | Matches the empirical lesson from Kelly & Xiu and practical tree models |
| First model | LightGBM regression on next-bar log return | Strong tabular baseline, fast, good with mixed feature scales |
| Baselines | Ridge, ElasticNet, RandomForest, XGBoost | Needed for sanity checks and model ranking |
| NN follow-up | PyTorch FFN first, LSTM second | Lower friction than TensorFlow on Windows 10 + Python 3.12 |
| Ensemble | Validation-weighted average of LightGBM + XGBoost + FFN | Simple and robust |
| Backtesting | Extend current `backend/app/services/backtester.py` and keep the vectorbt path | You already have the beginnings of the right tool |
| HPO | Optuna | Easy integration, pruning, reproducible studies |
| Explainability | SHAP | Best practical feature-importance workflow for tree models |
| Live rollout | Shadow mode first, then small notional | Avoids premature live risk |

### 1.3 What Needs to Change Immediately

The current rule system is not just conservative. It is structurally mis-specified for return asymmetry:

- The bot trades too rarely
- The win rate is not the real problem
- Losses being 3.7x larger than wins means the system can look “accurate” and still destroy expectancy
- Moving to ML without fixing execution policy and risk sizing will only produce a more complicated failure mode

Immediate priorities:

1. Build a proper historical dataset
2. Add a repeatable walk-forward research pipeline
3. Separate prediction from signal policy
4. Fix risk and exit logic before live ML execution
5. Run the first ML model in shadow mode before allowing capital allocation

### 1.4 Recommended First Milestone

The first credible milestone is not “use neural networks.”  
The first credible milestone is:

> A LightGBM model trained on 60-80 engineered features, validated with expanding walk-forward windows, traded through a thresholded signal policy, and backtested after fees and slippage across all five symbols.

If that does not outperform the current strategy, adding LSTM or RL is premature.

---

## 2. Current Repo Snapshot and Constraints

### 2.1 What the Existing Backend Already Does Well

From the current backend code:

- [`backend/app/services/kline_collector.py`](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/kline_collector.py) already stores:
  - open, high, low, close, volume
  - quote volume
  - trades count
  - taker-buy base volume
  - taker-buy quote volume
- [`backend/app/services/backtester.py`](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/backtester.py) already includes a `vectorbt` path with fee and slippage support
- [`backend/app/services/signal_generator.py`](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/signal_generator.py) is modular enough to replace rule outputs with model predictions
- [`backend/app/services/risk_manager.py`](D:/OneDrive/GitHub/traiding-agentic/backend/app/services/risk_manager.py) can remain as a hard-constraint layer above ML signals

This matters because you do not need a greenfield rewrite.  
You need a research and inference layer that plugs into the current service boundaries.

### 2.2 Current Weak Points

The current architecture still has material gaps for ML:

| Area | Current state | Problem for ML | Required change |
|---|---|---|---|
| Historical coverage | `backfill()` defaults to 30 days | Not enough data | Backfill at least 365 days, preferably full listing history |
| Signal timing | Orchestrator runs every 60 seconds while trading 1h bars | Can repeatedly react to the same incomplete candle | Trigger feature generation and inference on candle close |
| Labels | No dedicated label store | Hard to reproduce experiments | Store training labels explicitly |
| Feature store | No feature store | Feature leakage risk and inconsistent live/offline parity | Persist computed features by timestamp/symbol |
| Model registry | None | No auditability | Save model metadata, features, metrics, training window |
| Walk-forward engine | Partial backtesting support | No robust ML validation | Add rolling/expanding walk-forward orchestration |
| Risk policy | Simple rule checks | Does not solve R:R asymmetry | Add stop, sizing, drawdown, regime logic |

### 2.3 Crypto-Specific Constraints That Must Shape the Design

Crypto is not equities. The system has to account for:

- 24/7 trading
- Regime changes that arrive faster than typical large-cap equities
- More abrupt volatility clustering
- Exchange-specific market structure
- Frequent microstructure distortions during liquidations and breakout hours
- Symbol-specific listing history differences
- Spot-only limitations if you stay on Binance Spot Testnet

These differences mean:

- Calendar features matter differently than in equities
- Regime filtering matters more
- Microstructure proxies matter even on hourly bars
- Derivatives data can add material predictive power later
- Slippage assumptions on testnet are almost certainly too optimistic for production

### 2.4 Working Assumption for This Report

The recommendations below assume:

- Primary horizon: 1h bars
- Assets: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT
- Venue: Binance Spot Testnet for execution, Binance Spot production data for research
- Objective: increase trade count materially while improving expectancy, Sharpe, and profit factor
- Budget: prefer free and open source, but document paid choices

---

## 3. Historical Data Sources for Crypto

### 3.1 Decision Summary

For your minimum requirement of one year of 1h candles for five symbols:

| Requirement | Amount |
|---|---|
| Symbols | 5 |
| Hours per year | 8,760 |
| Approximate rows | 43,800 |
| Core fields needed | OHLCV, quote volume, trades count, taker buy fields |

This is a very small dataset.  
You do not need Kaiko or CoinAPI to get started.  
You need reliable, venue-aligned history with clean timestamps.

### 3.2 Best Free Option

The best free option is:

1. `data.binance.vision` for bulk historical files
2. Binance REST `GET /api/v3/klines` for incremental updates

Why this is the best free option:

- Same exchange as the intended live execution path
- Free
- High availability
- Includes exchange-native candle definitions
- Binance Kline payloads also expose quote volume, number of trades, taker buy base, and taker buy quote values
- Easy to automate
- One year of 1h data for five assets is operationally trivial

### 3.3 Comparison Table: Crypto Historical Data Options

| Source | Access model | Max lookback | Granularity | Fields | Rate limits / constraints | Data quality | Cost | Fit for this project |
|---|---|---|---|---|---|---|---|---|
| Binance REST `/api/v3/klines` | API | Listing date onward, queried in pages | `1m` to `1M`, includes `1h` | OHLCV + quote volume + trades count + taker buy fields | Max 1000 candles per request, request weight 2 | Very high for Binance-traded pairs | Free | Excellent for incremental sync |
| `data.binance.vision` | Downloadable archives | Deep archive from listing date onward for many symbols | Daily/monthly zipped files; spot klines commonly minute/hour/day compatible datasets | Venue-native OHLCV and related fields depending file type | Bulk download, no normal REST pagination pain | Very high for Binance | Free | Best bulk backfill |
| CryptoDataDownload | Downloadable CSVs | Varies by exchange and pair, often multi-year | 1m, 1h, 1d depending dataset | Usually OHLCV; some datasets omit exchange-native microstructure extras | Site download limits, no official low-level API quota model | Good, but derived and mirror-based | Free core, paid premium tiers | Good convenience fallback |
| `ccxt` | Unified Python library | Depends on exchange API history | Depends on exchange, usually `1m` to `1d`+ | Whatever exchange returns via unified OHLCV schema | Constrained by each exchange’s API, pagination required | Good abstraction, not a data vendor | Open source library | Good integration layer, not best source of record |
| CoinGecko | API | Historical price series but not exchange-native deep microstructure | Auto granularity rules, hourly only for limited horizon on some endpoints | Prices, market cap, volume estimates | Demo key around 30 calls/minute; auto granularity limits | Good macro/market data, not venue-specific | Free/demo + paid | Weak primary source for exchange execution research |
| CryptoCompare / CoinDesk Data | API | Multi-year | Minute, hour, day | OHLCV aggregates, market summaries | Varies by key and endpoint; some old free endpoints still exist | Good aggregate data | Free/basic + enterprise | Secondary source |
| Kaggle datasets | Files | Depends on uploader | Depends on dataset | Often OHLCV only | No streaming or official exchange SLA | Variable | Free | Good for sandbox experiments only |
| Kaiko | Enterprise API / files | Since 2014 for many markets | Tick to aggregated bars | OHLCV, trades, order books, reference data, liquidity metrics | Commercial SLA | Excellent institutional quality | Paid, contact sales | Overkill for phase 1 |
| CoinAPI | Commercial API | Historical depth advertised back to 2010 | 1 second to 1 month | OHLCV, trades, quotes, order books by plan | Metered API calls, plan quotas | High | Paid, business pricing published | Useful if you later need multi-exchange normalization |
| CCData / CoinDesk enterprise feeds | Commercial API | Multi-year | Minute/hour/day and more | Aggregates, index, market data | Paid | High | Paid | Useful later if adding cross-venue analytics |
| Exchange-native alternatives via `ccxt` | API | Varies by exchange listing and endpoint | Usually `1m` to `1d` | Usually OHLCV only in unified schema | Rate-limit and pagination pain | Exchange-dependent | Free | Useful for cross-venue features |

### 3.4 Binance: Detailed Assessment

#### 3.4.1 What Binance Gives You

Official Binance spot market-data docs show:

- `GET /api/v3/klines`
- Request weight: `2`
- Maximum candles per request: `1000`
- Response includes:
  - open time
  - open
  - high
  - low
  - close
  - volume
  - close time
  - quote asset volume
  - number of trades
  - taker buy base asset volume
  - taker buy quote asset volume

This matters because your current collector already captures several fields beyond plain OHLCV.  
Those are useful for volume imbalance and microstructure proxy features.

#### 3.4.2 Practical Limits

One year of 1h candles per symbol is 8,760 rows.

At 1000 rows per request:

- ~9 requests per symbol
- ~45 requests for five symbols
- Request weight ~90 total

That is trivial.

Even a full multi-year backfill is easy if you combine archive files with REST.

#### 3.4.3 Recommended Usage Pattern

Use Binance in two modes:

| Mode | Source | Purpose |
|---|---|---|
| Historical bootstrap | `data.binance.vision` | Bulk backfill without pagination overhead |
| Daily/hourly increment | REST `GET /api/v3/klines` | Update recent candles and catch latest closed bars |
| Gap repair | REST `GET /api/v3/klines` | Re-fetch missing windows |
| Validation | Compare latest stored close time to expected schedule | Ensure no silent data holes |

#### 3.4.4 Data Quality Notes

Advantages:

- Venue-native
- Deterministic candle boundaries
- Extra fields beyond OHLCV
- Best alignment with actual future execution

Limitations:

- No full depth order book history in the simple kline feed
- Spot data does not include funding rates or futures open interest
- Historical availability begins at listing date, not a universal synthetic history

### 3.5 `data.binance.vision`: Why It Should Be the Primary Backfill Path

Binance publishes public archives at `https://data.binance.vision/`.

Practical advantages:

- Faster than paginating all history through REST
- Easier reproducibility
- Can be re-downloaded and checksummed
- Good for repeatable training datasets

Recommended policy:

1. Download monthly or daily kline archives for each symbol and timeframe
2. Parse and insert into your `klines` table
3. Run an integrity check on timestamp continuity
4. Use REST only to update recent periods after the latest archived file

### 3.6 CryptoDataDownload.com

#### 3.6.1 What It Is Good At

CryptoDataDownload is useful when you want:

- Quick CSV access
- Exchange-specific historical data
- No authentication for basic download
- A convenience fallback if you do not want to build archive ingestion immediately

It is especially useful for:

- Prototyping notebooks
- Cross-checking timestamps
- Quick offline exploration

#### 3.6.2 Limitations

- It is not your execution venue’s canonical archive
- Exchange-native extra fields may be missing
- Update cadence and normalization choices are controlled by the provider
- Some datasets are free but premium “cleaner” tiers exist

#### 3.6.3 Verdict

Use it only as:

- a convenience mirror
- a backup source
- a quick notebook source

Do not use it as the primary source of truth if you execute on Binance spot.

### 3.7 Kaiko

#### 3.7.1 Where Kaiko Fits

Kaiko is an institutional-grade market-data provider with:

- long multi-exchange history
- normalized market data
- trades, order books, and liquidity analytics
- reference data
- stronger vendor guarantees than free exchange feeds

#### 3.7.2 Why It Is Not the First Buy Here

For five symbols on hourly bars:

- the problem is not data breadth
- the problem is model quality and research discipline

Kaiko would make sense later if you want:

- cross-exchange microstructure features
- trade-level or order-book-level research
- external liquidity and reference datasets
- enterprise support or SLA

#### 3.7.3 Cost

Public raw market-data pricing is generally not listed in a simple self-serve retail schedule.  
Expect enterprise/custom quote pricing.

#### 3.7.4 Verdict

Excellent vendor.  
Wrong cost/complexity point for phase 1.

### 3.8 CoinAPI

#### 3.8.1 Strengths

CoinAPI is one of the strongest paid self-serve options for:

- normalized multi-exchange history
- API-first workflows
- deep historical coverage
- timeframes from seconds to months

#### 3.8.2 Pricing Position

Public pricing indicates:

- a metered/free-credit entry path
- business plans around the hundreds of dollars per month range

This is reasonable for commercial multi-exchange work, but still unnecessary for the first stage of your bot.

#### 3.8.3 Verdict

Best use case later:

- if you want unified multi-exchange data in one schema
- if you want to compare Binance vs Coinbase vs Kraken behavior
- if you want exchange diversification without maintaining many adapters

### 3.9 CryptoCompare / CoinDesk Data / CCData

#### 3.9.1 Strengths

This ecosystem is useful for:

- aggregate market views
- broad historical access
- index/reference-style data
- quick experiments when you do not require exchange-native microstructure fidelity

#### 3.9.2 Limitations for Your Use Case

- Not the cleanest fit if execution remains on Binance spot
- Free/min API access exists, but quotas and product boundaries are less straightforward than using Binance directly
- Exchange-native fields like trades count and taker-buy data are not always mirrored the same way

#### 3.9.3 Verdict

Good secondary vendor.  
Not the best primary research feed for this bot.

### 3.10 `ccxt`

#### 3.10.1 What `ccxt` Solves

`ccxt` is not a market-data vendor.  
It is a unified exchange interface.

Use it when you want:

- one Python API for many exchanges
- fast experimentation across venues
- portability
- less bespoke API code

#### 3.10.2 What `ccxt` Does Not Solve

`ccxt` does not create deeper history than the exchange offers.

Key implication:

- If Binance only gives certain history or pagination behavior, `ccxt` inherits that limitation
- If Kraken has older BTC history than Binance for some pairs, `ccxt` can access it, but you still need venue-specific reasoning

#### 3.10.3 Deepest History by Exchange

As a practical rule:

- For large legacy assets like BTC and ETH, older spot history may be easier to find on long-running venues such as Kraken, Bitfinex, and Coinbase
- For Binance-native alt liquidity and exact venue alignment on SOL, BNB, XRP, and many alt pairs, Binance is still the most relevant source

For this project, “deepest history” is less important than “matching the venue you trade on.”

#### 3.10.4 Verdict

Use `ccxt` as:

- a fallback collector
- a future multi-exchange feature source
- a cross-check layer

Do not replace direct Binance collection with `ccxt` for the core dataset unless you need exchange portability immediately.

### 3.11 Kaggle Datasets

#### 3.11.1 Where Kaggle Helps

Kaggle is useful for:

- offline experimentation
- quickly comparing model families
- learning from notebooks and competition workflows
- observing what high-ranking solutions do with tabular time-series features

The most relevant competition signal for your project is still the broader pattern:

- gradient boosted trees remain extremely strong on engineered tabular features
- ensembling matters
- feature engineering matters more than model novelty in many settings

#### 3.11.2 Why Kaggle Is Not Your Core Data Source

- data provenance varies
- exchange alignment varies
- preprocessing may already encode assumptions you do not want
- licensing and reproducibility are inconsistent

#### 3.11.3 Verdict

Use Kaggle for:

- ideas
- feature engineering inspiration
- benchmarking model families

Do not use it as the production historical source for this bot.

### 3.12 CoinGecko and Other Cheap/Free Sources

Other sources worth knowing:

| Source | Best use | Weakness for your setup |
|---|---|---|
| CoinGecko | Market-wide price, volume, market-cap context | Not exchange-native, limited hourly horizons on some endpoints |
| Alpha Vantage crypto endpoints | Very light exploratory work | Thin compared with exchange-native crypto tooling |
| Twelve Data | Generic multi-asset access | Better for broad prototyping than exchange-native research |
| Stooq / Yahoo-style mirrors | General experimentation | Weak crypto venue fidelity |
| Public exchange CSV mirrors on GitHub | Toy experiments | Quality control and continuity risk |

### 3.13 Historical Data Recommendation Matrix

| Need | Best source | Backup | Paid upgrade path |
|---|---|---|---|
| 1 year of 1h bars for Binance spot pairs | Binance archive + REST | CryptoDataDownload | CoinAPI |
| Exact trades count / taker-buy fields | Binance | None of the generic mirrors reliably match | Kaiko |
| Multi-exchange normalized candles | CoinAPI | `ccxt` + your own normalization | Kaiko |
| Order book research | Not in basic Binance klines | Native market-depth capture | Kaiko |
| Funding/open interest | Binance futures endpoints or derivatives vendors | Coinglass-style secondary sources | Kaiko / CoinAPI + derivatives vendors |

### 3.14 Practical Data Collection Design

Recommended pipeline:

1. Bootstrap all five symbols from archive
2. Fetch the latest closed 1h candle via REST on schedule
3. Reconcile missing intervals each day
4. Store raw klines unchanged
5. Build features from raw klines, not from already transformed tables

### 3.15 Recommended Data Retention Windows

| Use case | Minimum | Better | Best practical phase-1 target |
|---|---|---|---|
| Simple baseline ML | 1 year | 2 years | 2-4 years if listed history exists |
| Walk-forward with multiple folds | 1 year | 2 years | 3 years |
| LSTM / transformer experiments | 2 years | 3 years | 4+ years where available |
| Regime detection | 1 year | 2 years | 3+ years |

### 3.16 Data Source Conclusion

For your exact requirement, the answer is straightforward:

- Best free source: Binance archive + Binance REST
- Best free convenience fallback: CryptoDataDownload
- Best exchange abstraction: `ccxt`
- Best paid upgrade if you later need normalized multi-exchange APIs: CoinAPI
- Best enterprise-quality institutional upgrade: Kaiko

---

## 4. ML Libraries and Frameworks for Time Series Financial Prediction

### 4.1 Decision Summary

For this project, the most pragmatic library stack is:

1. `scikit-learn` for baselines and preprocessing
2. `lightgbm` as the first serious model
3. `xgboost` as the second tree benchmark
4. `pytorch` for FFN and later LSTM
5. `optuna` for HPO
6. `shap` for interpretation
7. `vectorbt` plus your existing backtester for walk-forward portfolio testing

### 4.2 Comparison Table: Core Modeling Libraries

| Library | Python 3.12 status | Best use here | Strengths | Weaknesses | Learning curve | Pandas integration | Recommendation |
|---|---|---|---|---|---|---|---|
| `scikit-learn` | Strong | Baselines, preprocessing, CV utilities | Stable, familiar, broad API | Tree boosting weaker than dedicated libraries | Low | Excellent | Mandatory baseline layer |
| `lightgbm` | Good | Main tabular alpha model | Fast, strong on large feature sets, handles nonlinear interactions well | Can overfit noisy data without discipline | Medium | Very good | First model to build |
| `xgboost` | Good | Second tree benchmark | Robust, mature, often very strong on tabular data | Heavier package, slower than LightGBM in some settings | Medium | Very good | Build after LightGBM |
| `catboost` | Good | Third tree benchmark | Strong defaults, robust categorical support | Less decisive advantage when features are mostly numeric | Medium | Good | Optional benchmark |
| `pytorch` | Strong | FFN and LSTM | Flexible, strong ecosystem, better practical Windows path than TF | More engineering than tree models | Medium-high | Good via `Dataset`/NumPy | Best NN stack |
| `tensorflow` | Mixed practicality on Windows | Alternative NN stack | Keras API is approachable | Windows GPU support path is less friendly than PyTorch | Medium | Good | Secondary choice |
| `statsmodels` | Strong | Classical baselines | Strong for linear/econometric benchmarks | Not a production alpha engine | Medium | Excellent | Use for diagnostics and baseline linear structure |

### 4.3 Package Footprint and Installation Friction

Approximate wheel sizes observed for current versions:

| Package | Version observed | Approx wheel size | Practical note |
|---|---|---:|---|
| `lightgbm` | `4.6.0` | 3.4 MB | Very light for the capability |
| `xgboost` | `3.2.0` | 125.6 MB | Heavier install but manageable |
| `catboost` | `1.2.10` | 95.6 MB | Heavy but still reasonable |
| `torch` | `2.10.0` | 108.5 MB | Fine for CPU, larger with CUDA ecosystem |
| `tensorflow` | `2.21.0` | 334.7 MB | Largest install, biggest friction |
| `statsmodels` | `0.14.6` | 9.1 MB | Easy |
| `optuna` | `4.8.0` | 0.4 MB | Very easy |
| `shap` | `0.51.0` | 0.5 MB | Easy package, some runtime heaviness |
| `vectorbt` | `0.28.4` | 0.4 MB | Small install, heavy power |
| `backtesting` | `0.6.5` | 0.2 MB | Very light |
| `backtrader` | `1.9.78.123` | 0.4 MB | Light but older ecosystem |
| `zipline-reloaded` | `3.1.1` | 4.7 MB | Moderate install complexity due to dependencies |
| `stable-baselines3` | `2.7.1` | 0.2 MB | Easy package, harder project |
| `ray` | `2.54.0` | 26.2 MB | Heavy orchestration stack |

### 4.4 `scikit-learn`

#### 4.4.1 Why It Still Matters

Even if you use LightGBM and PyTorch, `scikit-learn` stays central because it gives you:

- baseline models
- preprocessing
- pipelines
- metrics
- `TimeSeriesSplit`
- feature selection helpers
- calibration utilities

#### 4.4.2 Models You Should Actually Use

Recommended `scikit-learn` models for your benchmark layer:

| Model | Why use it | What it tells you |
|---|---|---|
| Ridge | Regularized linear baseline | Whether most signal is linear and weak |
| Lasso | Sparse linear baseline | Which features survive aggressive shrinkage |
| ElasticNet | Balanced linear baseline | Useful when feature groups are correlated |
| RandomForestRegressor | Nonlinear ensemble baseline | Whether simple bagging already captures signal |
| GradientBoostingRegressor | Historical tree baseline | Useful but usually superseded by LightGBM/XGBoost |
| HistGradientBoostingRegressor | Fast built-in boosting | Good extra benchmark |

#### 4.4.3 Verdict

Mandatory.  
Not enough on its own for the best alpha model, but essential for research hygiene.

### 4.5 LightGBM vs XGBoost vs CatBoost

#### 4.5.1 Practical Winner for Phase 1

`LightGBM` is the best first tree-based model for your project.

Why:

- extremely strong on tabular financial features
- handles many correlated numeric features well
- fast to train and tune
- good for repeated walk-forward retraining
- integrates cleanly with Optuna and SHAP

#### 4.5.2 Detailed Comparison

| Criterion | LightGBM | XGBoost | CatBoost |
|---|---|---|---|
| Fit for numeric tabular financial data | Excellent | Excellent | Very good |
| Speed on repeated retraining | Excellent | Very good | Good |
| Memory efficiency | Very good | Good | Good |
| Default robustness | Good | Good | Very good |
| Categorical feature handling | Moderate | Moderate | Excellent |
| Ecosystem maturity | Excellent | Excellent | Strong |
| Typical advantage in finance competitions | Very strong | Very strong | Sometimes strong, less dominant in numeric-only settings |
| Best role here | First production baseline | Benchmark and ensemble member | Optional benchmark |

#### 4.5.3 Why LightGBM First

For your feature set:

- almost all inputs are numeric
- there are many derived ratios and rolling statistics
- retraining needs to be inexpensive
- you care about fast iteration more than theoretical elegance

That is a LightGBM-shaped problem.

#### 4.5.4 Why XGBoost Second

You should still run XGBoost because:

- it often behaves slightly differently on noisy tabular data
- its regularization knobs are strong
- ensembles benefit from partially independent errors

#### 4.5.5 When CatBoost Becomes More Interesting

CatBoost becomes more attractive if you later add:

- explicit categorical regime labels
- exchange identifiers
- instrument metadata
- cross-venue categorical fields

For the first phase, it is optional.

### 4.6 PyTorch

#### 4.6.1 Why PyTorch Over TensorFlow for This Project

For Windows 10 + Python 3.12, PyTorch is the safer default:

- native installation is straightforward
- CPU workflow is smooth
- future GPU migration is more practical
- research ecosystem is stronger for custom finance models

#### 4.6.2 Best Use Cases

Use PyTorch for:

- feed-forward tabular nets
- sequence models such as LSTM
- later lightweight attention models
- custom losses and ensemble architectures

#### 4.6.3 Where It Should Sit in the Roadmap

PyTorch should come after:

1. data integrity
2. feature store
3. tabular boosting baseline

If LightGBM is not profitable after disciplined walk-forward testing, a neural net is not the automatic fix.

### 4.7 TensorFlow / Keras

#### 4.7.1 Strengths

- Keras API is approachable
- strong documentation
- broad examples
- good for rapid simple prototypes

#### 4.7.2 Weaknesses Here

- Windows support is more awkward than PyTorch for modern workflows
- GPU setup on native Windows is less attractive than WSL2 paths
- lower practical payoff than just standardizing on PyTorch

#### 4.7.3 Verdict

Viable, but not the best primary NN stack for your environment.

### 4.8 `statsmodels`

#### 4.8.1 Why You Still Want It

`statsmodels` is useful for:

- linear diagnostics
- AR terms
- stationarity tests
- volatility baselines
- simple econometric sanity checks

#### 4.8.2 Good Uses

| Use case | Example |
|---|---|
| Baseline regression | OLS or rolling OLS on a smaller feature set |
| Serial correlation diagnostics | Ljung-Box style checks |
| Regime proxy research | Markov switching if you later want a regime model |
| Volatility modeling | GARCH via `arch` package is often more convenient, but statsmodels remains useful |

#### 4.8.3 Verdict

Useful as a diagnostics library, not the main alpha engine.

### 4.9 Backtesting and Research Libraries

| Library | Best use | Verdict |
|---|---|---|
| `vectorbt` | fast vectorized backtests, parameter sweeps, multi-asset research | Best fit |
| `backtesting.py` | simple strategy prototypes | Good secondary tool |
| `backtrader` | event-driven simulation with broad features | Too much weight for this phase |
| `zipline-reloaded` | legacy quant workflows | Not ideal for 24/7 crypto |

Full framework comparison is covered in Section 7.

### 4.10 Optuna

#### 4.10.1 Why You Want It

Optuna is the correct HPO tool here because it gives you:

- easy search-space definitions
- pruning
- persistent studies
- solid integration with LightGBM, XGBoost, and PyTorch

#### 4.10.2 Good Use Cases

Use Optuna for:

- LightGBM hyperparameter search
- threshold optimization for signal conversion
- FFN architecture search
- retraining cadence experiments

#### 4.10.3 What Not to Do

Do not let Optuna tune against one static split and declare victory.  
It must tune against walk-forward validation metrics.

### 4.11 SHAP

#### 4.11.1 Why It Matters

SHAP is the practical choice for:

- global feature importance
- per-prediction explanation
- feature pruning
- sanity checks against nonsense features

#### 4.11.2 What It Does Not Replace

SHAP does not replace:

- walk-forward validation
- leakage checks
- economic reasoning

If a feature ranks high in SHAP because it leaks the future, SHAP will happily celebrate the mistake.

### 4.12 Community Support and Learning Curve

| Tool | Community | Docs quality | Learning curve | Practical recommendation |
|---|---|---|---|---|
| `scikit-learn` | Huge | Excellent | Low | Use everywhere |
| `lightgbm` | Large | Good | Medium | First main model |
| `xgboost` | Huge | Excellent | Medium | Second benchmark |
| `catboost` | Strong | Good | Medium | Optional third benchmark |
| `pytorch` | Huge | Good | Medium-high | Primary NN stack |
| `tensorflow` | Huge | Good | Medium | Secondary NN option |
| `statsmodels` | Mature | Good | Medium | Diagnostic support |
| `optuna` | Strong | Good | Low-medium | Default HPO |
| `shap` | Strong | Good | Medium | Default explainability |
| `vectorbt` | Strong niche | Good | Medium | Best research backtester |

### 4.13 Library Recommendation Conclusion

Use this stack first:

- `scikit-learn`
- `lightgbm`
- `xgboost`
- `pytorch`
- `optuna`
- `shap`
- `vectorbt`

Delay:

- `catboost`
- `tensorflow`
- RL stacks

---

## 5. Feature Engineering: Complete Feature Set

### 5.1 Design Principle

The best lesson from both academic and practitioner evidence is not “one magic indicator wins.”  
It is:

- broad feature coverage
- disciplined leakage control
- careful validation
- pruning by out-of-sample usefulness

Kelly & Xiu explicitly point toward richer feature spaces and regularized nonlinear models.  
Kaggle-style crypto forecasting workflows also repeatedly converge on:

- many engineered features
- tree models
- ensembles

### 5.2 Feature Engineering Rules for This Bot

Follow these rules:

1. Every feature must be computable from information available at bar close `t`
2. Targets must start strictly after feature timestamp `t`
3. Use rolling windows with `min_periods`
4. Prefer stationary transforms over raw price levels
5. Standardize or winsorize only where justified
6. Track feature definitions in code, not just notebooks
7. Persist the exact feature list per model version

### 5.3 Target Design

Recommended primary target:

```text
y_reg[t] = log(close[t+1] / close[t])
```

Recommended secondary classification target:

```text
y_cls[t] = 1 if forward_return_after_costs[t] > threshold else 0
```

Optional phase-2 target:

- triple-barrier or meta-labeling

### 5.4 Feature Catalog Columns

The master table below uses:

- `Feature`: canonical internal name
- `Formula / description`: short implementation definition
- `pandas-ta-classic`: direct function if available, else `custom`
- `Expected predictive power`: subjective but practical estimate
- `Cost`: relative CPU cost for 1h-bar pipelines

### 5.5 Master Feature Catalog

#### 5.5.1 Price-Based Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 1 | `ret_1h` | `close.pct_change(1)` | `custom` | Medium | Fast |
| 2 | `ret_2h` | `close.pct_change(2)` | `custom` | Medium | Fast |
| 3 | `ret_3h` | `close.pct_change(3)` | `custom` | Medium | Fast |
| 4 | `ret_6h` | `close.pct_change(6)` | `custom` | Medium-high | Fast |
| 5 | `ret_12h` | `close.pct_change(12)` | `custom` | Medium-high | Fast |
| 6 | `ret_24h` | `close.pct_change(24)` | `custom` | Medium-high | Fast |
| 7 | `ret_48h` | `close.pct_change(48)` | `custom` | Medium | Fast |
| 8 | `logret_1h` | `log(close / close.shift(1))` | `custom` | Medium-high | Fast |
| 9 | `logret_6h` | `log(close / close.shift(6))` | `custom` | Medium-high | Fast |
| 10 | `logret_24h` | `log(close / close.shift(24))` | `custom` | Medium-high | Fast |
| 11 | `close_open_ratio` | `close / open - 1` | `custom` | Medium | Fast |
| 12 | `high_low_range_pct` | `(high - low) / close` | `custom` | Medium | Fast |
| 13 | `body_to_range` | `abs(close-open) / (high-low)` | `custom` | Low-medium | Fast |
| 14 | `upper_wick_ratio` | `(high - max(open,close)) / (high-low)` | `custom` | Low-medium | Fast |
| 15 | `lower_wick_ratio` | `(min(open,close) - low) / (high-low)` | `custom` | Low-medium | Fast |
| 16 | `close_location_value` | `(close-low) / (high-low)` | `custom` | Medium | Fast |
| 17 | `gap_prev_close_open` | `open / close.shift(1) - 1` | `custom` | Low on 24/7 crypto, but useful around jumps | Fast |
| 18 | `close_to_rolling_max_24` | `close / rolling_max_24 - 1` | `custom` | Medium | Fast |
| 19 | `close_to_rolling_min_24` | `close / rolling_min_24 - 1` | `custom` | Medium | Fast |
| 20 | `zscore_close_24` | `(close - ma24) / std24` | `zscore` or `custom` | Medium | Fast |
| 21 | `zscore_close_72` | `(close - ma72) / std72` | `zscore` or `custom` | Medium | Fast |
| 22 | `rolling_rank_24` | rolling percentile rank of close in 24h window | `custom` | Medium | Medium |
| 23 | `price_accel_3_6` | `ret_3h - ret_6h` style acceleration proxy | `custom` | Medium | Fast |
| 24 | `distance_to_vwap_24` | `close / rolling_vwap_24 - 1` | `vwap` + `custom` | Medium | Medium |

#### 5.5.2 Momentum Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 25 | `rsi_2` | short-horizon RSI | `rsi` | Medium-high | Fast |
| 26 | `rsi_6` | medium-short RSI | `rsi` | Medium-high | Fast |
| 27 | `rsi_14` | standard RSI | `rsi` | Medium | Fast |
| 28 | `rsi_28` | slow RSI | `rsi` | Medium | Fast |
| 29 | `stoch_k_14` | stochastic %K | `stoch` | Medium | Fast |
| 30 | `stoch_d_14` | stochastic %D | `stoch` | Medium | Fast |
| 31 | `stoch_k_d_spread` | `%K - %D` | `stoch` + `custom` | Medium | Fast |
| 32 | `willr_14` | Williams %R | `willr` | Medium | Fast |
| 33 | `roc_5` | rate of change 5 | `roc` | Medium-high | Fast |
| 34 | `roc_10` | rate of change 10 | `roc` | Medium-high | Fast |
| 35 | `roc_20` | rate of change 20 | `roc` | Medium | Fast |
| 36 | `cci_20` | Commodity Channel Index | `cci` | Medium | Fast |
| 37 | `cmo_14` | Chande Momentum Oscillator | `cmo` | Medium | Fast |
| 38 | `macd_line` | EMA12 - EMA26 | `macd` | Medium-high | Fast |
| 39 | `macd_signal` | signal line | `macd` | Medium | Fast |
| 40 | `macd_hist` | histogram | `macd` | Medium-high | Fast |
| 41 | `tsi_25_13` | True Strength Index | `tsi` | Medium | Fast |
| 42 | `uo_7_14_28` | Ultimate Oscillator | `uo` | Medium | Fast |
| 43 | `ppo_12_26` | Percentage Price Oscillator | `ppo` if available else `custom` | Medium | Fast |
| 44 | `mom_10` | Momentum over 10 bars | `mom` if available else `custom` | Medium | Fast |

#### 5.5.3 Trend Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 45 | `sma10_sma20_ratio` | `sma10 / sma20 - 1` | `sma` + `custom` | Medium | Fast |
| 46 | `sma20_sma50_ratio` | `sma20 / sma50 - 1` | `sma` + `custom` | Medium-high | Fast |
| 47 | `sma50_sma100_ratio` | `sma50 / sma100 - 1` | `sma` + `custom` | Medium | Fast |
| 48 | `ema12_ema26_ratio` | `ema12 / ema26 - 1` | `ema` + `custom` | Medium-high | Fast |
| 49 | `ema20_slope` | slope or delta of EMA20 | `ema` + `custom` | Medium-high | Fast |
| 50 | `ema50_slope` | slope or delta of EMA50 | `ema` + `custom` | Medium | Fast |
| 51 | `adx_14` | trend strength | `adx` | Medium-high | Fast |
| 52 | `plus_di_14` | positive directional indicator | `adx` | Medium | Fast |
| 53 | `minus_di_14` | negative directional indicator | `adx` | Medium | Fast |
| 54 | `plus_di_minus_di` | `+DI - -DI` | `adx` + `custom` | Medium-high | Fast |
| 55 | `aroon_up_25` | Aroon up | `aroon` | Medium | Fast |
| 56 | `aroon_down_25` | Aroon down | `aroon` | Medium | Fast |
| 57 | `aroon_osc_25` | Aroon oscillator | `aroon` + `custom` | Medium-high | Fast |
| 58 | `ichimoku_tenkan` | conversion line | `ichimoku` | Medium | Medium |
| 59 | `ichimoku_kijun` | base line | `ichimoku` | Medium | Medium |
| 60 | `ichimoku_tenkan_kijun_spread` | conversion minus base | `ichimoku` + `custom` | Medium-high | Medium |
| 61 | `psar_distance` | distance from close to PSAR | `psar` | Medium | Medium |
| 62 | `supertrend_dir_10_3` | trend direction from SuperTrend | `supertrend` | Medium-high | Medium |
| 63 | `supertrend_distance_10_3` | close distance to SuperTrend line | `supertrend` + `custom` | Medium-high | Medium |
| 64 | `vortex_pos_14` | positive VI | `vortex` | Medium | Fast |
| 65 | `vortex_neg_14` | negative VI | `vortex` | Medium | Fast |
| 66 | `vortex_diff_14` | positive minus negative VI | `vortex` + `custom` | Medium-high | Fast |
| 67 | `kama_distance` | distance to KAMA | `kama` | Medium | Medium |
| 68 | `hma20_slope` | Hull MA slope | `hma` if available else `custom` | Medium | Medium |
| 69 | `linreg_slope_20` | linear-regression slope of close | `linreg` if available else `custom` | Medium-high | Medium |

#### 5.5.4 Volatility Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 70 | `atr_14` | average true range | `atr` | Medium | Fast |
| 71 | `atr_pct` | `atr / close` | `atr` + `custom` | Medium-high | Fast |
| 72 | `natr_14` | normalized ATR | `natr` | Medium-high | Fast |
| 73 | `bb_upper_20_2` | Bollinger upper band | `bbands` | Low alone | Fast |
| 74 | `bb_lower_20_2` | Bollinger lower band | `bbands` | Low alone | Fast |
| 75 | `bb_width_20_2` | `(upper-lower)/mid` | `bbands` + `custom` | Medium-high | Fast |
| 76 | `bb_percent_b` | position within Bollinger band | `bbands` + `custom` | Medium-high | Fast |
| 77 | `kc_width_20` | Keltner width | `kc` | Medium | Fast |
| 78 | `donchian_width_20` | channel width | `donchian` | Medium-high | Fast |
| 79 | `donchian_breakout_pos` | close position in Donchian channel | `donchian` + `custom` | Medium-high | Fast |
| 80 | `ulcer_index_14` | downside volatility/discomfort | `ui` | Medium | Medium |
| 81 | `realized_vol_6` | std of 1h log returns over 6 bars | `custom` | Medium-high | Fast |
| 82 | `realized_vol_24` | std of 1h log returns over 24 bars | `custom` | Medium-high | Fast |
| 83 | `realized_vol_72` | std over 72 bars | `custom` | Medium | Fast |
| 84 | `realized_vol_ratio_6_24` | `rv6 / rv24` | `custom` | Medium-high | Fast |
| 85 | `garman_klass_vol_24` | OHLC-based volatility estimator | `custom` | Medium-high | Medium |
| 86 | `parkinson_vol_24` | range-based volatility estimator | `custom` | Medium | Medium |
| 87 | `chop_14` | choppiness index proxy | `chop` if available else `custom` | Medium | Medium |
| 88 | `vol_of_vol_24` | rolling std of realized vol | `custom` | Medium | Medium |

#### 5.5.5 Volume and Flow Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 89 | `volume_change_1` | `volume.pct_change(1)` | `custom` | Medium | Fast |
| 90 | `volume_change_6` | `volume.pct_change(6)` | `custom` | Medium | Fast |
| 91 | `volume_zscore_24` | `(volume - ma24)/std24` | `zscore` or `custom` | Medium-high | Fast |
| 92 | `volume_zscore_72` | longer z-score | `zscore` or `custom` | Medium | Fast |
| 93 | `volume_to_sma20` | `volume / volume_sma20` | `custom` | Medium-high | Fast |
| 94 | `quote_volume_zscore` | z-score of quote volume | `custom` | Medium-high | Fast |
| 95 | `trades_count_zscore` | z-score of number of trades | `custom` | Medium-high | Fast |
| 96 | `avg_trade_size` | `quote_volume / trades_count` | `custom` | Medium | Fast |
| 97 | `avg_trade_size_zscore` | rolling z-score of avg trade size | `custom` | Medium | Fast |
| 98 | `taker_buy_base_ratio` | `taker_buy_base / volume` | `custom` | High for venue flow proxy | Fast |
| 99 | `taker_buy_quote_ratio` | `taker_buy_quote / quote_volume` | `custom` | High for venue flow proxy | Fast |
| 100 | `obv` | On-Balance Volume | `obv` | Medium | Fast |
| 101 | `obv_slope_10` | short rolling slope of OBV | `obv` + `custom` | Medium-high | Medium |
| 102 | `mfi_14` | Money Flow Index | `mfi` | Medium-high | Fast |
| 103 | `cmf_20` | Chaikin Money Flow | `cmf` | Medium-high | Fast |
| 104 | `ad_line` | Accumulation/Distribution line | `ad` or `adosc` family, else `custom` | Medium | Fast |
| 105 | `adosc` | Chaikin oscillator | `adosc` | Medium | Fast |
| 106 | `eom_14` | Ease of Movement | `eom` | Medium | Fast |
| 107 | `vwap_distance` | close distance from session/rolling VWAP | `vwap` + `custom` | Medium-high | Medium |
| 108 | `vwma_ratio` | VWMA / close - 1 | `vwma` | Medium | Fast |

#### 5.5.6 Cross-Asset and Relative Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 109 | `btc_ret_1h` | BTC 1h return aligned to same timestamp | `custom` | Medium-high | Fast |
| 110 | `btc_ret_6h` | BTC 6h return | `custom` | Medium-high | Fast |
| 111 | `btc_realized_vol_24` | BTC realized volatility | `custom` | Medium-high | Fast |
| 112 | `eth_ret_1h` | ETH 1h return | `custom` | Medium | Fast |
| 113 | `eth_ret_6h` | ETH 6h return | `custom` | Medium | Fast |
| 114 | `asset_to_btc_return_spread` | asset return minus BTC return | `custom` | Medium-high | Fast |
| 115 | `asset_to_eth_return_spread` | asset return minus ETH return | `custom` | Medium | Fast |
| 116 | `rolling_corr_btc_24` | 24-bar rolling return correlation with BTC | `custom` | Medium-high | Medium |
| 117 | `rolling_corr_btc_72` | 72-bar rolling correlation | `custom` | Medium | Medium |
| 118 | `rolling_beta_btc_24` | rolling beta vs BTC | `custom` | Medium-high | Medium |
| 119 | `rolling_beta_eth_24` | rolling beta vs ETH | `custom` | Medium | Medium |
| 120 | `cross_sectional_return_rank` | rank of asset return among tracked universe | `custom` | Medium-high | Medium |
| 121 | `cross_sectional_momentum_rank` | rank of medium-horizon momentum across assets | `custom` | Medium-high | Medium |
| 122 | `cross_sectional_vol_rank` | rank of realized volatility among assets | `custom` | Medium | Medium |

#### 5.5.7 Crypto-Specific and Derivatives-Aware Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 123 | `funding_rate` | latest funding rate for corresponding perpetual | `custom` | High if available | Fast |
| 124 | `funding_rate_change` | delta in funding rate | `custom` | High if available | Fast |
| 125 | `open_interest` | futures OI aligned to spot bar | `custom` | High if available | Fast |
| 126 | `open_interest_change` | pct change in OI | `custom` | High if available | Fast |
| 127 | `oi_price_divergence` | OI change minus price change regime proxy | `custom` | High if available | Fast |
| 128 | `liquidation_long_notional` | long liquidation notional | `custom` | High if available | Medium |
| 129 | `liquidation_short_notional` | short liquidation notional | `custom` | High if available | Medium |
| 130 | `liquidation_imbalance` | long minus short liquidation pressure | `custom` | High if available | Medium |
| 131 | `basis_premium` | perp/spot basis or quarterly basis | `custom` | High if available | Fast |
| 132 | `exchange_inflow` | on-chain or exchange flow signal | `custom` | Medium-high if reliable | Slow |
| 133 | `exchange_outflow` | on-chain or exchange flow signal | `custom` | Medium-high if reliable | Slow |
| 134 | `stablecoin_supply_proxy` | stablecoin market/liquidity proxy | `custom` | Medium | Slow |

#### 5.5.8 Calendar and Cyclical Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 135 | `hour_of_day` | raw hour integer | `custom` | Low alone | Fast |
| 136 | `hour_sin` | `sin(2*pi*hour/24)` | `custom` | Medium when combined | Fast |
| 137 | `hour_cos` | `cos(2*pi*hour/24)` | `custom` | Medium when combined | Fast |
| 138 | `dow` | day-of-week integer | `custom` | Low alone | Fast |
| 139 | `dow_sin` | cyclical day-of-week | `custom` | Medium | Fast |
| 140 | `dow_cos` | cyclical day-of-week | `custom` | Medium | Fast |
| 141 | `month` | month integer | `custom` | Low alone | Fast |
| 142 | `month_sin` | cyclical month | `custom` | Low-medium | Fast |
| 143 | `month_cos` | cyclical month | `custom` | Low-medium | Fast |
| 144 | `is_weekend` | weekend flag | `custom` | Medium for crypto | Fast |
| 145 | `is_us_session_overlap` | overlap proxy for major liquidity hours | `custom` | Medium | Fast |

#### 5.5.9 Entropy and Information-Theoretic Features

| # | Feature | Formula / description | `pandas-ta-classic` | Expected predictive power | Cost |
|---:|---|---|---|---|---|
| 146 | `shannon_entropy_24` | Shannon entropy on recent return distribution | `entropy` or `custom` | Medium | Medium |
| 147 | `shannon_entropy_72` | longer-window Shannon entropy | `entropy` or `custom` | Medium | Medium |
| 148 | `sample_entropy_24` | complexity of recent return series | `custom` | Medium | Slow |
| 149 | `sample_entropy_72` | longer sample entropy | `custom` | Medium | Slow |
| 150 | `approximate_entropy_24` | ApEn of returns | `custom` | Medium | Slow |
| 151 | `approximate_entropy_72` | longer ApEn | `custom` | Medium | Slow |
| 152 | `permutation_entropy_24` | ordinal-pattern complexity | `custom` | Medium | Slow |
| 153 | `hurst_proxy_72` | persistence/mean-reversion proxy | `custom` | Medium | Slow |

### 5.6 Feature Set Size Recommendation

Recommended progression:

| Phase | Feature count | Goal |
|---|---:|---|
| Phase 1 | 25-35 | Build stable training and live feature parity |
| Phase 2 | 50-80 | Expand feature surface and let tree models prune useful interactions |
| Phase 3 | 80-120 | Add derivatives and cross-market context only if data quality is good |

### 5.7 Top 30 Features to Start With

If you want the most practical first set, start here:

| # | Starter feature | Why it belongs in v1 |
|---:|---|---|
| 1 | `ret_1h` | captures immediate drift/reversal |
| 2 | `ret_3h` | short horizon momentum |
| 3 | `ret_6h` | medium-short momentum |
| 4 | `ret_12h` | half-day trend context |
| 5 | `ret_24h` | daily momentum anchor |
| 6 | `logret_1h` | stable return transform |
| 7 | `sma20_sma50_ratio` | clean trend proxy |
| 8 | `ema12_ema26_ratio` | faster trend/momentum crossover information |
| 9 | `ema20_slope` | local trend direction |
| 10 | `rsi_2` | short-term mean-reversion signal |
| 11 | `rsi_14` | standard momentum context |
| 12 | `stoch_k_14` | short range-position oscillator |
| 13 | `macd_hist` | momentum acceleration |
| 14 | `adx_14` | trend-strength filter |
| 15 | `plus_di_minus_di` | directional trend asymmetry |
| 16 | `aroon_osc_25` | trend age and breakout context |
| 17 | `atr_pct` | volatility-normalized range |
| 18 | `bb_width_20_2` | squeeze/expansion context |
| 19 | `bb_percent_b` | price location inside volatility envelope |
| 20 | `donchian_width_20` | breakout regime context |
| 21 | `realized_vol_6` | short realized volatility |
| 22 | `realized_vol_24` | daily realized volatility |
| 23 | `volume_zscore_24` | abnormal activity |
| 24 | `quote_volume_zscore` | notional flow anomaly |
| 25 | `trades_count_zscore` | participation anomaly |
| 26 | `taker_buy_base_ratio` | buy-side aggression proxy |
| 27 | `mfi_14` | price-volume momentum |
| 28 | `cmf_20` | flow strength |
| 29 | `btc_ret_1h` | cross-asset market leader context |
| 30 | `rolling_corr_btc_24` | dependence on BTC regime |

If you can tolerate a slightly larger starter set, add:

- `hour_sin`
- `hour_cos`
- `dow_sin`
- `dow_cos`
- `shannon_entropy_24`

### 5.8 Feature Selection Strategy

Use a three-stage approach:

1. Start wide
2. Rank with walk-forward importance
3. Prune aggressively only after repeated out-of-sample evaluation

Recommended sequence:

| Step | Method | Why |
|---|---|---|
| 1 | correlation filtering | remove obvious duplicates |
| 2 | LightGBM gain importance | quick initial screen |
| 3 | SHAP summary over out-of-sample folds | more stable importance signal |
| 4 | remove expensive/unstable low-value features | simplify live pipeline |
| 5 | re-test reduced set | verify no hidden interaction loss |

### 5.9 Features with the Best Practical ROI

Most practical ROI for your current data:

- multi-horizon returns
- volatility-normalized price position metrics
- trend strength metrics
- quote volume and trades count anomalies
- taker-buy ratios
- cross-asset BTC context
- cyclical time features

Highest upside later, once you add more data:

- funding rates
- open interest
- liquidation imbalance
- basis
- on-chain exchange flows

### 5.10 Feature Engineering Conclusion

The right v1 feature strategy is not to over-debate indicator purity.  
It is to build:

- a broad but computable feature surface
- strict anti-leakage rules
- exact live/offline parity

Start with 30 features.  
Expand to 60-80 quickly once the pipeline is stable.

---

## 6. Model Architecture Options

### 6.1 Overview

You asked for four model families:

- gradient boosted trees
- neural networks
- ensembles
- reinforcement learning

The correct order of priority is:

1. Gradient boosted trees
2. FFN neural nets
3. Simple ensembles
4. LSTM/transformers only if justified
5. RL last

### 6.2 A. Gradient Boosted Trees Approach

#### 6.2.1 Why GBTs Are the Right First Production Model

They are:

- strong on tabular features
- robust with relatively small datasets
- fast to retrain
- explainable with SHAP
- usually hard to beat in early-stage financial ML

#### 6.2.2 Recommended Objective

Primary task:

- regression on next-bar log return

Secondary task:

- binary classification on cost-adjusted positive edge

Why start with regression:

- avoids arbitrary label thresholds too early
- preserves information
- lets you build signal policies separately

#### 6.2.3 LightGBM Hyperparameter Ranges

| Parameter | Suggested range | Notes |
|---|---|---|
| `objective` | `regression`, optionally `huber` | `huber` can help with heavy tails |
| `boosting_type` | `gbdt`, optionally `dart` later | `gbdt` first |
| `learning_rate` | `0.01` to `0.08` | lower is safer with more trees |
| `n_estimators` | `200` to `2000` | use early stopping |
| `num_leaves` | `15` to `127` | strong regularization lever |
| `max_depth` | `3` to `10` or `-1` | cap if overfitting |
| `min_child_samples` | `20` to `300` | finance data often benefits from larger values |
| `subsample` | `0.5` to `1.0` | row sampling |
| `subsample_freq` | `1` to `5` | activate subsampling |
| `feature_fraction` | `0.4` to `1.0` | column sampling |
| `reg_alpha` | `0` to `10` | L1 regularization |
| `reg_lambda` | `0` to `20` | L2 regularization |
| `min_split_gain` | `0` to `0.1` | split conservatism |
| `max_bin` | `63` to `255` | speed/precision tradeoff |

#### 6.2.4 XGBoost Hyperparameter Ranges

| Parameter | Suggested range | Notes |
|---|---|---|
| `objective` | `reg:squarederror` | first choice |
| `eta` | `0.01` to `0.1` | learning rate |
| `n_estimators` | `200` to `2000` | use early stopping |
| `max_depth` | `3` to `8` | finance data usually does not need deep trees |
| `min_child_weight` | `1` to `20` | useful regularizer |
| `subsample` | `0.5` to `1.0` | row sampling |
| `colsample_bytree` | `0.4` to `1.0` | feature sampling |
| `gamma` | `0` to `2` | split penalty |
| `lambda` | `1` to `20` | L2 |
| `alpha` | `0` to `10` | L1 |

#### 6.2.5 CatBoost Hyperparameter Ranges

| Parameter | Suggested range | Notes |
|---|---|---|
| `loss_function` | `RMSE` | first choice |
| `depth` | `4` to `8` | moderate depth |
| `learning_rate` | `0.01` to `0.08` | standard |
| `iterations` | `300` to `1500` | early stopping still helpful |
| `l2_leaf_reg` | `2` to `20` | strong regularization lever |
| `subsample` | `0.5` to `1.0` | if using Bernoulli bootstrap |

#### 6.2.6 Feature Selection: SHAP vs Recursive Elimination

Preferred order:

1. broad initial feature set
2. SHAP importance across walk-forward folds
3. remove persistently low-value features
4. re-train

Why SHAP first:

- captures nonlinear interactions better than simple recursive elimination
- easier to inspect for financial plausibility
- works especially well for tree models

Use RFE only as a secondary check, not the main pruning method.

#### 6.2.7 Handling Class Imbalance

If you use classification, class imbalance can appear because:

- most bars do not have strong cost-adjusted edge
- thresholded targets create many zeros

Practical guidance:

- prefer regression first
- if using classification, try moderate thresholding
- use `class_weight` only if imbalance is severe
- do not optimize raw accuracy
- optimize precision/recall of positive edge, expected value, and strategy metrics

#### 6.2.8 Walk-Forward Training Protocol

Mandatory protocol:

1. sort by timestamp
2. train on an expanding or rolling historical window
3. validate on the next contiguous test block
4. roll forward
5. aggregate strategy metrics across all folds

Recommended first design:

| Item | Recommendation |
|---|---|
| Train window | 180 to 365 days |
| Test window | 14 to 30 days |
| Retrain frequency | weekly at first |
| Embargo | 1-3 bars if features overlap heavily |
| Evaluation | return correlation, strategy Sharpe, PF, turnover, DD |

### 6.3 B. Neural Network Approach

#### 6.3.1 Feed-Forward Network First

The first NN to build should be a feed-forward network on the engineered feature table.

Recommended starter architecture:

| Component | Recommendation |
|---|---|
| Input | `n_features` |
| Hidden layer 1 | `256` |
| Hidden layer 2 | `128` |
| Hidden layer 3 | `64` |
| Activation | `SiLU` or `GELU` |
| Dropout | `0.1` to `0.3` |
| Normalization | optional `LayerNorm` or `BatchNorm1d` |
| Output | `1` regression node |

Why FFN before LSTM:

- lower complexity
- faster training
- easier debugging
- strong performance when features already summarize time structure

#### 6.3.2 LSTM

Recommended if, and only if, FFN and GBT plateau.

Suggested LSTM search space:

| Parameter | Suggested range |
|---|---|
| Sequence length | `24` to `72` bars |
| Hidden size | `32` to `128` |
| Layers | `1` to `2` |
| Dropout | `0.1` to `0.3` |
| Output head | regression head |

Pros:

- captures temporal patterns directly
- may exploit ordering better than tabular models

Cons:

- slower
- easier to overfit
- more sensitive to training setup
- more engineering burden for live inference

#### 6.3.3 Transformer-Based Options

Transformer variants worth knowing:

- `PatchTST`
- `iTransformer`
- small temporal self-attention models

Verdict for your scale:

- technically viable
- not the first practical move
- likely overkill for five assets on 1h bars unless you have multiple years of well-curated data and a clean GPU workflow

#### 6.3.4 Training Defaults for NNs

| Parameter | FFN recommendation | LSTM recommendation |
|---|---|---|
| Batch size | `128` to `1024` | `32` to `256` |
| Learning rate | `1e-4` to `3e-3` | `1e-4` to `1e-3` |
| Optimizer | `AdamW` | `AdamW` |
| Weight decay | `1e-5` to `1e-3` | `1e-5` to `1e-3` |
| Early stopping patience | `10` to `20` epochs | `10` to `20` epochs |
| Gradient clipping | optional | recommended |
| Loss | `MSE`, `Huber`, or weighted variant | same |

### 6.4 C. Ensemble Approach

#### 6.4.1 Why Ensemble at All

Finance models often fail for different reasons in different regimes.  
Ensembling can reduce model-specific fragility.

#### 6.4.2 Recommended Combination Order

Start with:

1. LightGBM
2. XGBoost
3. FFN

#### 6.4.3 Combination Methods

| Method | Complexity | Recommendation |
|---|---|---|
| Simple average | Low | Good first step |
| Validation-weighted average | Low-medium | Best first production ensemble |
| Stacking with ridge/logistic meta-model | Medium | Good phase 2 |
| Weighted voting on directional classes | Medium | Useful if you shift to classification |

#### 6.4.4 Best First Ensemble

Use validation-weighted averaging of out-of-sample predictions.

Example:

```text
pred = 0.5 * lgbm + 0.3 * xgb + 0.2 * ffn
```

Do not hand-pick weights permanently.  
Estimate them from walk-forward out-of-sample performance.

#### 6.4.5 Retraining Cadence

Recommended initial cadence:

| Component | Frequency |
|---|---|
| Feature computation | every closed 1h bar |
| Inference | every closed 1h bar |
| Threshold recalibration | weekly |
| Model retraining | weekly |
| Full hyperparameter retune | monthly or when performance drifts materially |

Daily retraining is possible, but usually not necessary at the start.

### 6.5 D. Reinforcement Learning

#### 6.5.1 Is RL Practical Here?

Not as the first implementation.

For five spot assets on hourly bars:

- data is not huge
- environment design becomes the real problem
- reward design is fragile
- you still need realistic costs and risk limits

If your supervised models cannot beat naive baselines, RL is unlikely to save the system.

#### 6.5.2 Library Comparison

| Library | Strengths | Weaknesses | Recommendation |
|---|---|---|---|
| `stable-baselines3` | easiest RL starting point, strong docs | still requires careful environment design | only if you insist on RL later |
| `RLlib` | scalable, flexible | much heavier operational stack | unnecessary here |
| custom RL | total control | highest engineering burden | avoid in phase 1 |

#### 6.5.3 Reward Function Design

If you do RL later, reward should not be raw PnL.  
Use something like:

```text
reward_t = pnl_t - fees_t - slippage_t - lambda_turnover * turnover_t - lambda_dd * drawdown_penalty_t
```

You may also include:

- inventory penalty
- volatility penalty
- position concentration penalty

#### 6.5.4 Verdict on RL

Recommendation:

- do not allocate serious time to RL until a supervised baseline with disciplined risk control is profitable out of sample

### 6.6 Model Architecture Conclusion

The best sequence is:

1. LightGBM regression
2. XGBoost regression
3. FFN regression
4. Validation-weighted ensemble
5. LSTM only if justified
6. RL later, if ever

---

## 7. Backtesting Frameworks

### 7.1 What the Framework Must Support

For this bot, the framework must handle:

- walk-forward validation
- multi-asset portfolios
- fees
- slippage
- signal thresholding
- position sizing logic
- easy integration with pandas DataFrames

### 7.2 Comparison Table

| Framework | Walk-forward support | Transaction cost modeling | Multi-asset support | Reporting quality | Speed | Fit for this project |
|---|---|---|---|---|---|---|
| `vectorbt` | Excellent with custom orchestration | Good | Strong | Strong | Excellent | Best |
| `backtesting.py` | Possible but simpler | Good | Limited relative to vectorbt | Good | Good | Secondary |
| `backtrader` | Strong | Strong | Strong | Good | Slower | Too heavy for phase 1 |
| `zipline-reloaded` | Good | Good | Historically strong | Good | Moderate | Less natural for 24/7 crypto |
| Custom pandas | Whatever you build | Whatever you build | Whatever you build | Custom | Depends | Necessary supplement |
| Existing `backtester.py` | Extendable | Already has fees/slippage path | Moderate with work | Existing metrics | Good enough | Extend, do not replace |

### 7.3 `vectorbt`

Why it is the best fit:

- fast vectorized research
- easy to run many parameter combinations
- natural pandas integration
- strong portfolio APIs
- already partially present in your codebase

What you still need to add:

- walk-forward orchestration
- model prediction injection
- portfolio-level exposure controls
- richer trade analytics

### 7.4 `backtesting.py`

Strengths:

- simple API
- pleasant for single-strategy prototypes
- quick interactive experimentation

Weaknesses for you:

- less natural for multi-asset research
- not as attractive when you already have vectorbt hooks

Verdict:

Good for toy prototypes.  
Not the best core engine for this repo.

### 7.5 `backtrader`

Strengths:

- feature-rich
- event-driven
- many examples

Weaknesses:

- older style
- more boilerplate
- slower research loop

Verdict:

Useful if you need a classical event-driven engine later.  
Not necessary now.

### 7.6 `zipline-reloaded`

Strengths:

- mature legacy quant concepts
- pipeline-style workflows

Weaknesses for crypto:

- more equity/trading-calendar shaped
- less natural for 24/7 spot crypto
- more setup weight than your project needs

Verdict:

Not the best fit.

### 7.7 Custom Pandas Logic

You still need custom pandas logic even if you use vectorbt because:

- purged walk-forward splitting is custom
- ML predictions are custom
- label generation is custom
- thresholding and sizing rules are custom

The right architecture is:

- custom pandas and model code for research pipeline
- vectorbt for portfolio simulation and metrics

### 7.8 Extending Your Existing `backtester.py`

This is the preferred path.

What to add:

| Addition | Why |
|---|---|
| walk-forward runner | evaluate ML honestly |
| prediction adapter | convert model outputs into entry/exit arrays |
| threshold optimizer | map regression outputs to trades |
| portfolio allocator | manage simultaneous signals across symbols |
| richer slippage model | reduce testnet realism gap |
| fold-level report persistence | compare folds, not just aggregate |

### 7.9 Recommended Walk-Forward Backtest Protocol

| Item | Recommendation |
|---|---|
| Universe | all 5 symbols together |
| Train window | 180-365 days |
| Test window | 14-30 days |
| Retrain | weekly |
| Signal input | model prediction at candle close |
| Execution assumption | next open or next bar VWAP proxy |
| Costs | exchange fees + slippage |
| Metrics | Sharpe, Sortino, PF, turnover, hit rate, DD, average hold |

### 7.10 Backtesting Conclusion

Recommendation:

- keep `vectorbt`
- extend your existing `backtester.py`
- use custom pandas code for dataset building and walk-forward orchestration

Do not replace the current backtester with a completely different framework unless the existing design proves unworkable.

---

## 8. Risk Management Improvements

### 8.1 First Principle

Risk management is not a post-processing detail.  
For your current bot, it is the difference between a 67% win rate that still loses money and a strategy with positive expectancy.

### 8.2 Immediate Problem to Fix

Current diagnosis:

- win rate: acceptable
- average loss: much larger than average win
- result: negative expectancy despite decent hit rate

This means you need exit logic and sizing discipline before live ML deployment.

### 8.3 Trailing Stops

#### 8.3.1 ATR-Based Stop

Starter rule:

```text
initial_stop = entry_price - k * ATR
```

Typical `k` values:

- `1.5`
- `2.0`
- `2.5`

Use larger multipliers for volatile names like SOL or XRP during stress.

#### 8.3.2 Percentage Trailing Stop

Simple but less adaptive:

```text
trailing_stop = max(trailing_stop, highest_price_since_entry * (1 - pct))
```

Good for operational simplicity, weaker than ATR in changing volatility regimes.

#### 8.3.3 Chandelier Exit

Recommended trend-friendly stop:

```text
stop = highest_high_since_entry - k * ATR
```

This is better than a fixed stop for trend continuation systems.

### 8.4 Dynamic Position Sizing

#### 8.4.1 Kelly and Fractional Kelly

Kelly is useful conceptually, dangerous operationally.

Recommendation:

- estimate edge from walk-forward data
- apply only fractional Kelly
- cap hard

Practical rule:

```text
position_fraction = min(0.25 * Kelly, max_risk_cap)
```

Do not let noisy live estimates determine size directly.

#### 8.4.2 Volatility-Scaled Sizing

Much safer default:

```text
position_size ~ risk_budget / atr_pct
```

This naturally reduces size in more volatile periods.

#### 8.4.3 Risk Parity Across Open Positions

Because your symbols are correlated, notional parity is misleading.

Better:

- allocate by inverse volatility
- then cap based on correlations

### 8.5 Portfolio-Level Risk

Recommended controls:

| Control | Recommendation |
|---|---|
| Max gross exposure | cap total open notional |
| Max per-position risk | cap to a fraction of equity |
| Correlation cap | reduce new long exposure if new asset is highly correlated with current holdings |
| Cluster cap | treat BTC/ETH/BNB/SOL/XRP as partially shared crypto-beta exposure |
| Max simultaneous positions | cap to avoid over-fragmentation |

### 8.6 Regime-Aware Sizing

Recommended rule:

- reduce size in high-volatility chop
- allow normal or slightly higher size in strong trend regimes

Example regime inputs:

- `adx_14`
- `realized_vol_ratio_6_24`
- `bb_width_20_2`
- entropy

Example policy:

| Regime | Size multiplier |
|---|---:|
| High-volatility chop | `0.4x` to `0.7x` |
| Neutral | `1.0x` |
| Clean trend, moderate vol | `1.1x` to `1.25x` |

### 8.7 Maximum Drawdown Control

You need hard kill-switches.

Recommended guardrails:

| Guardrail | Example |
|---|---|
| Daily loss limit | stop opening new positions after `-2%` daily equity move |
| Rolling 7-day DD | cut sizing by 50% or halt after threshold |
| Model degradation alert | disable model if recent live hit rate or Sharpe collapses vs expectation |
| Consecutive loss circuit breaker | pause after `N` losses if combined with regime instability |

### 8.8 Slippage Modeling

Testnet is not reality.

Model at minimum:

- exchange fee
- base slippage
- volatility-dependent slippage

Practical starting assumptions:

| Asset bucket | Base slippage assumption |
|---|---:|
| BTC, ETH, BNB | `5` to `10` bps |
| SOL, XRP | `8` to `20` bps |
| Stress regimes | multiply above by `2x` to `4x` |

If the strategy only works at zero slippage, it does not work.

### 8.9 Time Stops

Add a maximum holding horizon.

Example:

- if signal edge decays after 6-24 bars, do not hold longer

Time stops are especially useful for 1h strategies where stale positions accumulate opportunity cost.

### 8.10 Risk Management Conclusion

Before live ML deployment, implement:

1. ATR-based stop logic
2. volatility-scaled sizing
3. portfolio-level exposure caps
4. drawdown circuit breakers
5. realistic slippage

---

## 9. Production Architecture for the Existing FastAPI Backend

### 9.1 Design Goal

Add ML without destroying the current service boundaries.

### 9.2 Recommended Service Layout

Create a new package:

```text
backend/app/services/ml/
```

Recommended modules:

| Module | Responsibility |
|---|---|
| `data_ingest.py` | archive bootstrap, REST incremental sync, integrity checks |
| `feature_store.py` | deterministic feature computation and persistence |
| `label_store.py` | target generation and storage |
| `dataset_builder.py` | training matrices, fold slicing, leakage checks |
| `trainer.py` | model training and evaluation |
| `walkforward.py` | expanding/rolling validation loops |
| `registry.py` | model metadata and artifact tracking |
| `predictor.py` | load model and generate live prediction |
| `signal_policy.py` | convert predictions into entries/exits/sizes |
| `monitoring.py` | live metrics and drift checks |

### 9.3 Suggested Data Flow

1. Collect raw klines
2. Persist raw klines unchanged
3. Compute features for closed bars
4. Compute labels for historical bars
5. Build train/test matrices
6. Train models
7. Persist model + metadata
8. On each new closed candle, compute latest feature row
9. Generate prediction
10. Convert prediction into signal with risk controls

### 9.4 Recommended Database Tables

| Table | Purpose |
|---|---|
| `klines` | existing raw bars |
| `ml_features_1h` | persisted feature rows |
| `ml_labels_1h` | historical targets |
| `ml_training_runs` | study metadata, fold metrics |
| `ml_models` | model registry |
| `ml_predictions` | stored out-of-sample and live predictions |
| `ml_signal_decisions` | prediction-to-action mapping |
| `ml_live_metrics` | ongoing monitoring |

### 9.5 Model Versioning Fields

Store at least:

- model id
- algorithm name
- training start/end timestamps
- feature list
- feature hash
- label definition
- hyperparameters
- package versions
- git commit hash
- training metrics
- walk-forward metrics
- threshold policy

### 9.6 Candle-Close Inference

This is important for your current orchestrator.

Recommendation:

- do not infer every minute on the same 1h candle
- infer once, immediately after the 1h candle is closed and stored

That reduces:

- repeated decision noise
- accidental leakage from partial-bar information
- operational confusion

### 9.7 Shadow Mode Rollout

Do this before live order routing:

1. generate predictions every hour
2. log the signal that would have been traded
3. compare against actual realized outcomes
4. compare against the current rule strategy

Run shadow mode for at least 2-4 weeks before giving the ML model capital.

### 9.8 A/B Testing

Recommended rollout:

| Phase | Capital | Mode |
|---|---:|---|
| Shadow | 0% | prediction logging only |
| Pilot | 5-10% | small live allocation |
| Expansion | 25-50% | only if pilot is stable |
| Full adoption | case by case | after repeated validation |

### 9.9 Monitoring

Track in production:

- prediction distribution drift
- feature drift
- live vs backtest slippage gap
- hit rate
- profit factor
- Sharpe
- turnover
- drawdown
- trade frequency

### 9.10 Production Architecture Conclusion

You do not need a separate microservice fleet yet.  
You need:

- deterministic batch-style training
- candle-close inference
- versioned artifacts
- shadow deployment

---

## 10. Open Source Trading Bots with ML

### 10.1 Comparison Table

| Project | Stars observed | ML support | What to borrow | Verdict |
|---|---:|---|---|---|
| `freqtrade/freqtrade` | 47k+ | Strong via FreqAI | feature expansion, retraining patterns, config design | Most useful reference |
| `jesse-ai/jesse` | 7.5k+ | Limited first-class ML support | event-driven architecture, clean strategy engine | Useful engine patterns, less ML guidance |
| `hummingbot/hummingbot` | 17k+ | Weak native ML, stronger infra | connectors, execution architecture | Good infra reference |
| `tensortrade-org/tensortrade` | 6k+ | RL-focused | environment design ideas | Research-only for now |
| `AI4Finance-Foundation/FinRL` | 14k+ | RL-focused | portfolio/RL experimentation patterns | Educational, not first production path |
| `Yvictor/TradingGym` | 1.8k+ | RL environments | RL sandboxing | Niche later-phase reference |
| `edtechre/pybroker` | 3.2k+ | ML-friendly Python backtesting | strategy-research API ideas | Useful secondary reference |
| `asavinov/intelligent-trading-bot` | 1.6k+ | ML signal generation | ML feature/prediction pipeline ideas | Good niche reference |

### 10.2 Freqtrade and FreqAI

Why it matters:

- It is the clearest open-source example of ML integrated into a crypto bot
- FreqAI explicitly supports feature engineering expansion and periodic retraining
- It treats prediction and signal policy as related but separable concerns

What to borrow:

- feature configuration patterns
- model retraining orchestration
- feature expansion over multiple timeframes and correlated assets
- model artifact management ideas

What not to copy blindly:

- large framework complexity
- generic plugin layers you do not need

### 10.3 Jesse

Strengths:

- strong event-driven architecture
- clean backtesting/live-trading patterns
- good for systematic strategy development

Weakness:

- ML is not the core differentiator

Borrow:

- execution and strategy engine ideas
- clean state transition handling

### 10.4 Hummingbot

Strengths:

- robust exchange connectivity
- mature infrastructure

Weakness:

- ML alpha generation is not its main focus

Borrow:

- architecture ideas for connectors, risk layers, and deployment discipline

### 10.5 TradingGym, TensorTrade, FinRL

These are primarily RL/research ecosystems.

Value:

- useful to understand environment and reward design

Weakness for you:

- too far from the shortest path to a profitable 1h spot strategy

### 10.6 Open-Source Reference Conclusion

Best references by area:

| Need | Best reference |
|---|---|
| ML-enabled crypto bot patterns | Freqtrade / FreqAI |
| Event-driven trading engine ideas | Jesse |
| Connector and execution infrastructure | Hummingbot |
| RL experimentation only | FinRL / TensorTrade / TradingGym |

---

## 11. Recommended Implementation Roadmap

### 11.1 Final Recommendations

#### 11.1.1 Which Data Source to Use

Use:

1. Binance archive for backfill
2. Binance REST for incremental updates
3. Optional Binance futures endpoints later for funding/OI features

#### 11.1.2 Which ML Stack to Use

Use:

- `scikit-learn`
- `lightgbm`
- `xgboost`
- `pytorch`
- `optuna`
- `shap`
- `vectorbt`

#### 11.1.3 Which Features to Start With

Start with the top 30 list from Section 5.7.

#### 11.1.4 Which Model to Build First

Build:

- LightGBM regression on next-bar log return

Then:

- XGBoost
- FFN
- simple ensemble

#### 11.1.5 Which Backtesting Framework

Use:

- current `backtester.py`
- keep the vectorbt path
- extend with walk-forward orchestration

### 11.2 Concrete Milestones

| Phase | Duration | Deliverables |
|---|---|---|
| 0. Data hardening | 1-3 days | full backfill, integrity checks, archive loader |
| 1. Feature store | 2-4 days | 30-60 deterministic features persisted |
| 2. Baseline models | 4-7 days | Ridge, ElasticNet, RF, LightGBM, XGBoost |
| 3. Walk-forward engine | 2-4 days | fold orchestration, metrics, reports |
| 4. Signal policy tuning | 2-3 days | thresholds, sizing, exits |
| 5. Shadow deployment | 2-4 weeks runtime | prediction logs, drift monitoring |
| 6. FFN + ensemble | 1-2 weeks | PyTorch model and ensemble |
| 7. Optional advanced models | later | LSTM, transformer, RL only if justified |

### 11.3 Specific Hyperparameter Ranges to Search

#### 11.3.1 LightGBM

- `learning_rate`: `0.01` to `0.08`
- `num_leaves`: `15` to `127`
- `max_depth`: `3` to `10`
- `min_child_samples`: `20` to `300`
- `subsample`: `0.5` to `1.0`
- `feature_fraction`: `0.4` to `1.0`
- `reg_alpha`: `0` to `10`
- `reg_lambda`: `0` to `20`
- `n_estimators`: `200` to `2000`

#### 11.3.2 XGBoost

- `eta`: `0.01` to `0.1`
- `max_depth`: `3` to `8`
- `min_child_weight`: `1` to `20`
- `subsample`: `0.5` to `1.0`
- `colsample_bytree`: `0.4` to `1.0`
- `gamma`: `0` to `2`
- `lambda`: `1` to `20`
- `alpha`: `0` to `10`

#### 11.3.3 FFN

- hidden dims: `[128, 64]`, `[256, 128, 64]`
- dropout: `0.1` to `0.3`
- lr: `1e-4` to `3e-3`
- weight decay: `1e-5` to `1e-3`
- batch size: `128` to `1024`

### 11.4 Success Metrics

Suggested research thresholds:

| Metric | Minimum acceptable | Strong target |
|---|---:|---:|
| Out-of-sample Sharpe | `> 0.8` | `> 1.2` |
| Profit factor | `> 1.15` | `> 1.30` |
| Max drawdown | `< 12%` | `< 8%` |
| Monthly trade count | `20+` | `30-60` |
| Average reward/risk | `> 1.0` | `> 1.2` |
| Calibration stability | stable across folds | stable across folds |

### 11.5 What Not to Optimize For

Do not optimize primarily for:

- win rate
- in-sample Sharpe
- one lucky fold
- minimum drawdown at the cost of never trading

### 11.6 Final Roadmap Recommendation

The shortest path to a materially better bot is:

1. venue-aligned historical data
2. 30-80 engineered features
3. LightGBM walk-forward baseline
4. proper signal policy and risk layer
5. shadow deployment
6. FFN and ensemble later

That path is practical, cheap, and aligned with both the literature and the current codebase.

---

## 12. Appendix A: Install Commands and Versions

### 12.1 Currently Relevant Versions Observed

| Package | Version |
|---|---|
| `scikit-learn` | `1.5.2` installed, `1.8.0` latest observed |
| `pandas-ta-classic` | `0.3.59` installed, `0.4.47` latest observed |
| `xgboost` | `3.1.0` installed, `3.2.0` latest observed |
| `lightgbm` | `4.6.0` latest observed |
| `catboost` | `1.2.10` latest observed |
| `statsmodels` | `0.14.5` installed, `0.14.6` latest observed |
| `torch` | `2.10.0` latest observed |
| `tensorflow` | `2.21.0` latest observed |
| `optuna` | `4.8.0` latest observed |
| `shap` | `0.49.1` installed, `0.51.0` latest observed |
| `vectorbt` | `0.28.4` latest observed |
| `backtesting` | `0.6.5` latest observed |
| `backtrader` | `1.9.78.123` latest observed |
| `zipline-reloaded` | `3.1.1` latest observed |
| `stable-baselines3` | `2.7.1` latest observed |
| `ray` | `2.54.0` latest observed |
| `ccxt` | `4.5.44` latest observed |

### 12.2 Recommended Install Commands

```powershell
cd backend
python -m pip install --upgrade lightgbm xgboost optuna shap vectorbt backtesting statsmodels ccxt
python -m pip install --upgrade torch --index-url https://download.pytorch.org/whl/cpu
```

Optional:

```powershell
cd backend
python -m pip install --upgrade catboost
python -m pip install --upgrade stable-baselines3 gymnasium
```

Avoid installing TensorFlow unless you specifically decide to standardize on it.

---

## 13. Appendix B: Code Snippets

### 13.1 Binance REST Kline Fetch

```python
import requests
import pandas as pd


def fetch_klines(symbol: str, interval: str = "1h", start_time: int | None = None, end_time: int | None = None, limit: int = 1000) -> pd.DataFrame:
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    if start_time is not None:
        params["startTime"] = start_time
    if end_time is not None:
        params["endTime"] = end_time

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "ignore",
    ]
    df = pd.DataFrame(data, columns=cols)
    numeric = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ]
    df[numeric] = df[numeric].astype(float)
    df["trades_count"] = df["trades_count"].astype(int)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    return df.drop(columns=["ignore"])
```

### 13.2 `ccxt` Fallback Collector

```python
import ccxt
import pandas as pd


def fetch_binance_ohlcv_ccxt(symbol: str = "BTC/USDT", timeframe: str = "1h", since: int | None = None, limit: int = 1000) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True})
    rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df
```

### 13.3 Starter Feature Builder

```python
import numpy as np
import pandas as pd
import pandas_ta_classic as ta


def build_features(df: pd.DataFrame, btc_close: pd.Series | None = None) -> pd.DataFrame:
    out = df.copy()

    out["ret_1h"] = out["close"].pct_change(1)
    out["ret_3h"] = out["close"].pct_change(3)
    out["ret_6h"] = out["close"].pct_change(6)
    out["ret_12h"] = out["close"].pct_change(12)
    out["ret_24h"] = out["close"].pct_change(24)
    out["logret_1h"] = np.log(out["close"] / out["close"].shift(1))

    out["sma20"] = ta.sma(out["close"], length=20)
    out["sma50"] = ta.sma(out["close"], length=50)
    out["ema12"] = ta.ema(out["close"], length=12)
    out["ema26"] = ta.ema(out["close"], length=26)
    out["ema20"] = ta.ema(out["close"], length=20)

    out["sma20_sma50_ratio"] = out["sma20"] / out["sma50"] - 1
    out["ema12_ema26_ratio"] = out["ema12"] / out["ema26"] - 1
    out["ema20_slope"] = out["ema20"].diff()

    out["rsi_2"] = ta.rsi(out["close"], length=2)
    out["rsi_14"] = ta.rsi(out["close"], length=14)

    stoch = ta.stoch(out["high"], out["low"], out["close"])
    out["stoch_k_14"] = stoch.iloc[:, 0]

    macd = ta.macd(out["close"])
    out["macd_hist"] = macd.iloc[:, 1] if macd.shape[1] > 1 else macd.iloc[:, 0]

    adx = ta.adx(out["high"], out["low"], out["close"], length=14)
    out["adx_14"] = adx.iloc[:, 0]
    out["plus_di_minus_di"] = adx.iloc[:, 1] - adx.iloc[:, 2]

    aroon = ta.aroon(out["high"], out["low"], length=25)
    out["aroon_osc_25"] = aroon.iloc[:, 0] - aroon.iloc[:, 1]

    out["atr"] = ta.atr(out["high"], out["low"], out["close"], length=14)
    out["atr_pct"] = out["atr"] / out["close"]

    bb = ta.bbands(out["close"], length=20, std=2)
    out["bb_width_20_2"] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / bb.iloc[:, 1]
    out["bb_percent_b"] = (out["close"] - bb.iloc[:, 2]) / (bb.iloc[:, 0] - bb.iloc[:, 2])

    out["realized_vol_6"] = out["logret_1h"].rolling(6).std()
    out["realized_vol_24"] = out["logret_1h"].rolling(24).std()

    out["volume_zscore_24"] = (out["volume"] - out["volume"].rolling(24).mean()) / out["volume"].rolling(24).std()
    out["quote_volume_zscore"] = (out["quote_volume"] - out["quote_volume"].rolling(24).mean()) / out["quote_volume"].rolling(24).std()
    out["trades_count_zscore"] = (out["trades_count"] - out["trades_count"].rolling(24).mean()) / out["trades_count"].rolling(24).std()
    out["taker_buy_base_ratio"] = out["taker_buy_base_volume"] / out["volume"].replace(0, np.nan)
    out["mfi_14"] = ta.mfi(out["high"], out["low"], out["close"], out["volume"], length=14)
    out["cmf_20"] = ta.cmf(out["high"], out["low"], out["close"], out["volume"], length=20)

    if btc_close is not None:
        btc_ret_1h = btc_close.pct_change(1).reindex(out.index)
        out["btc_ret_1h"] = btc_ret_1h
        out["rolling_corr_btc_24"] = out["logret_1h"].rolling(24).corr(np.log(btc_close / btc_close.shift(1)).reindex(out.index))

    hour = out.index.hour
    dow = out.index.dayofweek
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    out["dow_cos"] = np.cos(2 * np.pi * dow / 7)

    out["target_logret_1h"] = np.log(out["close"].shift(-1) / out["close"])
    return out
```

### 13.4 LightGBM Training Skeleton

```python
import lightgbm as lgb
from sklearn.metrics import mean_squared_error


def train_lgbm(X_train, y_train, X_valid, y_valid):
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=1000,
        learning_rate=0.03,
        num_leaves=31,
        max_depth=6,
        min_child_samples=100,
        subsample=0.8,
        subsample_freq=1,
        feature_fraction=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_valid, y_valid)],
        eval_metric="l2",
        callbacks=[lgb.early_stopping(100), lgb.log_evaluation(50)],
    )
    preds = model.predict(X_valid)
    rmse = mean_squared_error(y_valid, preds, squared=False)
    return model, preds, rmse
```

### 13.5 Optuna Walk-Forward Objective Skeleton

```python
import optuna
import numpy as np


def objective(trial):
    params = {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 300),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.4, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 20.0),
    }

    fold_scores = []
    for fold in walkforward_splits:
        model = make_lgbm(params)
        model.fit(fold.X_train, fold.y_train)
        pred = model.predict(fold.X_test)
        score = strategy_sharpe_from_predictions(pred, fold.market_df)
        fold_scores.append(score)

    return float(np.mean(fold_scores))


study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)
```

### 13.6 PyTorch FFN Skeleton

```python
import torch
from torch import nn


class TabularFFN(nn.Module):
    def __init__(self, in_features: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.SiLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.SiLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.SiLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)
```

### 13.7 Walk-Forward Portfolio Evaluation Sketch

```python
def regression_to_signal(pred, entry_threshold=0.0008, exit_threshold=0.0):
    long_entry = pred > entry_threshold
    long_exit = pred < exit_threshold
    return long_entry, long_exit


def run_walkforward_backtest(folds, fee=0.001, slippage=0.0005):
    all_results = []
    for fold in folds:
        model = train_model(fold.X_train, fold.y_train, fold.X_valid, fold.y_valid)
        pred = model.predict(fold.X_test)
        entries, exits = regression_to_signal(pred)
        result = backtest_with_vectorbt(
            prices=fold.market_df["close"],
            entries=entries,
            exits=exits,
            fee=fee,
            slippage=slippage,
        )
        all_results.append(result)
    return summarize_results(all_results)
```

### 13.8 Suggested Model Metadata JSON

```json
{
  "model_id": "lgbm_1h_v001",
  "algorithm": "lightgbm_regression",
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
  "timeframe": "1h",
  "train_window_days": 365,
  "test_window_days": 30,
  "retrain_frequency": "weekly",
  "target": "log(close[t+1]/close[t])",
  "feature_hash": "sha256:...",
  "feature_count": 30,
  "threshold_policy": {
    "entry_threshold": 0.0008,
    "exit_threshold": 0.0
  },
  "cost_assumptions": {
    "fee_bps": 10,
    "slippage_bps": 8
  }
}
```

---

## 14. Appendix C: Source Links and References

### 14.1 Core Papers and Academic References

- Kelly, B., and Xiu, D. (2023), *Financial Machine Learning*, SSRN: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4501707>
- G-Research wrap-up: <https://www.gresearch.com/blog/article/wrapping-up-the-g-research-crypto-forecasting-competition/>

### 14.2 Official Market Data Documentation

- Binance spot market data endpoints: <https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints>
- Binance general API information / testnet docs: <https://developers.binance.com/docs/binance-spot-api-docs/testnet/rest-api/general-api-information>
- Binance public data archive: <https://data.binance.vision/>
- CoinGecko API docs: <https://docs.coingecko.com/reference/coins-id-market-chart>
- CoinGecko OHLC docs: <https://docs.coingecko.com/reference/coins-id-ohlc>
- CryptoCompare historical docs: <https://min-api.cryptocompare.com/documentation?cat=dataHistohour&key=Historical>
- Kaiko home: <https://www.kaiko.com/>
- CoinAPI pricing and docs entry points: <https://www.coinapi.io/> and <https://www.coinapi.io/pricing>

### 14.3 Library Documentation

- CCXT manual: <https://github.com/ccxt/ccxt/wiki/Manual>
- LightGBM docs: <https://lightgbm.readthedocs.io/>
- XGBoost docs: <https://xgboost.readthedocs.io/>
- CatBoost docs: <https://catboost.ai/>
- scikit-learn docs: <https://scikit-learn.org/stable/>
- PyTorch docs: <https://pytorch.org/docs/stable/>
- PyTorch install selector: <https://pytorch.org/get-started/locally/>
- TensorFlow install/docs: <https://www.tensorflow.org/install/pip>
- statsmodels docs: <https://www.statsmodels.org/stable/>
- Optuna docs: <https://optuna.readthedocs.io/>
- SHAP docs: <https://shap.readthedocs.io/>
- vectorbt docs: <https://vectorbt.dev/>
- backtesting.py docs: <https://kernc.github.io/backtesting.py/>
- backtrader site: <https://www.backtrader.com/>
- Zipline Reloaded docs: <https://zipline.ml4trading.io/>
- Stable-Baselines3 docs: <https://stable-baselines3.readthedocs.io/>
- Ray RLlib docs: <https://docs.ray.io/en/latest/rllib/>

### 14.4 Open Source Bot References

- Freqtrade docs: <https://www.freqtrade.io/>
- FreqAI feature engineering docs: <https://docs.freqtrade.io/en/2024.9/freqai-feature-engineering/>
- FreqAI parameter table: <https://www.freqtrade.io/en/stable/freqai-parameter-table/>
- Jesse: <https://github.com/jesse-ai/jesse>
- Hummingbot: <https://github.com/hummingbot/hummingbot>
- Hummingbot Quants Lab: <https://hummingbot.org/quants-lab/>
- TensorTrade: <https://github.com/tensortrade-org/tensortrade>
- FinRL: <https://github.com/AI4Finance-Foundation/FinRL>
- TradingGym: <https://github.com/Yvictor/TradingGym>
- PyBroker: <https://github.com/edtechre/pybroker>
- Intelligent Trading Bot: <https://github.com/asavinov/intelligent-trading-bot>

### 14.5 Practitioner and Competition-Style References

- CryptoDataDownload exchange datasets: <https://www.cryptodatadownload.com/data/binance/>
- Kaggle G-Research competition landing page: <https://www.kaggle.com/c/g-research-crypto-forecasting>
- Example mirrored competition summary: <https://kaggle.curtischong.me/competitions/G-Research-Crypto-Forecasting>

---

## 15. Appendix D: Data Quality and Leakage Checklists

### 15.1 Why These Checklists Matter

Most trading ML projects fail for boring reasons:

- missing bars
- duplicated bars
- timezone mistakes
- target leakage
- implicit look-ahead through joins
- unrealistic execution assumptions

The fastest way to waste a month is to skip these controls.

### 15.2 Raw Kline Data QA Checklist

Use this checklist after every backfill and every incremental sync:

| Check | Pass condition | Failure implication |
|---|---|---|
| symbol present | all expected symbols loaded | incomplete universe |
| timeframe present | only expected timeframe values | mixed-bar contamination |
| monotonic timestamps | strictly increasing by symbol | load or sort bug |
| duplicate timestamps | zero duplicates per symbol/timeframe | duplicate bars corrupt rolling features |
| missing timestamps | zero unexpected gaps | feature windows become inconsistent |
| open time alignment | every bar aligned to exact hour | timezone or parsing bug |
| close time alignment | exact expected 1h close boundary | API translation bug |
| OHLC numeric parse | no string residues | downstream model matrix failure |
| volume numeric parse | no string residues | bad feature generation |
| nonnegative volume | all volume >= 0 | parse or source corruption |
| high >= low | always true | invalid bar |
| high >= open/close | always true | invalid bar |
| low <= open/close | always true | invalid bar |
| quote volume available | non-null for Binance feed | missed field mapping |
| trades count available | non-null for Binance feed | missed field mapping |
| taker-buy fields available | non-null for Binance feed | missed field mapping |
| no future timestamps | max timestamp <= current closed bar | partial-bar leakage |
| continuity after archive load | no missing month/day blocks | archive ingestion bug |
| continuity after REST patch | no overlap bugs | duplicate or lost increments |
| symbol listing start sanity | first bar roughly near listing history | incorrect archive path |

### 15.3 Kline Field-Level QA Rules

Recommended assertions in code:

1. `open_time` is timezone-aware UTC
2. `close_time` is timezone-aware UTC
3. `close_time - open_time == interval - 1 ms` for raw Binance schema, or is normalized consistently after ingestion
4. `volume >= 0`
5. `quote_volume >= 0`
6. `trades_count >= 0`
7. `taker_buy_base_volume <= volume + epsilon`
8. `taker_buy_quote_volume <= quote_volume + epsilon`
9. `notional`-derived fields do not overflow float precision for current asset scale
10. `symbol`, `timeframe`, `open_time` form a unique key

### 15.4 Incremental Sync QA Checklist

For each hourly update job:

- fetch the latest two or three closed bars, not just one
- upsert rather than blind insert
- verify stored latest close time after insert
- compare expected next timestamp to actual
- log rows inserted
- log rows updated
- log symbols with gaps
- log symbols with delayed close
- alert on zero bars fetched for any active symbol
- alert on repeated stale latest timestamp
- alert on REST failure bursts
- alert on database write failures

### 15.5 Feature Store QA Checklist

Every feature pipeline run should validate:

| Check | Pass condition |
|---|---|
| feature row count | matches eligible raw-bar count minus warmup |
| one row per symbol/timestamp | unique constraint passes |
| no forbidden NaNs after warmup | only expected NaNs in early warmup zone |
| finite values | no inf or -inf |
| feature naming consistency | exact expected schema |
| feature dtype consistency | numeric columns are numeric |
| rolling-window warmup documented | first usable row clearly defined |
| cyclical features bounded | values in `[-1, 1]` |
| ratio features safe | denominator-zero handling present |
| z-score features stable | std-zero handling present |
| cross-asset joins aligned | join timestamps exact |
| entropy features deterministic | repeated run gives same values |

### 15.6 Leakage Checklist: Feature Engineering

These are the most common feature leakage traps:

1. computing a rolling metric with centered windows
2. joining BTC features from a later timestamp due to timezone mismatch
3. using current candle intrabar state when the live system only has candle close
4. using target-shifted columns in feature matrices by accident
5. normalizing across the full dataset rather than the training window
6. imputing missing values with information from future rows
7. fitting PCA or feature scaling on all rows before walk-forward splitting
8. computing cross-sectional ranks using assets that were unavailable at that timestamp
9. using future-derived labels inside threshold selection for the current fold
10. using forward-filled derivatives data that arrives after the bar close in reality

### 15.7 Leakage Checklist: Training and Validation

Never do the following:

- random train/test split on time-series bars
- shuffling rows before model fit
- tuning hyperparameters on one test month and reporting that same month
- optimizing thresholds on the same fold used for reporting
- training on a fold that includes the future of another asset if your decision uses cross-asset contemporaneous data incorrectly
- computing feature importance on the full dataset and pruning before walk-forward testing

### 15.8 Leakage Checklist: Signal Policy

Common mistakes:

- entering on the same close used to compute the signal without explicitly assuming it
- using next-bar high/low to determine whether a stop would have been hit before entry
- using end-of-bar realized volatility that includes the bar you claim to enter at its open
- optimizing stop-loss multipliers on the final reported test window

### 15.9 Label Construction Checklist

For every label definition, record:

- target formula
- forward horizon
- whether costs are included
- whether slippage is included
- whether execution is assumed at next open, next close, or VWAP proxy
- whether labels are clipped or winsorized
- whether classification thresholds are fixed or regime-adaptive
- whether labels differ by asset

### 15.10 Train/Test Split Checklist

Before any reported result:

1. confirm train and test windows are contiguous
2. confirm test begins strictly after train ends
3. confirm hyperparameter tuning is nested or otherwise separated
4. confirm no feature fit step used test data
5. confirm no scaler fit step used test data
6. confirm no target-based pruning used test data
7. confirm performance is aggregated across multiple folds
8. confirm reported metrics are after fees and slippage

### 15.11 Execution Assumption Checklist

Document:

- signal timestamp
- order placement timestamp
- fill price assumption
- fee assumption
- slippage assumption
- partial-fill assumption
- max concurrent positions
- priority when multiple symbols trigger simultaneously

### 15.12 Model Registry Checklist

Every saved model should include:

- model id
- training timestamp
- training data window
- feature schema version
- preprocessing schema version
- label definition
- hyperparameters
- random seed
- package versions
- git commit
- backtest result summary

### 15.13 Monitoring QA Checklist

Daily or hourly checks:

- latest data freshness
- feature freshness
- prediction freshness
- model artifact load success
- prediction distribution drift
- feature mean/std drift
- live slippage drift vs assumption
- turnover drift
- drawdown drift
- trade-count drift

### 15.14 Pre-Live Promotion Checklist

Promote a model only if:

1. data QA passed for the full training window
2. feature QA passed
3. walk-forward metrics exceeded minimum thresholds
4. model stability across folds is acceptable
5. no single symbol carries all performance
6. slippage sensitivity analysis still leaves positive expectancy
7. shadow-mode behavior matches offline logic

### 15.15 Post-Mortem Checklist for a Bad Fold

When a fold performs badly, inspect:

- regime shift
- data gap
- overtrading
- threshold too low
- volatility spike
- correlation spike across assets
- one symbol dominating losses
- stop-loss too wide
- slippage underestimation
- feature drift

### 15.16 Minimum QA Automation to Implement in Code

Build automated tests for:

- duplicate timestamps
- missing intervals
- invalid OHLC relationships
- non-finite feature values
- label/feature alignment
- train/test separation
- same-row prediction parity between offline and online feature builders

---

## 16. Appendix E: Experiment Backlog and Search Grids

### 16.1 Why a Backlog Matters

Without a fixed backlog, research degenerates into:

- ad hoc tuning
- cherry-picking
- undocumented pivots

The solution is a ranked experiment queue.

### 16.2 Recommended Experiment Naming Convention

Use a deterministic naming scheme:

```text
ALG_TARGET_FEATURESET_WINDOW_THRESHOLD_COSTS_VERSION
```

Example:

```text
LGBM_LOGRET1H_FS30_TR365_TE30_TH08_COST10BPS_V001
```

### 16.3 Phase-1 Baseline Experiment Queue

| Priority | Experiment | Goal |
|---:|---|---|
| 1 | Ridge on 30 features | linear sanity check |
| 2 | ElasticNet on 30 features | sparse regularized baseline |
| 3 | RandomForest on 30 features | nonlinear ensemble baseline |
| 4 | LightGBM on 30 features | first serious tabular benchmark |
| 5 | XGBoost on 30 features | second serious tabular benchmark |
| 6 | LightGBM on 50 features | test richer feature surface |
| 7 | XGBoost on 50 features | compare expansion effect |
| 8 | LightGBM on 30 features plus calendar | assess cyclical contribution |
| 9 | LightGBM on 30 features plus BTC context | assess cross-asset lift |
| 10 | LightGBM on 30 features plus entropy | assess complexity features |
| 11 | LightGBM with Huber loss | robustness to outliers |
| 12 | LightGBM with wider slippage | sensitivity check |

### 16.4 Phase-2 Experiment Queue

| Priority | Experiment | Goal |
|---:|---|---|
| 13 | LightGBM on 80 features | broader tabular model |
| 14 | XGBoost on 80 features | ensemble candidate |
| 15 | CatBoost on 80 features | optional third tree candidate |
| 16 | FFN on 30 features | first NN benchmark |
| 17 | FFN on 80 features | richer NN benchmark |
| 18 | FFN with Huber loss | robust regression |
| 19 | LightGBM + FFN average | simple ensemble |
| 20 | LightGBM + XGBoost average | tree ensemble |
| 21 | LightGBM + XGBoost + FFN | validation-weighted ensemble |
| 22 | Threshold optimization by fold | improve trade conversion |
| 23 | ATR stop sweep | fix payoff asymmetry |
| 24 | volatility-size sweep | improve risk control |

### 16.5 Phase-3 Experiment Queue

| Priority | Experiment | Goal |
|---:|---|---|
| 25 | LSTM sequence 24 | first sequence model |
| 26 | LSTM sequence 48 | more context |
| 27 | LSTM sequence 72 | longer context |
| 28 | derivatives features added | test futures context |
| 29 | funding + OI only | isolate derivative lift |
| 30 | liquidation features | test liquidation regime edge |
| 31 | transformer-lite | test attention only if justified |
| 32 | meta-labeling on top of LGBM | improve precision |

### 16.6 Threshold Search Grid

For regression-to-signal conversion, test:

| Entry threshold | Exit threshold | Notes |
|---:|---:|---|
| `0.0000` | `0.0000` | maximum activity, likely too noisy |
| `0.0003` | `0.0000` | mild threshold |
| `0.0005` | `0.0000` | balanced starting point |
| `0.0008` | `0.0000` | conservative starter |
| `0.0010` | `0.0002` | slightly hysteretic exit |
| `0.0015` | `0.0005` | low turnover |
| quantile 60 | quantile 50 | percentile-based dynamic threshold |
| quantile 70 | quantile 55 | stronger dynamic threshold |

### 16.7 Stop-Loss Search Grid

| Stop type | Candidate values |
|---|---|
| ATR stop | `1.5x`, `2.0x`, `2.5x`, `3.0x` |
| percentage stop | `0.8%`, `1.2%`, `1.8%`, `2.5%` |
| chandelier | `2.0x ATR`, `2.5x ATR`, `3.0x ATR` |
| time stop | `6`, `12`, `24`, `48` bars |

### 16.8 Take-Profit Search Grid

| Exit type | Candidate values |
|---|---|
| fixed reward target | `1.0x`, `1.5x`, `2.0x` initial risk |
| trailing only | none fixed |
| hybrid | partial at `1.0x`, trail remainder |
| time exit | `12`, `24`, `36` bars |

### 16.9 Position-Sizing Search Grid

| Method | Candidate values |
|---|---|
| fixed notional | `5%`, `10%`, `15%` per signal |
| inverse ATR | base risk budget `0.25%`, `0.5%`, `0.75%` |
| inverse realized vol | same grid as above |
| fractional Kelly cap | `10%`, `20%`, `25%` of Kelly |
| correlation-adjusted | cap effective exposure if `corr > 0.75` |

### 16.10 Train/Test Window Grid

| Train days | Test days | Why test it |
|---:|---:|---|
| 180 | 14 | more reactive |
| 180 | 30 | balanced short memory |
| 270 | 30 | medium memory |
| 365 | 30 | strong baseline |
| 365 | 14 | stable train, reactive test |
| 540 | 30 | slow-adapting long memory |

### 16.11 Retraining Frequency Grid

| Retrain cadence | Use case |
|---|---|
| every bar | likely overkill/noisy |
| daily | aggressive adaptation |
| weekly | recommended baseline |
| biweekly | lower operational cost |
| monthly | only if performance is stable |

### 16.12 Cost Assumption Grid

| Scenario | Fee bps | Slippage bps |
|---|---:|---:|
| optimistic BTC/ETH | 10 | 5 |
| realistic liquid | 10 | 8 |
| cautious liquid | 10 | 12 |
| realistic alt | 10 | 15 |
| stressed alt | 10 | 25 |

### 16.13 Metrics to Track Per Experiment

Track at least:

1. mean fold Sharpe
2. median fold Sharpe
3. worst fold Sharpe
4. mean profit factor
5. mean max drawdown
6. monthly trade count
7. mean holding time
8. gross exposure
9. slippage sensitivity
10. symbol concentration of returns

### 16.14 Minimum Result Table Schema

Persist:

- experiment id
- parent experiment id
- timestamp
- code commit
- feature set name
- label name
- train window
- test window
- model params
- threshold params
- stop params
- sizing params
- fee/slippage assumptions
- fold metrics
- aggregate metrics

### 16.15 Experiment Stop Rules

Kill an experiment family early if:

- it only works before costs
- it needs zero slippage
- one asset contributes nearly all profits
- worst fold is catastrophic
- trade count collapses below useful levels
- hyperparameter sensitivity is extreme

### 16.16 Experiment Promotion Rules

Promote to shadow mode if:

- mean out-of-sample Sharpe > 0.8
- profit factor > 1.15
- worst fold is not structurally broken
- trade frequency exceeds current bot materially
- payoff asymmetry is improved

### 16.17 Feature-Set Progression Plan

| Feature set | Count | Composition |
|---|---:|---|
| `FS30` | 30 | returns + trend + vol + volume + BTC context |
| `FS45` | 45 | `FS30` + calendar + entropy + extra flow |
| `FS60` | 60 | `FS45` + more trend/vol variants |
| `FS80` | 80 | `FS60` + cross-sectional and derivatives placeholders |

### 16.18 Priority Ranking for Research Time

Spend time in this order:

1. data integrity
2. feature/live parity
3. walk-forward engine
4. LightGBM threshold and stop logic
5. slippage realism
6. ensemble
7. LSTM
8. RL

### 16.19 Documenting Negative Results

Always write down:

- what failed
- why it likely failed
- whether failure was cost-related, risk-related, or predictive-related
- whether the experiment should be retired or revisited later

### 16.20 One-Week Sprint Backlog

If you had one focused week, do:

Day 1:

- full data backfill
- QA scripts

Day 2:

- 30-feature builder
- label builder

Day 3:

- walk-forward splitter
- Ridge/ElasticNet baselines

Day 4:

- LightGBM and XGBoost baselines
- threshold sweep

Day 5:

- ATR stop sweep
- slippage scenarios

Day 6:

- result comparison
- choose shadow candidate

Day 7:

- deploy shadow pipeline

---

## 17. Appendix F: Production Runbooks and Alerts

### 17.1 Hourly Inference Runbook

Every 1h cycle should do this:

1. wait for the bar-close buffer
2. fetch latest closed bars for all active symbols
3. upsert bars
4. verify freshness
5. compute latest features
6. verify feature completeness
7. load active model
8. generate predictions
9. apply threshold policy
10. apply risk policy
11. generate orders or shadow decisions
12. persist every intermediate artifact

### 17.2 Daily Data Integrity Runbook

Daily job:

- scan for missing hourly intervals
- scan for duplicate intervals
- scan for invalid OHLC relationships
- compare latest timestamp against expected clock
- re-fetch repair windows
- summarize anomalies by symbol
- emit alert if any symbol remains broken

### 17.3 Weekly Retraining Runbook

Weekly job:

1. freeze a training cutoff timestamp
2. rebuild feature and label dataset to that cutoff
3. run data QA
4. run feature QA
5. train baseline models
6. run walk-forward evaluation
7. compare to current production model
8. save artifacts and metadata
9. nominate candidate for shadow or promotion

### 17.4 Model Promotion Runbook

Promote only after:

- candidate beats current model on agreed metrics
- candidate is not carried by one symbol only
- shadow-mode inference matches offline outputs
- alerting and rollback paths are ready
- artifact registry entry is complete

Promotion steps:

1. mark current model as `active_old`
2. mark candidate as `shadow_active`
3. run parallel for a fixed period if possible
4. switch active pointer
5. keep one-click rollback to prior model id

### 17.5 Incident Response Runbook

If live behavior looks wrong:

1. pause new entries
2. preserve logs
3. inspect latest data timestamps
4. inspect latest feature row
5. inspect prediction distribution
6. inspect recent fills and slippage
7. compare online feature row to offline recomputation
8. decide whether to roll back model or data pipeline

### 17.6 Suggested Alert List

Emit alerts for:

- no new bar for any symbol
- partial symbol update
- duplicate bars inserted
- feature pipeline failure
- model load failure
- prediction job failure
- prediction values all zeros
- prediction values exploding beyond normal range
- order rejection burst
- slippage spike
- drawdown breach
- trade frequency collapse

### 17.7 Alert Severity Levels

| Severity | Meaning | Example |
|---|---|---|
| `INFO` | expected operational note | retraining completed |
| `WARN` | degraded but not fatal | one symbol delayed by one bar |
| `ERROR` | workflow failed | feature generation failed |
| `CRITICAL` | trading should halt | stale data across symbols or DD kill switch |

### 17.8 Recommended Logging Payload for Each Inference

Log:

- timestamp
- symbol
- model id
- feature schema version
- prediction value
- threshold values
- resulting action
- size multiplier
- risk overrides triggered
- bar timestamp used

### 17.9 Drift Monitoring Rules

Feature drift alerts:

- z-score of feature mean shift beyond threshold
- z-score of feature std shift beyond threshold
- missing-value rate increase
- sudden collapse to constant values

Prediction drift alerts:

- rolling mean prediction shifts materially
- rolling std collapses
- class/threshold hit rate changes
- sign bias becomes extreme

### 17.10 Shadow Mode Evaluation Template

Track during shadow mode:

- predicted direction
- predicted magnitude
- would-enter flag
- would-exit flag
- actual next-bar return
- actual 6-bar outcome
- actual 24-bar outcome
- hypothetical PnL after costs
- differences vs rule-based strategy

### 17.11 Rollback Checklist

Rollback immediately if:

- live data is stale
- feature parity breaks
- live slippage is materially above modeled assumptions
- drawdown breaches hard limit
- predictions become obviously nonsensical
- order churn spikes unexpectedly

### 17.12 Recommended Config Flags

Expose config flags for:

- active model id
- shadow model id
- inference enabled
- live trading enabled
- risk override enabled
- max gross exposure
- max per-position risk
- slippage scenario
- threshold preset
- retraining schedule

### 17.13 Suggested Health Endpoints

Add health outputs for:

- latest raw kline timestamp by symbol
- latest feature timestamp by symbol
- active model metadata
- shadow model metadata
- recent prediction count
- recent order count
- drawdown state
- alert state

### 17.14 Minimal Retention Policy

Retain:

- raw bars indefinitely if storage allows
- feature rows at least as long as raw bars for reproducibility
- labels for all historical training windows
- model artifacts for every promoted model
- prediction logs for shadow and live modes
- trade decision logs

### 17.15 Scheduler Recommendation

For this backend:

- use a simple scheduled job aligned to candle close
- avoid minute-by-minute evaluation of the same 1h bar
- keep retraining out of the request/response path

### 17.16 Deployment Modes

| Mode | Behavior |
|---|---|
| `research` | offline dataset build, model training, no orders |
| `shadow` | online inference, no orders |
| `pilot` | limited-capital live orders |
| `active` | primary live model |
| `paused` | data and inference okay, no new orders |

### 17.17 Monitoring Dashboard Panels

Recommended panels:

- latest bar freshness
- latest feature freshness
- prediction histogram
- signal count by symbol
- live exposure by symbol
- live DD
- rolling Sharpe
- rolling PF
- realized slippage
- alert history

### 17.18 Production Readiness Checklist

Before enabling live ML:

1. all QA checks automated
2. shadow mode tested
3. rollback path tested
4. alerting tested
5. model registry enforced
6. fee/slippage assumptions reviewed
7. risk caps configured

---

## 18. Appendix G: Asset-Specific Notes for the Five-Symbol Universe

### 18.1 Why Asset-Specific Notes Matter

The five symbols are not interchangeable.

Even though they all trade on Binance spot and all use 1h bars:

- liquidity profiles differ
- volatility regimes differ
- dependence on BTC differs
- event risk differs

### 18.2 BTCUSDT

Use BTCUSDT as:

- a tradable asset
- the primary market-leader context series

Operational notes:

- most liquid in the universe
- lowest relative slippage assumption
- strongest macro-beta anchor
- good source for cross-asset relative features

Modeling notes:

- threshold can be slightly lower than smaller alts
- stop multipliers can often be tighter than for SOL/XRP in calm conditions

### 18.3 ETHUSDT

Use ETHUSDT as:

- second market-leader context series
- tradable asset with strong correlation to BTC but different regime expression

Operational notes:

- still very liquid
- often reacts differently in alt-led or DeFi-led regimes

Modeling notes:

- keep ETH context features for non-BTC assets
- ETH/BTC spread information can be useful later

### 18.4 SOLUSDT

Operational notes:

- higher volatility
- regime shifts faster than BTC/ETH
- likely needs wider stop assumptions
- can deliver more trades, but also more slippage sensitivity

Modeling notes:

- volatility and flow features likely matter more
- taker-buy ratios and abnormal volume may have more impact

### 18.5 BNBUSDT

Operational notes:

- structurally linked to Binance ecosystem dynamics
- often liquid and tradable
- may show exchange-specific behavior less transferable to other venues

Modeling notes:

- venue-aligned data is especially important
- cross-asset context with BTC and exchange-specific idiosyncrasy both matter

### 18.6 XRPUSDT

Operational notes:

- headline sensitivity can be abrupt
- can gap and trend hard on legal/regulatory news
- slippage assumptions should be more conservative than BTC/ETH

Modeling notes:

- volatility regime filters matter
- breakout and flow features may dominate mean-reversion features during event bursts

### 18.7 Suggested Slippage Buckets by Asset

| Symbol | Calm assumption | Stress assumption |
|---|---:|---:|
| BTCUSDT | `5` bps | `10` bps |
| ETHUSDT | `6` bps | `12` bps |
| BNBUSDT | `8` bps | `15` bps |
| SOLUSDT | `10` bps | `20` bps |
| XRPUSDT | `10` bps | `20` bps |

### 18.8 Suggested Stop Multipliers by Asset

| Symbol | ATR stop baseline |
|---|---:|
| BTCUSDT | `1.5x` to `2.0x` |
| ETHUSDT | `1.75x` to `2.25x` |
| BNBUSDT | `1.75x` to `2.25x` |
| SOLUSDT | `2.0x` to `2.75x` |
| XRPUSDT | `2.0x` to `2.75x` |

### 18.9 Suggested Threshold Bias by Asset

If trading each asset independently, start by testing:

| Symbol | Relative threshold |
|---|---|
| BTCUSDT | baseline |
| ETHUSDT | baseline |
| BNBUSDT | slightly above baseline |
| SOLUSDT | above baseline |
| XRPUSDT | above baseline |

Reason:

- smaller, noisier assets can generate more false positives from the same prediction scale

### 18.10 Cross-Asset Allocation Rules

Recommended starting rules:

- never allow full-size long on all five symbols just because all predicted returns are positive
- treat BTC and ETH as core beta
- treat SOL, BNB, XRP as higher-vol beta extensions
- reduce size when rolling correlation across the book spikes

### 18.11 Symbol-Level Failure Checks

Disable a symbol temporarily if:

- data freshness repeatedly fails for that symbol
- slippage assumptions are repeatedly violated
- its fold performance is persistently destructive
- exchange metadata changes or listing behavior becomes abnormal

### 18.12 Asset-Specific Conclusion

The first model can be pooled across symbols, but:

- thresholds
- stop multipliers
- sizing caps

should remain configurable per asset.

---

## 19. Appendix H: Detailed Module Contracts and Storage Design

### 19.1 Purpose

This appendix translates the earlier architecture recommendations into explicit module contracts.  
The goal is to reduce the chance that the first implementation becomes a pile of notebooks and one-off scripts.

### 19.2 `data_ingest.py`

Primary responsibilities:

- bootstrap historical klines from archive
- run REST incremental sync
- reconcile gaps
- produce integrity reports

Inputs:

- symbol list
- timeframe
- archive path or URL
- REST window parameters

Outputs:

- persisted raw `klines`
- ingestion logs
- data QA summary

Failure modes:

- archive file schema drift
- partial REST success
- duplicate upserts
- timezone normalization bugs

### 19.3 `feature_store.py`

Primary responsibilities:

- compute deterministic features from raw bars
- maintain feature schema version
- persist feature rows

Inputs:

- raw kline DataFrame
- optional cross-asset aligned series
- feature-set config

Outputs:

- `ml_features_1h`
- feature QA report

Failure modes:

- NaN explosion from denominator-zero cases
- broken joins for BTC/ETH context
- schema mismatch between train and live

### 19.4 `label_store.py`

Primary responsibilities:

- compute targets
- record label version and execution assumptions
- persist labels by symbol/time

Inputs:

- raw close series
- cost assumptions
- target config

Outputs:

- `ml_labels_1h`

Failure modes:

- off-by-one shifts
- future leakage
- changing execution assumptions without version bump

### 19.5 `dataset_builder.py`

Primary responsibilities:

- join features and labels
- drop unusable warmup rows
- enforce train/test cutoffs
- materialize model-ready matrices

Inputs:

- feature table
- label table
- split config

Outputs:

- `X_train`, `y_train`
- `X_valid`, `y_valid`
- `X_test`, `y_test`

Failure modes:

- train/test overlap
- inconsistent symbol coverage
- hidden NaNs entering model fit

### 19.6 `walkforward.py`

Primary responsibilities:

- define folds
- run training by fold
- aggregate metrics
- persist fold reports

Inputs:

- dataset builder
- model factory
- policy config

Outputs:

- fold-level metrics
- aggregated metrics
- comparison reports

Failure modes:

- leaking tuned parameters into evaluation
- inconsistent fold boundaries across symbols
- different cost assumptions between folds

### 19.7 `trainer.py`

Primary responsibilities:

- fit model
- store hyperparameters
- evaluate validation metrics
- export artifact

Inputs:

- model config
- training data
- validation data

Outputs:

- trained model artifact
- model metrics

Failure modes:

- seed instability
- silent parameter drift
- training on a different feature order than live inference

### 19.8 `registry.py`

Primary responsibilities:

- register model artifacts
- mark active/shadow states
- attach metadata
- support rollback

Inputs:

- artifact path
- metadata JSON
- metrics summary

Outputs:

- registry rows
- active model pointers

Failure modes:

- active model changed without audit trail
- artifact path missing
- stale registry pointers

### 19.9 `predictor.py`

Primary responsibilities:

- load active model
- validate live feature schema
- generate predictions
- persist prediction records

Inputs:

- latest feature rows
- model artifact
- feature schema hash

Outputs:

- `ml_predictions`

Failure modes:

- model/file load failure
- feature column mismatch
- all-null or constant predictions

### 19.10 `signal_policy.py`

Primary responsibilities:

- map predictions to entries/exits
- apply thresholds
- apply position sizing
- apply asset caps

Inputs:

- predictions
- threshold config
- risk config
- current portfolio state

Outputs:

- signal decisions
- candidate orders

Failure modes:

- repeated signals on same bar
- over-allocation under multiple simultaneous positives
- threshold changes not versioned

### 19.11 `monitoring.py`

Primary responsibilities:

- monitor freshness
- monitor drift
- monitor performance
- emit alerts

Inputs:

- latest data timestamps
- feature stats
- predictions
- realized trades

Outputs:

- health summaries
- alerts
- dashboards

Failure modes:

- stale data not detected
- drift detected but not actioned
- alert fatigue from noisy rules

### 19.12 Suggested Dependency Graph

```text
data_ingest -> feature_store -> label_store -> dataset_builder -> walkforward -> trainer -> registry
                                                               -> predictor -> signal_policy -> monitoring
```

### 19.13 Storage Design Principles

Follow these rules:

1. keep raw bars immutable after validated ingest
2. version every derived table
3. do not overwrite model metadata in place
4. treat feature schema as a first-class artifact
5. persist enough state to fully reproduce a promoted model

### 19.14 Suggested `ml_features_1h` Columns

| Column | Type | Notes |
|---|---|---|
| `symbol` | string | primary key part |
| `timeframe` | string | primary key part |
| `timestamp` | timestamp UTC | primary key part |
| `feature_set` | string | `FS30`, `FS45`, etc. |
| `schema_version` | string | explicit feature schema version |
| `ret_1h` | float | example feature |
| `ret_3h` | float | example feature |
| `ret_6h` | float | example feature |
| `rsi_2` | float | example feature |
| `rsi_14` | float | example feature |
| `adx_14` | float | example feature |
| `atr_pct` | float | example feature |
| `bb_width_20_2` | float | example feature |
| `volume_zscore_24` | float | example feature |
| `quote_volume_zscore` | float | example feature |
| `trades_count_zscore` | float | example feature |
| `taker_buy_base_ratio` | float | example feature |
| `btc_ret_1h` | float | example feature |
| `rolling_corr_btc_24` | float | example feature |
| `created_at` | timestamp UTC | audit |

### 19.15 Suggested `ml_labels_1h` Columns

| Column | Type | Notes |
|---|---|---|
| `symbol` | string | primary key part |
| `timeframe` | string | primary key part |
| `timestamp` | timestamp UTC | primary key part |
| `label_name` | string | e.g. `LOGRET_1H_V1` |
| `target_logret_1h` | float | primary regression target |
| `target_cls_edge_1h` | int | optional binary label |
| `cost_assumption_bps` | float | versioning aid |
| `execution_assumption` | string | next open / next bar |
| `created_at` | timestamp UTC | audit |

### 19.16 Suggested `ml_models` Columns

| Column | Type | Notes |
|---|---|---|
| `model_id` | string | unique id |
| `algorithm` | string | lightgbm/xgboost/ffn |
| `status` | string | candidate/shadow/active/retired |
| `artifact_path` | string | model file path |
| `feature_set` | string | feature-set id |
| `feature_hash` | string | order-sensitive hash |
| `label_name` | string | linked label definition |
| `train_start_ts` | timestamp UTC | training window |
| `train_end_ts` | timestamp UTC | training window |
| `test_scheme` | string | walk-forward summary |
| `metrics_json` | json/text | stored aggregate metrics |
| `params_json` | json/text | hyperparameters |
| `git_commit` | string | reproducibility |
| `package_versions` | json/text | reproducibility |
| `created_at` | timestamp UTC | audit |

### 19.17 Suggested `ml_training_runs` Columns

| Column | Type | Notes |
|---|---|---|
| `run_id` | string | unique id |
| `model_id` | string | FK-like link |
| `fold_id` | string | fold label |
| `train_start_ts` | timestamp UTC | fold start |
| `train_end_ts` | timestamp UTC | fold end |
| `test_start_ts` | timestamp UTC | fold start |
| `test_end_ts` | timestamp UTC | fold end |
| `sharpe` | float | fold metric |
| `profit_factor` | float | fold metric |
| `max_drawdown` | float | fold metric |
| `trade_count` | int | fold metric |
| `notes` | text | anomaly notes |

### 19.18 Suggested `ml_predictions` Columns

| Column | Type | Notes |
|---|---|---|
| `model_id` | string | model source |
| `symbol` | string | asset |
| `timestamp` | timestamp UTC | feature bar timestamp |
| `prediction` | float | regression output |
| `threshold_entry` | float | policy used |
| `threshold_exit` | float | policy used |
| `would_enter` | bool | policy outcome |
| `would_exit` | bool | policy outcome |
| `mode` | string | research/shadow/live |
| `created_at` | timestamp UTC | audit |

### 19.19 Suggested `ml_signal_decisions` Columns

| Column | Type | Notes |
|---|---|---|
| `decision_id` | string | unique id |
| `model_id` | string | origin model |
| `symbol` | string | asset |
| `timestamp` | timestamp UTC | decision timestamp |
| `signal_type` | string | enter/exit/hold/reduce |
| `prediction` | float | source prediction |
| `size_multiplier` | float | post-risk sizing |
| `risk_overrides` | json/text | caps triggered |
| `reason` | text | threshold / stop / regime note |

### 19.20 Suggested `ml_live_metrics` Columns

| Column | Type | Notes |
|---|---|---|
| `timestamp` | timestamp UTC | metric timestamp |
| `model_id` | string | active model |
| `rolling_sharpe_7d` | float | monitoring |
| `rolling_pf_7d` | float | monitoring |
| `rolling_dd_7d` | float | monitoring |
| `trade_count_7d` | int | monitoring |
| `mean_prediction_7d` | float | drift |
| `std_prediction_7d` | float | drift |
| `mean_slippage_7d_bps` | float | execution realism |
| `alert_state` | string | healthy/warn/critical |

### 19.21 Artifact Directory Layout

Recommended structure:

```text
backend/artifacts/
  ml/
    models/
      lgbm_1h_v001.pkl
      xgb_1h_v001.json
      ffn_1h_v001.pt
    reports/
      lgbm_1h_v001/
        folds.csv
        summary.json
        shap_summary.png
        config.json
    datasets/
      snapshots/
        2026-03-18_fs30_logret1h.parquet
```

### 19.22 Config Separation Recommendation

Keep these config files separate:

- `data.yml`
- `features.yml`
- `labels.yml`
- `models.yml`
- `policy.yml`
- `risk.yml`
- `alerts.yml`

### 19.23 Interface Rule: No Hidden Global State

Every module should accept explicit inputs and return explicit outputs.  
Avoid:

- hidden mutable globals
- random seeds set in scattered files
- untracked default thresholds
- implicit feature column order

### 19.24 Interface Rule: Online and Offline Parity

The same feature function must power:

- training datasets
- backtests
- shadow mode
- live mode

Any divergence here destroys trust in the research loop.

### 19.25 Storage Design Conclusion

The simplest robust design is:

- raw immutable bars
- explicit feature/label tables
- strict model registry
- full prediction logging

That is enough to support disciplined iteration without building a heavy MLOps platform.

---

## 20. Appendix I: Metrics, Diagnostics, and Reporting Templates

### 20.1 Why Reporting Quality Matters

A model that looks good in one chart can still be unusable.  
The report layer has to make failure visible.

### 20.2 Core Strategy Metrics

| Metric | Formula / description | Why it matters |
|---|---|---|
| Sharpe | mean excess return / std return | overall risk-adjusted performance |
| Sortino | mean excess return / downside std | penalizes downside more directly |
| Profit factor | gross profit / gross loss | simple expectancy proxy |
| CAGR or annualized return | compounded return rate | useful but secondary |
| Max drawdown | peak-to-trough decline | capital pain and survivability |
| Calmar | CAGR / max drawdown | return efficiency relative to DD |
| Win rate | winning trades / all trades | weak alone, useful in context |
| Average win | mean positive trade return | payoff side |
| Average loss | mean negative trade return | pain side |
| Payoff ratio | avg win / avg loss | directly addresses your current issue |
| Expectancy per trade | mean trade return | core trade economics |
| Turnover | gross traded notional over capital | cost sensitivity |
| Exposure | fraction of time in market | helps interpret Sharpe |
| Trade count | total trades | checks whether system is too sparse |
| Avg holding time | mean bars per trade | strategy style indicator |
| Slippage-adjusted edge | edge after execution assumptions | realism check |
| Hit rate by symbol | win rate split by symbol | checks overfitting concentration |
| Fold stability | dispersion across folds | robustness |
| Live-vs-backtest drift | performance difference online vs offline | production realism |
| Cost sensitivity | metric delta under worse fees/slippage | robustness test |

### 20.3 Prediction Metrics

For regression models, also track:

| Metric | Why it matters |
|---|---|
| RMSE | basic forecast error |
| MAE | robust absolute error |
| Spearman correlation | ranking quality of predictions |
| Pearson correlation | linear return correlation |
| directional accuracy | sign hit rate |
| top-decile return | quality of strongest signals |
| bottom-decile return | quality of weakest signals |
| calibration by prediction bucket | whether stronger forecasts really mean stronger outcomes |

### 20.4 Minimum Fold Report Table

| Column | Description |
|---|---|
| `fold_id` | fold name |
| `train_start` | train start |
| `train_end` | train end |
| `test_start` | test start |
| `test_end` | test end |
| `algorithm` | model family |
| `feature_set` | feature schema |
| `entry_threshold` | policy threshold |
| `stop_type` | stop logic |
| `sharpe` | fold Sharpe |
| `profit_factor` | fold PF |
| `max_drawdown` | fold DD |
| `trade_count` | fold trades |
| `avg_win` | fold avg win |
| `avg_loss` | fold avg loss |
| `payoff_ratio` | fold avg win/avg loss |
| `notes` | anomalies |

### 20.5 Symbol-Level Report Table

| Column | Description |
|---|---|
| `symbol` | asset |
| `sharpe` | symbol-only strategy Sharpe |
| `profit_factor` | symbol PF |
| `trade_count` | symbol trades |
| `avg_hold_bars` | holding time |
| `slippage_assumption_bps` | used assumption |
| `avg_prediction` | mean prediction |
| `std_prediction` | dispersion |
| `best_fold` | strongest fold |
| `worst_fold` | weakest fold |

### 20.6 Portfolio-Level Report Table

| Column | Description |
|---|---|
| `model_id` | active model |
| `period` | reporting period |
| `portfolio_sharpe` | aggregated Sharpe |
| `portfolio_pf` | aggregated PF |
| `portfolio_dd` | aggregated DD |
| `gross_exposure_mean` | average gross exposure |
| `net_exposure_mean` | average net exposure |
| `trade_count_total` | total trades |
| `trades_per_month` | turnover rate |
| `return_contribution_by_symbol` | concentration view |

### 20.7 Recommended Result Views

Every serious experiment should output:

1. fold-by-fold metric table
2. portfolio equity curve
3. drawdown curve
4. return histogram
5. trade return histogram
6. rolling Sharpe chart
7. prediction bucket chart
8. feature-importance chart
9. symbol contribution chart
10. slippage sensitivity table

### 20.8 Diagnostic Questions for Poor Results

Ask:

1. Is the model actually predicting returns, or just activity regimes?
2. Is the threshold too low?
3. Are costs killing otherwise real but small edge?
4. Is one symbol degrading the basket?
5. Is the model overtrading during chop?
6. Are stops too wide?
7. Are exits too slow?
8. Is training memory too long or too short?
9. Are cross-asset features helping or hurting?
10. Are entropy features adding value or noise?

### 20.9 Diagnostic Table: What Bad Metrics Usually Mean

| Pattern | Likely cause | First action |
|---|---|---|
| high hit rate, bad PF | losses too large | tighten stop / improve exits |
| good pre-cost Sharpe, bad post-cost Sharpe | overtrading | raise threshold |
| good mean Sharpe, terrible worst fold | instability | reduce complexity / improve regime control |
| high return concentration in one symbol | universe imbalance | add symbol caps |
| live trade count far above backtest | parity bug | compare online/offline signals |
| prediction std collapses | stale features or model drift | inspect feature pipeline |
| very few trades | threshold too high or model too conservative | lower threshold / adjust objective |
| lots of trades, poor expectancy | no edge or no cost discipline | tighten threshold and stop logic |

### 20.10 Calibration Report Template

Bucket predictions into deciles or quantiles and report:

| Bucket | Mean prediction | Mean realized return | Trade count |
|---|---:|---:|---:|
| Q1 |  |  |  |
| Q2 |  |  |  |
| Q3 |  |  |  |
| Q4 |  |  |  |
| Q5 |  |  |  |
| Q6 |  |  |  |
| Q7 |  |  |  |
| Q8 |  |  |  |
| Q9 |  |  |  |
| Q10 |  |  |  |

Desired pattern:

- realized returns should increase with prediction bucket

### 20.11 Slippage Sensitivity Template

| Scenario | Sharpe | PF | DD | Trades |
|---|---:|---:|---:|---:|
| fee 10bps, slip 5bps |  |  |  |  |
| fee 10bps, slip 8bps |  |  |  |  |
| fee 10bps, slip 12bps |  |  |  |  |
| fee 10bps, slip 20bps |  |  |  |  |

Required interpretation:

- if strategy dies immediately as slippage rises modestly, it is too fragile

### 20.12 Threshold Sensitivity Template

| Entry threshold | Sharpe | PF | Trades | Avg hold |
|---:|---:|---:|---:|---:|
| 0.0000 |  |  |  |  |
| 0.0003 |  |  |  |  |
| 0.0005 |  |  |  |  |
| 0.0008 |  |  |  |  |
| 0.0010 |  |  |  |  |
| 0.0015 |  |  |  |  |

### 20.13 Stop-Loss Sensitivity Template

| Stop config | Sharpe | PF | DD | Trades |
|---|---:|---:|---:|---:|
| none |  |  |  |  |
| ATR 1.5x |  |  |  |  |
| ATR 2.0x |  |  |  |  |
| ATR 2.5x |  |  |  |  |
| chandelier 2.5x |  |  |  |  |
| time stop 24 bars |  |  |  |  |

### 20.14 Feature Ablation Template

| Experiment | Removed feature block | Sharpe delta | PF delta | Interpretation |
|---|---|---:|---:|---|
| A | volume/flow |  |  |  |
| B | cross-asset |  |  |  |
| C | trend |  |  |  |
| D | volatility |  |  |  |
| E | entropy |  |  |  |
| F | calendar |  |  |  |

### 20.15 Model Comparison Template

| Model | Feature set | Sharpe | PF | DD | Trades | Notes |
|---|---|---:|---:|---:|---:|---|
| Ridge | FS30 |  |  |  |  |  |
| ElasticNet | FS30 |  |  |  |  |  |
| RF | FS30 |  |  |  |  |  |
| LGBM | FS30 |  |  |  |  |  |
| XGB | FS30 |  |  |  |  |  |
| LGBM | FS60 |  |  |  |  |  |
| FFN | FS30 |  |  |  |  |  |
| Ensemble | FS30 |  |  |  |  |  |

### 20.16 Shadow Mode Report Template

| Date | Symbol | Prediction | Would trade? | Actual next 1h | Actual next 6h | Comment |
|---|---|---:|---|---:|---:|---|
|  |  |  |  |  |  |  |

### 20.17 Live Monitoring Summary Template

| Metric | Last 24h | Last 7d | Threshold | Status |
|---|---:|---:|---:|---|
| data freshness lag |  |  |  |  |
| feature freshness lag |  |  |  |  |
| trade count |  |  |  |  |
| rolling PF |  |  |  |  |
| rolling DD |  |  |  |  |
| mean slippage |  |  |  |  |
| alert count |  |  |  |  |

### 20.18 Promotion Memo Template

When promoting a model, write:

1. what changed
2. why it changed
3. which metrics improved
4. which risks remain
5. rollback criteria

### 20.19 Retirement Memo Template

When retiring a model, write:

1. what failed
2. when the failure started
3. whether it was data, execution, or model quality
4. whether the model should be archived or revisited

### 20.20 Monthly Research Review Template

Summarize:

- winning experiments
- losing experiments
- top feature groups
- top failure modes
- cost realism updates
- shadow/live parity issues
- next month priorities

### 20.21 Minimum Dashboard KPIs

Display:

- active model id
- shadow model id
- latest data timestamp
- latest prediction timestamp
- rolling 7d Sharpe
- rolling 7d PF
- rolling DD
- trade count
- realized slippage
- alert status

### 20.22 Recommended Interpretation Order

Read results in this order:

1. data validity
2. costs included
3. worst fold
4. drawdown
5. profit factor
6. trade count
7. feature importance
8. only then mean Sharpe

### 20.23 Reporting Conclusion

The report layer should force you to answer:

- is the signal real
- is the strategy tradable
- is the risk acceptable
- is the result stable

If the answer to any of those is unclear, the model is not ready.

---

## Final Recommendation Snapshot

If this report is distilled into one implementation plan, it is:

1. Backfill Binance archive history for all five pairs
2. Build a persisted 30-feature v1 feature store
3. Train LightGBM on next-bar log return with walk-forward windows
4. Convert predictions into trades with thresholding, ATR stops, and volatility-scaled sizing
5. Backtest through the existing `vectorbt`-enabled backtester
6. Run shadow mode
7. Add XGBoost and FFN for ensemble improvements

That path is the highest-probability way to turn the current rule-based system into a researchable ML trading bot without unnecessary platform churn.
