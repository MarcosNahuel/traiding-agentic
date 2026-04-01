# Directorio de Fuentes Academicas y de Investigacion

**Fecha:** 2026-03-30
**Objetivo:** Catálogo autoritativo de fuentes para alimentar el pipeline de investigación del Source Agent

---

## A) Repositorios de Papers y Preprint Servers

### 1. arXiv — Quantitative Finance (q-fin)

**URL principal:** https://arxiv.org/archive/q-fin
**Tipo:** Preprint server abierto (sin peer review, pero estándar de facto en quant finance)
**Frecuencia:** Diaria (nuevos papers cada día hábil)
**Acceso:** Gratuito, sin registro. URLs directas por categoría.

**Subcategorías relevantes para el proyecto:**

| Categoría | URL | Contenido |
|-----------|-----|-----------|
| **q-fin.TR** | https://arxiv.org/list/q-fin.TR/recent | Trading and Market Microstructure — market making, automated trading, agent-based modeling, auction design |
| **q-fin.CP** | https://arxiv.org/list/q-fin.CP/recent | Computational Finance — Monte Carlo, PDE, métodos numéricos aplicados a finanzas |
| **q-fin.ST** | https://arxiv.org/list/q-fin.ST/recent | Statistical Finance — econometría, econofísica, análisis estadístico de mercados |
| **q-fin.PM** | https://arxiv.org/list/q-fin.PM/recent | Portfolio Management — selección de activos, optimización, estrategias de inversión |
| **q-fin.RM** | https://arxiv.org/list/q-fin.RM/recent | Risk Management — medición y gestión de riesgos financieros |
| **q-fin.MF** | https://arxiv.org/list/q-fin.MF/recent | Mathematical Finance — métodos estocásticos, probabilísticos, algebraicos |
| **q-fin.PR** | https://arxiv.org/list/q-fin.PR/recent | Pricing of Securities — valuación y hedging de derivados |
| **q-fin.GN** | https://arxiv.org/list/q-fin.GN/recent | General Finance — metodologías cuantitativas generales |

**Categorías cruzadas también relevantes:**

| Categoría | URL | Contenido |
|-----------|-----|-----------|
| **cs.LG** | https://arxiv.org/list/cs.LG/recent | Machine Learning — muchos papers de ML aplicado a trading |
| **cs.AI** | https://arxiv.org/list/cs.AI/recent | Artificial Intelligence — agentes AI, LLMs en finanzas |
| **cs.CE** | https://arxiv.org/list/cs.CE/recent | Computational Engineering/Finance — métodos computacionales |
| **stat.ML** | https://arxiv.org/list/stat.ML/recent | Machine Learning (estadístico) |

**Feed RSS:** https://arxiv.org/rss/q-fin (todas las subcategorías)
**API:** https://info.arxiv.org/help/api/index.html (búsqueda programática)

---

### 2. SSRN (Social Science Research Network)

**URL principal:** https://www.ssrn.com/
**Tipo:** Repositorio de working papers (pre y post peer review)
**Frecuencia:** Diaria (miles de papers nuevos por mes)
**Acceso:** Gratuito para lectura. Requiere cuenta gratuita para descargas.

**Redes y hubs relevantes:**

| Hub/Red | URL | Contenido |
|---------|-----|-----------|
| **Cryptocurrency Research Hub** | https://www.ssrn.com/index.cfm/en/cryptocurrency/ | Hub interdisciplinario: tecnología, regulación, mercados crypto |
| **FEN (Financial Economics Network)** | https://www.ssrn.com/index.cfm/en/fen/ | Red principal de economía financiera |
| **Capital Markets: Asset Pricing** | Dentro de FEN | Valoración de activos, modelos de factores |
| **Capital Markets: Market Efficiency** | Dentro de FEN | Eficiencia de mercado, anomalías |
| **Quantitative Methods eJournal** | Dentro de FEN | Métodos cuantitativos en inversión |

**Papers fundamentales ya en nuestro pipeline:**
- Kakushadze & Serur — 151 Trading Strategies: https://ssrn.com/abstract=3247865
- Avellaneda-Stoikov — HFT in Limit Order Book: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1416153

**Blog SSRN (curación):** https://blog.ssrn.com/ — publica resúmenes temáticos regulares (ej: "The Latest Research on Cryptocurrency", Feb 2026)

---

### 3. NBER (National Bureau of Economic Research)

**URL principal:** https://www.nber.org/papers
**Tipo:** Working papers de economistas de élite (Harvard, MIT, Chicago, Columbia)
**Frecuencia:** Semanal (~50-80 papers nuevos por semana)
**Acceso:** Abstracts gratuitos. Papers completos requieren suscripción o acceso institucional (muchos disponibles vía Google Scholar).

**Papers crypto/fintech relevantes:**
- Cryptocurrencies and DeFi: https://www.nber.org/system/files/working_papers/w30006/w30006.pdf
- Stablecoins: https://www.nber.org/system/files/working_papers/w34475/w34475.pdf
- Who Invests in Crypto?: https://www.nber.org/system/files/working_papers/w31856/w31856.pdf
- Risks and Returns of Cryptocurrency: https://www.nber.org/system/files/working_papers/w24877/w24877.pdf
- CBDC: https://www.nber.org/system/files/working_papers/w23711/w23711.pdf
- Simple Economics of the Blockchain: https://www.nber.org/system/files/working_papers/w22952/w22952.pdf

---

### 4. RePEc / IDEAS

**URL principal:** https://ideas.repec.org/
**Tipo:** Base de datos bibliográfica descentralizada de economía (>3.8M papers)
**Frecuencia:** Continua
**Acceso:** Gratuito, indexa papers de múltiples fuentes

---

### 5. OpenAlex

**URL:** https://openalex.org/
**API:** https://developers.openalex.org/
**Tipo:** Catálogo abierto de 250M+ trabajos académicos (reemplazo de Microsoft Academic Graph)
**Acceso:** API gratuita sin key, límite 100K calls/día
**Uso para el bot:** Búsqueda programática de papers por tema, citaciones, autores

---

### 6. Semantic Scholar

**URL:** https://www.semanticscholar.org/
**API:** https://api.semanticscholar.org/
**Tipo:** Motor de búsqueda académico con AI (~200M papers)
**Acceso:** API gratuita (100 req/5 min sin key, más con key gratuita)
**Uso para el bot:** Búsqueda semántica, grafos de citación, papers relacionados

---

## B) Reportes Institucionales (Acceso Gratuito)

### Exchanges y Gestoras Crypto

| Fuente | URL | Contenido | Frecuencia | Acceso |
|--------|-----|-----------|------------|--------|
| **Binance Research** | https://research.binance.com/en/analysis | Análisis de mercado, reportes semestrales, market insights | Mensual + reportes especiales | Gratuito, sin registro |
| **Binance Research — Projects** | https://research.binance.com/en/projects | Due diligence de proyectos crypto | Continuo | Gratuito |
| **Grayscale Research** | https://research.grayscale.com/reports | Outlook anual, sector reports, market commentary | Trimestral + especiales | Gratuito, descarga directa |
| **Messari Research** | https://messari.io/research | Crypto Theses anuales, sector reports, protocol analysis | Continuo (algunos premium) | Parcial gratuito (Crypto Theses gratis, reportes avanzados requieren suscripción) |
| **Delphi Digital** | https://delphidigital.io/ | Year Ahead reports, DeFi/infra/macro analysis | Continuo (premium) | Parcial gratuito (Year Ahead gratis, investigación profunda requiere Delphi Pro) |

### Bancos Centrales y Organismos Internacionales

| Fuente | URL | Contenido | Frecuencia | Acceso |
|--------|-----|-----------|------------|--------|
| **IMF — Digital Payments** | https://www.imf.org/en/topics/digital-payments-and-finance | Policy papers sobre CBDC, stablecoins, cripto-activos, estabilidad financiera | Irregular (~10-20 papers/año) | Gratuito, PDFs directos |
| **BIS — Research** | https://www.bis.org/research/index.htm | Papers sobre criptomonedas, DeFi, CBDC, infraestructura de pagos, estabilidad financiera | Mensual | Gratuito, PDFs directos |
| **BIS Paper 156** | https://www.bis.org/publ/bppdf/bispap156.pdf | "Cryptocurrencies and DeFi: functions and financial stability" (Abril 2025) | Puntual | Gratuito |
| **ECB — Crypto Publications** | https://www.ecb.europa.eu/home/search/html/crypto-assets.en.html | Crypto-Asset Monitoring (CAMEG), stablecoins, política monetaria | ~10-15 papers/año | Gratuito, PDFs directos |
| **ECB — CAMEG 2025** | https://www.ecb.europa.eu/pub/pdf/scpops/ecb.op382.en.pdf | Dataset de indicadores crypto, monitoreo on-chain/off-chain | Anual | Gratuito |
| **Fed — FEDS Notes** | https://www.federalreserve.gov/econres/notes.htm | Notas de análisis sobre stablecoins, crypto, pagos digitales | Irregular | Gratuito |
| **Fed — Stablecoins Note** | https://www.federalreserve.gov/econres/notes/feds-notes/banks-in-the-age-of-stablecoins-implications-for-deposits-credit-and-financial-intermediation-20251217.html | Implicaciones de stablecoins para el sistema bancario (Dic 2025) | Puntual | Gratuito |

### Bancos de Inversión (Reportes Públicos Selectos)

Los grandes bancos publican research selectiva de forma pública:

| Fuente | Contenido | Acceso |
|--------|-----------|--------|
| **JPMorgan Insights** | Crypto inflows, institutional analysis. Estimaron $130B inflows crypto 2025 | Selectivo — notas de prensa y extractos en CoinDesk/Bloomberg |
| **Goldman Sachs Insights** | Surveys institucionales crypto, regulatory outlook | Selectivo — algunos reportes públicos |
| **Citi GPS** | Global Perspectives & Solutions — reportes macro sobre crypto | Algunos gratuitos previo registro |

> **Nota:** Los reportes completos de sell-side banks son generalmente paywall. La mejor vía es buscar extractos en CoinDesk, The Block, o Bloomberg.

---

## C) Journals Peer-Reviewed Clave

### Quantitative Finance y Trading

| Journal | Publisher | Enfoque | URL |
|---------|-----------|---------|-----|
| **Quantitative Finance** | Taylor & Francis | Métodos teóricos y empíricos en finanzas cuantitativas | https://www.tandfonline.com/journals/rquf20 |
| **Journal of Financial Economics** | Elsevier | Finance theory, empirical finance (top-3 journal) | https://www.sciencedirect.com/journal/journal-of-financial-economics |
| **Review of Financial Studies** | Oxford UP | Investigación financiera rigurosa (top-3 journal) | https://academic.oup.com/rfs |
| **Journal of Finance** | Wiley | El journal más prestigioso de finanzas (top-3) | https://onlinelibrary.wiley.com/journal/15406261 |
| **Journal of Financial Markets** | Elsevier | Market microstructure, trading, liquidez | https://www.sciencedirect.com/journal/journal-of-financial-markets |
| **Journal of Financial and Quantitative Analysis** | Cambridge UP | Análisis cuantitativo y empírico | https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis |

### Crypto y Blockchain Específicos

| Journal | Publisher | Enfoque | URL |
|---------|-----------|---------|-----|
| **Blockchain: Research and Applications** | Elsevier | Research y aplicaciones blockchain (papers recientes Feb 2026) | https://www.sciencedirect.com/journal/blockchain-research-and-applications |
| **Finance Research Letters** | Elsevier | Papers cortos — journal más productivo en crypto microstructure (48 publicaciones) | https://www.sciencedirect.com/journal/finance-research-letters |
| **Economics Letters** | Elsevier | Papers cortos — journal más citado en crypto microstructure (1,651 citas) | https://www.sciencedirect.com/journal/economics-letters |

### AI/ML en Finanzas

| Journal/Conference | Enfoque | URL |
|-------------------|---------|-----|
| **ACM ICAIF** | AI in Finance conference (papers peer-reviewed) | https://ai-finance.org/ |
| **Frontiers in AI** | Open access — papers de LLMs en equity markets | https://www.frontiersin.org/journals/artificial-intelligence |
| **Journal of Risk and Financial Management** | MDPI, open access — algorithmic trading, forecasting | https://www.mdpi.com/journal/jrfm |

---

## D) Curación de Papers y Newsletters

### Agregadores de Research Curado

| Fuente | URL | Contenido | Frecuencia | Acceso |
|--------|-----|-----------|------------|--------|
| **Quantocracy** | https://quantocracy.com/ | Agregador de los mejores blogs y papers de quant finance. "Quant Mashup" diario | Diario | Gratuito |
| **Quantpedia** | https://quantpedia.com/ | Enciclopedia de estrategias de trading derivadas de papers académicos. ~70 estrategias gratis, 900+ premium | Semanal (~70 análisis/año) | Parcial gratuito (70 estrategias free, 900+ premium) |
| **Alpha Architect** | https://alphaarchitect.com/blog/ | Curación de papers académicos de finanzas, factor investing, behavioral finance | 2-3 posts/semana | Gratuito |
| **OpenQuant** | https://openquant.co/blog/research-papers-for-quants | Lista curada de papers esenciales para quants | Irregular | Gratuito |
| **Oxford Man Institute Newsletter** | https://oxford-man.ox.ac.uk/quant-finance-research-newsletter/ | Resumen curado de research en decision-making financiero | Mensual (Mar 2025 — Feb 2026 confirmado) | Gratuito |
| **Wilmott Magazine** | https://wilmott.com/ | Magazine para la comunidad quant (6 ediciones/año) | Bimestral | Parcial gratuito |

### Newsletters Crypto con Enfoque Analítico

| Newsletter | URL | Enfoque | Frecuencia |
|------------|-----|---------|------------|
| **Blockworks Research Daily** | https://blockworks.co/newsletter | Market highlights, charts, governance, análisis cuantitativo | Diario |
| **The Node (CoinDesk)** | https://www.coindesk.com/newsletters/ | Resumen curado por equipo editorial de CoinDesk | Diario |
| **Proof of Work** | Substack | Weekly digest de lo que builders e inversores están leyendo | Semanal |

### GitHub — Listas Curadas

| Repo | URL | Contenido |
|------|-----|-----------|
| **blockchain-papers** | https://github.com/decrypto-org/blockchain-papers | Lista curada de papers académicos sobre blockchain |
| **hft_papers** | https://github.com/baobach/hft_papers | Lista curada de papers de HFT y quant finance |
| **QuantResearch/Resources** | https://github.com/letianzj/QuantResearch/blob/master/Resources.md | Recursos compilados de investigación cuantitativa |

---

## E) Surveys y Meta-Papers Clave (LLM/AI en Trading)

Papers de referencia que mapean el estado del arte:

| Paper | URL | Contenido | Fecha |
|-------|-----|-----------|-------|
| **"Large Language Model Agent in Financial Trading: A Survey"** | https://arxiv.org/abs/2408.06361 | Arquitecturas, datos, performance de LLM trading agents | 2024 (actualizado 2025) |
| **"Integrating LLMs in Financial Investments: A Survey"** | https://arxiv.org/abs/2507.01990 | 4 frameworks: LLM-based, Hybrid, Fine-Tuning, Agent-Based | Jul 2025 |
| **"The New Quant: LLMs in Financial Prediction and Trading"** | https://arxiv.org/abs/2510.05533 | Sistematización 2023-2025, equity prediction + portfolio | Oct 2025 |
| **"Large Language Models in Finance: A Survey"** | https://arxiv.org/abs/2311.10723 | Survey comprehensivo desde Columbia University | 2023 (foundational) |
| **"LLMs in Equity Markets: Applications, Techniques, Insights"** | https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1608365/full | 84 estudios 2022-2025, open access | 2025 |
| **"RL in Financial Decision Making: Systematic Review"** | https://arxiv.org/abs/2512.10913 | 167 artículos, hybrid approaches en aumento (42% en 2025) | Dic 2025 |
| **"Crypto Market Microstructure: Systematic Literature Review"** | https://link.springer.com/article/10.1007/s10479-023-05627-5 | Mapeo completo de research en microestructura crypto | 2023 |
| **"Microstructure and Market Dynamics in Crypto Markets"** | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5337672 | Easley & O'Hara (Cornell) — liquidez, price discovery en crypto | 2025 |

---

## F) APIs Programáticas para el Source Agent

Para automatizar la búsqueda de nuevos papers:

| API | URL | Rate Limit | Auth | Uso |
|-----|-----|------------|------|-----|
| **arXiv API** | https://info.arxiv.org/help/api/index.html | Sin límite documentado (cortesía: 1 req/3s) | No requiere | Búsqueda por categoría, keyword, autor |
| **OpenAlex API** | https://developers.openalex.org/ | 100K calls/día | No requiere key | 250M+ papers, metadata rica, citaciones |
| **Semantic Scholar API** | https://api.semanticscholar.org/ | 100 req/5 min (free), más con key | Key opcional (gratuita) | Búsqueda semántica, grafos de citación |
| **SSRN** | No tiene API pública | N/A | N/A | Solo scraping de search results o RSS |
| **CrossRef API** | https://api.crossref.org/ | Sin límite con "polite pool" (email en header) | No requiere | DOI resolution, metadata de journals |

---

## G) Priorización para el Pipeline del Bot

### Tier 1 — Monitoreo Diario (RSS/API)
1. **arXiv q-fin.TR** — Trading & Market Microstructure
2. **arXiv q-fin.CP** — Computational Finance
3. **arXiv q-fin.ST** — Statistical Finance
4. **arXiv cs.LG** (filtered: "trading" OR "crypto" OR "financial")

### Tier 2 — Monitoreo Semanal
5. **SSRN Cryptocurrency Hub** — nuevos papers crypto
6. **SSRN FEN** — papers de finanzas cuantitativas
7. **Quantocracy** — curación diaria de blogs quant
8. **Binance Research** — análisis de mercado

### Tier 3 — Monitoreo Mensual
9. **Grayscale Research** — outlook y sector reports
10. **IMF/BIS/ECB** — policy papers sobre digital assets
11. **NBER** — working papers de economistas top
12. **Alpha Architect** — curación de papers académicos

### Tier 4 — Consulta Ad-Hoc
13. **OpenAlex API** — búsqueda temática profunda
14. **Semantic Scholar API** — papers relacionados por citación
15. **GitHub curated lists** — listas de referencia

---

## H) Notas de Implementacion

1. **Para el Source Agent:** Las fuentes Tier 1 deberían chequearse vía RSS/API cada 24h. Los papers con keywords relevantes (crypto, bitcoin, algorithmic trading, market microstructure, LLM finance) se agregan automáticamente al pipeline de evaluación.

2. **Para validación de estrategias:** Priorizar papers de journals Tier 1 (JFE, RFS, JF) y preprints con >10 citaciones en Semantic Scholar.

3. **Para contexto regulatorio argentino:** Mantener las fuentes CNV/BCRA ya documentadas en `fuentes-validadas-2026-02-19.md`.

4. **Evitar:** Blogs de influencers, señales de trading, contenido patrocinado. Solo fuentes con respaldo académico o institucional.
