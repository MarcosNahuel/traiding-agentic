# Taxonomia SSRN 3247865 (151+ Estrategias)

Fuente base: `docs/algoritmos/ssrn-3247865.pdf` (Kakushadze & Serur, 2018).

Este inventario se usa como universo de estrategias para el agente de codificacion y para priorizar implementacion en BTC/Binance Spot/Futures.

## Resumen

- Estrategias detectadas en tabla de contenidos: **174** (incluye sub-variantes listadas en el indice del PDF).
- Criterio de priorizacion: `Alta` (aplicacion directa a BTC/Binance), `Media` (adaptable), `Baja` (fuera de foco operativo actual).

## Cobertura Por Seccion

| Seccion | Cantidad | Aplicabilidad Base |
|---|---:|---|
| Options | 58 | Media |
| Stocks | 21 | Media |
| ETFs | 8 | Baja |
| Fixed Income | 15 | Baja |
| Indexes | 5 | Media |
| Volatility | 7 | Media |
| FX | 6 | Media |
| Commodities | 6 | Media |
| Futures | 7 | Alta |
| Structured Assets | 6 | Baja |
| Convertibles | 2 | Baja |
| Tax Arbitrage | 3 | Baja |
| Misc Assets | 4 | Baja |
| Distressed Assets | 7 | Baja |
| Real Estate | 8 | Baja |
| Cash | 5 | Baja |
| Cryptocurrencies | 2 | Alta |
| Global Macro | 4 | Media |

## Inventario Completo

| Seccion SSRN | Codigo | Estrategia | Aplicabilidad BTC/Binance | Nota de Adaptacion |
|---|---|---|---|---|
| Options | 2.2 | Covered call | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.3 | Covered put | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.4 | Protective put | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.5 | Protective call | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.6 | Bull call spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.7 | Bull put spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.8 | Bear call spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.9 | Bear put spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.10 | Long synthetic forward | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.11 | Short synthetic forward | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.12 | Long combo | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.13 | Short combo | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.14 | Bull call ladder | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.15 | Bull put ladder | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.16 | Bear call ladder | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.17 | Bear put ladder | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.18 | Calendar call spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.19 | Calendar put spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.20 | Diagonal call spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.21 | Diagonal put spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.22 | Long straddle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.23 | Long strangle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.24 | Long guts | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.25 | Short straddle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.26 | Short strangle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.27 | Short guts | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.28 | Long call synthetic straddle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.29 | Long put synthetic straddle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.30 | Short call synthetic straddle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.31 | Short put synthetic straddle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.32 | Covered short straddle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.33 | Covered short strangle | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.34 | Strap | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.35 | Strip | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.36 | Call ratio backspread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.37 | Put ratio backspread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.38 | Ratio call spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.39 | Ratio put spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.40 | Long call buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.40.1 | Modied call buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.41 | Long put buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.41.1 | Modied put buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.42 | Short call buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.43 | Short put buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.44 | Long iron buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.45 | Short iron buttery | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.46 | Long call condor | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.47 | Long put condor | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.48 | Short call condor | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.49 | Short put condor | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.50 | Long iron condor | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.51 | Short iron condor | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.52 | Long box | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.53 | Collar | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.54 | Bullish short seagull spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.55 | Bearish long seagull spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.56 | Bearish short seagull spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Options | 2.57 | Bullish long seagull spread | Media | Aplicable en derivados/opciones; complejidad y liquidez variable por instrumento. |
| Stocks | 3.1 | Price-momentum | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.2 | Earnings-momentum | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.3 | Value | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.4 | Low-volatility anomaly | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.5 | Implied volatility | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.6 | Multifactor portfolio | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.7 | Residual momentum | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.8 | Pairs trading | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.9 | Mean-reversion single cluster | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.9.1 | Mean-reversion multiple clusters | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.10 | Mean-reversion weighted regression | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.11 | Single moving average | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.12 | Two moving averages | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.13 | Three moving averages | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.14 | Support and resistance | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.15 | Channel | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.16 | Event-driven M&A | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.17 | Machine learning single-stock KNN | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.18 | Statistical arbitrage optimization | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.19 | Market-making | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| Stocks | 3.20 | Alpha combos | Media | Las estrategias cuantitativas son transferibles si se recalibran para cripto 24/7. |
| ETFs | 4.1 | Sector momentum rotation | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| ETFs | 4.1.1 | Sector momentum rotation with MA lter | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| ETFs | 4.1.2 | Dual-momentum sector rotation | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| ETFs | 4.2 | Alpha rotation | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| ETFs | 4.3 | R-squared | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| ETFs | 4.4 | Mean-reversion | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| ETFs | 4.5 | Leveraged ETFs (LETFs) | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| ETFs | 4.6 | Multi-asset trend following | Baja | Dise?adas para ETFs; solo conceptos transferibles (rotation, trend, mean reversion). |
| Fixed Income | 5.2 | Bullets | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.3 | Barbells | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.4 | Ladders | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.5 | Bond immunization | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.6 | Dollar-duration-neutral buttery | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.7 | Fifty-fty buttery | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.8 | Regression-weighted buttery | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.8.1 | Maturity-weighted buttery | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.9 | Low-risk factor | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.10 | Value factor | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.11 | Carry factor | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.12 | Rolling down the yield curve | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.13 | Yield curve spread (atteners & steepeners) | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.14 | CDS basis arbitrage | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Fixed Income | 5.15 | Swap-spread arbitrage | Baja | Generalmente no aplica directo a BTC spot/futures. |
| Indexes | 6.2 | Cash-and-carry arbitrage | Media | Arbitraje y vol-targeting son adaptables a cestas/perps crypto. |
| Indexes | 6.3 | Dispersion trading in equity indexes | Media | Arbitraje y vol-targeting son adaptables a cestas/perps crypto. |
| Indexes | 6.3.1 | Dispersion trading subset portfolio | Media | Arbitraje y vol-targeting son adaptables a cestas/perps crypto. |
| Indexes | 6.4 | Intraday arbitrage between index ETFs | Media | Arbitraje y vol-targeting son adaptables a cestas/perps crypto. |
| Indexes | 6.5 | Index volatility targeting with risk-free asset | Media | Arbitraje y vol-targeting son adaptables a cestas/perps crypto. |
| Volatility | 7.2 | VIX futures basis trading | Media | Requiere acceso a derivados de volatilidad/opciones. |
| Volatility | 7.3 | Volatility carry with two ETNs | Media | Requiere acceso a derivados de volatilidad/opciones. |
| Volatility | 7.3.1 | Hedging short VXX with VIX futures | Media | Requiere acceso a derivados de volatilidad/opciones. |
| Volatility | 7.4 | Volatility risk premium | Media | Requiere acceso a derivados de volatilidad/opciones. |
| Volatility | 7.4.1 | Volatility risk premium with Gamma hedging | Media | Requiere acceso a derivados de volatilidad/opciones. |
| Volatility | 7.5 | Volatility skew long risk reversal | Media | Requiere acceso a derivados de volatilidad/opciones. |
| Volatility | 7.6 | Volatility trading with variance swaps | Media | Requiere acceso a derivados de volatilidad/opciones. |
| FX | 8.1 | Moving averages with HP lter | Media | Carry/arbitraje son adaptables a pares crypto y stablecoins. |
| FX | 8.2 | Carry trade | Media | Carry/arbitraje son adaptables a pares crypto y stablecoins. |
| FX | 8.2.1 | High-minus-low carry | Media | Carry/arbitraje son adaptables a pares crypto y stablecoins. |
| FX | 8.3 | Dollar carry trade | Media | Carry/arbitraje son adaptables a pares crypto y stablecoins. |
| FX | 8.4 | Momentum & carry combo | Media | Carry/arbitraje son adaptables a pares crypto y stablecoins. |
| FX | 8.5 | FX triangular arbitrage | Media | Carry/arbitraje son adaptables a pares crypto y stablecoins. |
| Commodities | 9.1 | Roll yields | Media | Trend/carry/value se puede adaptar a futuros crypto. |
| Commodities | 9.2 | Trading based on hedging pressure | Media | Trend/carry/value se puede adaptar a futuros crypto. |
| Commodities | 9.3 | Portfolio diversication with commodities | Media | Trend/carry/value se puede adaptar a futuros crypto. |
| Commodities | 9.4 | Value | Media | Trend/carry/value se puede adaptar a futuros crypto. |
| Commodities | 9.5 | Skewness premium | Media | Trend/carry/value se puede adaptar a futuros crypto. |
| Commodities | 9.6 | Trading with pricing models | Media | Trend/carry/value se puede adaptar a futuros crypto. |
| Futures | 10.1 | Hedging risk with futures | Alta | Aplicaci?n directa a Binance Futures (trend, calendar, contrarian). |
| Futures | 10.1.1 | Cross-hedging | Alta | Aplicaci?n directa a Binance Futures (trend, calendar, contrarian). |
| Futures | 10.1.2 | Interest rate risk hedging | Alta | Aplicaci?n directa a Binance Futures (trend, calendar, contrarian). |
| Futures | 10.2 | Calendar spread | Alta | Aplicaci?n directa a Binance Futures (trend, calendar, contrarian). |
| Futures | 10.3 | Contrarian trading (mean-reversion) | Alta | Aplicaci?n directa a Binance Futures (trend, calendar, contrarian). |
| Futures | 10.3.1 | Contrarian trading market activity | Alta | Aplicaci?n directa a Binance Futures (trend, calendar, contrarian). |
| Futures | 10.4 | Trend following (momentum) | Alta | Aplicaci?n directa a Binance Futures (trend, calendar, contrarian). |
| Structured Assets | 11.2 | Carry, equity tranche index hedging | Baja | No es foco para trading BTC en Binance. |
| Structured Assets | 11.3 | Carry, senior/mezzanine index hedging | Baja | No es foco para trading BTC en Binance. |
| Structured Assets | 11.4 | Carry tranche hedging | Baja | No es foco para trading BTC en Binance. |
| Structured Assets | 11.5 | Carry CDS hedging | Baja | No es foco para trading BTC en Binance. |
| Structured Assets | 11.6 | CDOs curve trades | Baja | No es foco para trading BTC en Binance. |
| Structured Assets | 11.7 | Mortgage-backed security (MBS) trading | Baja | No es foco para trading BTC en Binance. |
| Convertibles | 12.1 | Convertible arbitrage | Baja | No aplica de forma directa en Binance crypto. |
| Convertibles | 12.2 | Convertible option-adjusted spread | Baja | No aplica de forma directa en Binance crypto. |
| Tax Arbitrage | 13.1 | Municipal bond tax arbitrage | Baja | M?s relevante para estructuraci?n legal/fiscal que para se?al de trading. |
| Tax Arbitrage | 13.2 | Cross-border tax arbitrage | Baja | M?s relevante para estructuraci?n legal/fiscal que para se?al de trading. |
| Tax Arbitrage | 13.2.1 | Cross-border tax arbitrage with options | Baja | M?s relevante para estructuraci?n legal/fiscal que para se?al de trading. |
| Misc Assets | 14.1 | Ination hedging ination swaps | Baja | Fuera del scope principal BTC/Binance. |
| Misc Assets | 14.2 | TIPS-Treasury arbitrage | Baja | Fuera del scope principal BTC/Binance. |
| Misc Assets | 14.3 | Weather risk demand hedging | Baja | Fuera del scope principal BTC/Binance. |
| Misc Assets | 14.4 | Energy spark spread | Baja | Fuera del scope principal BTC/Binance. |
| Distressed Assets | 15.1 | Buying and holding distressed debt | Baja | No aplica al core de BTC spot/futures. |
| Distressed Assets | 15.2 | Active distressed investing | Baja | No aplica al core de BTC spot/futures. |
| Distressed Assets | 15.2.1 | Planning a reorganization | Baja | No aplica al core de BTC spot/futures. |
| Distressed Assets | 15.2.2 | Buying outstanding debt | Baja | No aplica al core de BTC spot/futures. |
| Distressed Assets | 15.2.3 | Loan-to-own | Baja | No aplica al core de BTC spot/futures. |
| Distressed Assets | 15.3 | Distress risk puzzle | Baja | No aplica al core de BTC spot/futures. |
| Distressed Assets | 15.3.1 | Distress risk puzzle risk management | Baja | No aplica al core de BTC spot/futures. |
| Real Estate | 16.2 | Mixed-asset diversication with real estate | Baja | Fuera de universo de instrumentos del proyecto. |
| Real Estate | 16.3 | Intra-asset diversication within real estate | Baja | Fuera de universo de instrumentos del proyecto. |
| Real Estate | 16.3.1 | Property type diversication | Baja | Fuera de universo de instrumentos del proyecto. |
| Real Estate | 16.3.2 | Economic diversication | Baja | Fuera de universo de instrumentos del proyecto. |
| Real Estate | 16.3.3 | Property type and geographic diversication | Baja | Fuera de universo de instrumentos del proyecto. |
| Real Estate | 16.4 | Real estate momentum regional approach | Baja | Fuera de universo de instrumentos del proyecto. |
| Real Estate | 16.5 | Ination hedging with real estate | Baja | Fuera de universo de instrumentos del proyecto. |
| Real Estate | 16.6 | Fix-and-ip | Baja | Fuera de universo de instrumentos del proyecto. |
| Cash | 17.2 | Money laundering the dark side of cash | Baja | Mayormente no trading sistem?tico de BTC. |
| Cash | 17.3 | Liquidity management | Baja | Mayormente no trading sistem?tico de BTC. |
| Cash | 17.4 | Repurchase agreement (REPO) | Baja | Mayormente no trading sistem?tico de BTC. |
| Cash | 17.5 | Pawnbroking | Baja | Mayormente no trading sistem?tico de BTC. |
| Cash | 17.6 | Loan sharking | Baja | Mayormente no trading sistem?tico de BTC. |
| Cryptocurrencies | 18.2 | Articial neural network (ANN) | Alta | Dise?adas expl?citamente para BTC/crypto. |
| Cryptocurrencies | 18.3 | Sentiment analysis nave Bayes Bernoulli | Alta | Dise?adas expl?citamente para BTC/crypto. |
| Global Macro | 19.2 | Fundamental macro momentum | Media | ?til para filtros de r?gimen y eventos, no como se?al ?nica. |
| Global Macro | 19.3 | Global macro ination hedge | Media | ?til para filtros de r?gimen y eventos, no como se?al ?nica. |
| Global Macro | 19.4 | Global xed-income strategy | Media | ?til para filtros de r?gimen y eventos, no como se?al ?nica. |
| Global Macro | 19.5 | Trading on economic announcements | Media | ?til para filtros de r?gimen y eventos, no como se?al ?nica. |