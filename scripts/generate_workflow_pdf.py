"""Genera un PDF gráfico explicando el workflow del sistema de trading agentic."""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Flowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

# Paleta
NAVY = HexColor("#0F172A")
BLUE = HexColor("#2563EB")
TEAL = HexColor("#0891B2")
GREEN = HexColor("#16A34A")
ORANGE = HexColor("#EA580C")
RED = HexColor("#DC2626")
PURPLE = HexColor("#7C3AED")
GRAY = HexColor("#64748B")
LIGHT = HexColor("#F1F5F9")
LIGHT2 = HexColor("#E2E8F0")
WHITE = HexColor("#FFFFFF")
YELLOW = HexColor("#FACC15")

OUT = r"C:\Users\nahue\Documents\PROYECTOS\traiding-agentic\docs\workflow-trading-agentic.pdf"

styles = getSampleStyleSheet()

H1 = ParagraphStyle("H1", parent=styles["Heading1"],
                    fontName="Helvetica-Bold", fontSize=22, textColor=NAVY,
                    spaceAfter=10, spaceBefore=4)
H2 = ParagraphStyle("H2", parent=styles["Heading2"],
                    fontName="Helvetica-Bold", fontSize=16, textColor=BLUE,
                    spaceAfter=8, spaceBefore=14)
H3 = ParagraphStyle("H3", parent=styles["Heading3"],
                    fontName="Helvetica-Bold", fontSize=12, textColor=NAVY,
                    spaceAfter=4, spaceBefore=10)
BODY = ParagraphStyle("BODY", parent=styles["BodyText"],
                      fontName="Helvetica", fontSize=10.5, textColor=NAVY,
                      leading=15, spaceAfter=6)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=9, textColor=GRAY, leading=12)
WHITE_BOLD = ParagraphStyle("WB", parent=BODY, fontName="Helvetica-Bold",
                             fontSize=11, textColor=WHITE, alignment=TA_CENTER, leading=14)
WHITE_BODY = ParagraphStyle("WBd", parent=BODY, fontSize=9.5, textColor=WHITE,
                             alignment=TA_CENTER, leading=12)
CENTER_BOLD = ParagraphStyle("CB", parent=BODY, fontName="Helvetica-Bold",
                              fontSize=11, alignment=TA_CENTER)


# ---------- Flowables custom ----------

class ColorBox(Flowable):
    """Caja coloreada con título y bullets."""
    def __init__(self, title, lines, color, width=17*cm, height=2.6*cm, icon=""):
        super().__init__()
        self.title = title; self.lines = lines; self.color = color
        self.width = width; self.height = height; self.icon = icon

    def wrap(self, *args): return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(self.color); c.setStrokeColor(self.color)
        c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(0.4*cm, self.height - 0.7*cm, f"{self.icon}  {self.title}")
        c.setFont("Helvetica", 9.5)
        y = self.height - 1.3*cm
        for ln in self.lines:
            c.drawString(0.6*cm, y, f"•  {ln}")
            y -= 0.42*cm


class Arrow(Flowable):
    """Flecha vertical ↓ centrada."""
    def __init__(self, label="", color=GRAY, width=17*cm, height=0.9*cm):
        super().__init__()
        self.label = label; self.color = color
        self.width = width; self.height = height

    def wrap(self, *a): return self.width, self.height

    def draw(self):
        c = self.canv
        cx = self.width / 2
        c.setStrokeColor(self.color); c.setFillColor(self.color)
        c.setLineWidth(2)
        c.line(cx, self.height - 0.1*cm, cx, 0.3*cm)
        # punta
        p = c.beginPath()
        p.moveTo(cx - 0.18*cm, 0.3*cm)
        p.lineTo(cx + 0.18*cm, 0.3*cm)
        p.lineTo(cx, 0.0)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        if self.label:
            c.setFont("Helvetica-Oblique", 9); c.setFillColor(self.color)
            c.drawString(cx + 0.4*cm, self.height/2 - 0.1*cm, self.label)


class Pill(Flowable):
    """Píldora horizontal para el header (3 columnas, ej. Frontend / Backend / DB)."""
    def __init__(self, items, width=17*cm, height=2.0*cm):
        super().__init__()
        self.items = items; self.width = width; self.height = height

    def wrap(self, *a): return self.width, self.height

    def draw(self):
        c = self.canv
        n = len(self.items)
        gap = 0.3*cm
        w = (self.width - gap*(n-1)) / n
        for i, (title, sub, color) in enumerate(self.items):
            x = i * (w + gap)
            c.setFillColor(color)
            c.roundRect(x, 0, w, self.height, 8, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(x + w/2, self.height - 0.7*cm, title)
            c.setFont("Helvetica", 9)
            # sub puede tener \n
            yy = self.height - 1.2*cm
            for ln in sub.split("\n"):
                c.drawCentredString(x + w/2, yy, ln); yy -= 0.36*cm


class Legend(Flowable):
    """Leyenda de colores horizontal."""
    def __init__(self, items, width=17*cm, height=0.8*cm):
        super().__init__()
        self.items = items; self.width = width; self.height = height
    def wrap(self, *a): return self.width, self.height
    def draw(self):
        c = self.canv
        x = 0
        for label, color in self.items:
            c.setFillColor(color); c.rect(x, 0.15*cm, 0.5*cm, 0.5*cm, fill=1, stroke=0)
            c.setFillColor(NAVY); c.setFont("Helvetica", 9)
            c.drawString(x + 0.65*cm, 0.28*cm, label)
            x += 4.5*cm


# ---------- Page decorations ----------

def page_decor(canv, doc):
    canv.saveState()
    # Header bar
    canv.setFillColor(NAVY)
    canv.rect(0, A4[1] - 1.0*cm, A4[0], 1.0*cm, fill=1, stroke=0)
    canv.setFillColor(WHITE); canv.setFont("Helvetica-Bold", 10)
    canv.drawString(1.5*cm, A4[1] - 0.65*cm, "Trading Agentic — Workflow del sistema")
    canv.setFont("Helvetica", 9)
    canv.drawRightString(A4[0] - 1.5*cm, A4[1] - 0.65*cm, "Para Nahuel  •  2026-04-25")
    # Footer
    canv.setFillColor(GRAY); canv.setFont("Helvetica", 8)
    canv.drawCentredString(A4[0]/2, 0.7*cm, f"Página {doc.page}")
    canv.restoreState()


# ---------- Build ----------

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=2*cm, rightMargin=2*cm,
                        topMargin=1.6*cm, bottomMargin=1.5*cm,
                        title="Workflow Trading Agentic", author="Trading Agentic")

story = []

# ===== PORTADA / RESUMEN =====
story.append(Paragraph("Trading Agentic", H1))
story.append(Paragraph(
    "Cómo funciona tu sistema, de punta a punta — sin tantos tecnicismos.",
    ParagraphStyle("sub", parent=BODY, fontSize=12, textColor=GRAY, spaceAfter=12)))

story.append(Pill([
    ("Frontend", "Next.js 16\nVercel\nDashboard + APIs", BLUE),
    ("Backend", "Python FastAPI\nDokploy VPS\nMotor cuantitativo", TEAL),
    ("Datos & IA", "Supabase (DB)\nGemini + Claude\nBinance Testnet", PURPLE),
]))
story.append(Spacer(1, 0.4*cm))

story.append(Paragraph("¿Qué hace este sistema en una frase?", H3))
story.append(Paragraph(
    "Investiga el mercado con IA, decide cuándo abrir/cerrar operaciones siguiendo "
    "una estrategia cuantitativa, ejecuta en Binance Testnet con un kill-switch, "
    "y te avisa por Telegram con botones de aprobación.", BODY))

story.append(Paragraph("Las 3 piezas que tenés que recordar", H3))
story.append(ColorBox("1. Cerebro de IA  (research + estrategia)",
    ["Lee fuentes, papers y noticias",
     "Genera 'guías de trading' y propone ajustes de parámetros",
     "Modelos: Gemini (rápido) + Claude (Strategist Agent — Fase 1)"],
    PURPLE, height=2.5*cm, icon="🧠"))
story.append(Spacer(1, 0.2*cm))
story.append(ColorBox("2. Motor cuantitativo  (Python / FastAPI)",
    ["Loop de 60s: indicadores técnicos, regímenes, señales",
     "Aplica reglas: cooldown, ATR, riesgo, Chandelier Exit",
     "Habla con Binance Testnet para abrir/cerrar posiciones"],
    TEAL, height=2.5*cm, icon="⚙️"))
story.append(Spacer(1, 0.2*cm))
story.append(ColorBox("3. Operador humano  (vos)",
    ["Mirás el dashboard en Vercel",
     "Aprobás/rechazás cambios de configuración por Telegram",
     "Activás el kill-switch (TRADING_ENABLED) cuando hace falta"],
    ORANGE, height=2.5*cm, icon="👤"))

story.append(PageBreak())

# ===== DIAGRAMA DE FLUJO PRINCIPAL =====
story.append(Paragraph("Workflow completo — el viaje de una operación", H2))
story.append(Paragraph(
    "Así se mueve la información desde que el sistema mira el mercado hasta que "
    "una orden queda ejecutada y vos recibís el aviso.", BODY))
story.append(Spacer(1, 0.3*cm))

flow = [
    ("📊  1. Captura de datos de mercado",
     ["Binance Testnet → velas (OHLCV), order book",
      "Binance Futures (read-only) → funding rate, open interest"],
     BLUE),
    ("🧮  2. Análisis cuantitativo (cada 60s)",
     ["Indicadores: RSI, ADX, ATR, EMAs, entropía",
      "Detecta régimen: trend / range / chop"],
     TEAL),
    ("🤖  3. Cerebro IA decide ajustes (1×/día)",
     ["Strategist Agent (Claude) propone cambios de parámetros",
      "Bounds SSOT — nunca puede pedir valores fuera de rango seguro"],
     PURPLE),
    ("📲  4. Aprobación por Telegram",
     ["Te llega un mensaje con botones [Aprobar] [Rechazar]",
      "Token timing-safe — solo vos podés aprobar"],
     ORANGE),
    ("🎯  5. Generación de señal",
     ["Si hay setup válido y no estás en cooldown → señal BUY/SELL",
      "Calcula tamaño con ATR + riesgo configurado"],
     YELLOW),
    ("✅  6. Ejecución en Binance Testnet",
     ["Orden con SL/TP basados en ATR",
      "Partial exit 50% al 1R + Chandelier trailing"],
     GREEN),
    ("📝  7. Registro y aviso",
     ["Posición guardada en Supabase",
      "Telegram te avisa: entrada, salida parcial, cierre"],
     NAVY),
]

for title, lines, color in flow:
    story.append(ColorBox(title, lines, color, height=2.0*cm))
    story.append(Arrow(color=GRAY))

story.append(Paragraph(
    "Si en cualquier paso TRADING_ENABLED=false, el sistema sigue analizando "
    "pero <b>no ejecuta nada</b>. Es tu freno de mano.", SMALL))

story.append(PageBreak())

# ===== HERRAMIENTAS =====
story.append(Paragraph("Herramientas que usa el sistema", H2))
story.append(Paragraph(
    "Cada herramienta hace una cosa concreta. Si algo falla, ya sabés a quién mirar.",
    BODY))
story.append(Spacer(1, 0.2*cm))

tool_data = [
    ["Categoría", "Herramienta", "Para qué sirve"],
    ["Frontend", "Next.js 16 (App Router)", "Dashboard, formularios, API routes"],
    ["", "React 19 + Tailwind 4", "UI del operador"],
    ["", "shadcn/ui + Lucide", "Componentes y íconos"],
    ["", "Vercel", "Hosting + Cron jobs (cleanup, watchdog)"],
    ["Backend", "Python 3.12 + FastAPI", "Motor cuantitativo y API trading"],
    ["", "Pandas / NumPy / SciPy", "Procesamiento numérico de velas"],
    ["", "Pandas-TA", "Indicadores técnicos (RSI, ADX, ATR…)"],
    ["", "httpx (async)", "Cliente HTTP para Binance Futures"],
    ["", "Dokploy (VPS)", "Despliegue del backend en Docker"],
    ["Datos", "Supabase Postgres", "DB: posiciones, configs, logs"],
    ["", "Supabase Auth", "Login del dashboard"],
    ["IA", "Google Gemini (Vercel AI SDK)", "Source / Reader / Synthesis / Chat"],
    ["", "Claude Agent SDK (Python)", "Strategist Agent — Fase 1"],
    ["", "LangGraph (en retiro)", "Pipeline diario antiguo, en decommission"],
    ["Trading", "Binance Spot Testnet", "Ejecución real de órdenes"],
    ["", "Binance Futures (read-only)", "Funding rate + open interest"],
    ["Avisos", "Telegram Bot API", "Notifs + aprobaciones inline"],
    ["Calidad", "pytest + pytest-asyncio", "Tests del backend (56+)"],
    ["", "ESLint + TypeScript strict", "Linter y tipos del frontend"],
    ["", "Playwright", "Tests integrales"],
    ["CI/CD", "GitHub Actions", "Lint + typecheck + tests + build"],
]

t = Table(tool_data, colWidths=[3.0*cm, 5.5*cm, 8.5*cm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("TEXTCOLOR", (0,0), (-1,0), WHITE),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 9.5),
    ("ALIGN", (0,0), (-1,0), "LEFT"),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.3, LIGHT2),
    ("LEFTPADDING", (0,0), (-1,-1), 6),
    ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ("TOPPADDING", (0,0), (-1,-1), 5),
    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    # Resaltar primera columna por bloque
    ("FONTNAME", (0,1), (0,-1), "Helvetica-Bold"),
    ("TEXTCOLOR", (0,1), (0,-1), BLUE),
]))
story.append(t)

story.append(PageBreak())

# ===== CICLOS DEL SISTEMA =====
story.append(Paragraph("Los 3 ciclos del sistema", H2))
story.append(Paragraph(
    "El sistema corre en paralelo con tres relojes distintos. Cada uno tiene "
    "su responsabilidad y nunca se pisan.", BODY))
story.append(Spacer(1, 0.3*cm))

story.append(ColorBox("⚡  Ciclo rápido — cada 60 segundos",
    ["Lee precios y recalcula indicadores",
     "Evalúa entradas/salidas, partial exit, trailing",
     "Ejecuta órdenes en Binance si hay señal"],
    BLUE, height=2.5*cm))
story.append(Spacer(1, 0.3*cm))

story.append(ColorBox("🕐  Ciclo medio — cada 5 minutos (Vercel Cron)",
    ["Limpia configs pendientes vencidas",
     "Watchdog: chequea que el backend Python esté vivo",
     "Fallback: si el backend cae, ejecuta análisis básico"],
    TEAL, height=2.5*cm))
story.append(Spacer(1, 0.3*cm))

story.append(ColorBox("📅  Ciclo lento — 1 vez al día (Strategist Agent)",
    ["Investiga mercado: regímenes, papers, noticias",
     "Propone nuevos parámetros (RSI, ADX, riesgo, etc.)",
     "Te pide aprobación por Telegram → vos decidís"],
    PURPLE, height=2.5*cm))

story.append(Spacer(1, 0.5*cm))

# ===== SEGURIDAD =====
story.append(Paragraph("Las barreras de seguridad", H2))

safety = [
    ("🔒  Kill switch", "TRADING_ENABLED=false detiene toda ejecución sin tocar código.", RED),
    ("📏  Bounds SSOT", "La IA nunca puede salirse del rango seguro de parámetros.", ORANGE),
    ("✅  Aprobación humana", "Cambios de config requieren tu OK por Telegram.", GREEN),
    ("🧪  Solo Testnet", "Binance Spot Testnet — sin plata real hasta que lo decidas.", BLUE),
    ("🛡️  SSRF + Auth", "API routes protegidas, middleware Supabase en el dashboard.", PURPLE),
]
for title, txt, color in safety:
    story.append(ColorBox(title, [txt], color, height=1.7*cm))
    story.append(Spacer(1, 0.15*cm))

story.append(PageBreak())

# ===== CHEAT SHEET =====
story.append(Paragraph("Cheat sheet — comandos del día a día", H2))

cmd_data = [
    ["Acción", "Comando"],
    ["Levantar frontend",       "pnpm dev"],
    ["Build frontend",          "pnpm build"],
    ["Lint + tipos",            "pnpm lint  &&  pnpm typecheck"],
    ["Levantar backend Python", "uvicorn app.main:app --reload --port 8000"],
    ["Tests backend",           "pytest tests/ -q --tb=short"],
    ["Refrescar contexto KB",   "python scripts/refresh-market-context.py"],
    ["Smoke Binance Futures",   "python backend/scripts/smoke_derivatives.py"],
    ["Chequear proxy drift",    "python backend/scripts/check_proxy_drift.py"],
]
t2 = Table(cmd_data, colWidths=[6*cm, 11*cm], repeatRows=1)
t2.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), NAVY),
    ("TEXTCOLOR", (0,0), (-1,0), WHITE),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTNAME", (1,1), (1,-1), "Courier-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 10),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.3, LIGHT2),
    ("LEFTPADDING", (0,0), (-1,-1), 8),
    ("TOPPADDING", (0,0), (-1,-1), 6),
    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
]))
story.append(t2)

story.append(Spacer(1, 0.6*cm))
story.append(Paragraph("Variables de entorno que importan", H3))
env_data = [
    ["Variable", "Para qué"],
    ["TRADING_ENABLED",         "Kill switch. Default: false"],
    ["BINANCE_TESTNET_API_KEY", "Llave del exchange (testnet)"],
    ["GOOGLE_AI_API_KEY",       "Gemini (research + chat)"],
    ["TELEGRAM_BOT_TOKEN",      "Notifs y botones de aprobación"],
    ["STRATEGIST_APPROVAL_TOKEN","Token para aprobar configs"],
    ["CRON_SECRET",             "Auth de los cron jobs Vercel"],
    ["LANGGRAPH_DAILY_ENABLED", "Apaga el pipeline viejo cuando esté listo"],
    ["PARTIAL_EXIT_ENABLED",    "Activa toma parcial al 1R"],
]
t3 = Table(env_data, colWidths=[7*cm, 10*cm], repeatRows=1)
t3.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), TEAL),
    ("TEXTCOLOR", (0,0), (-1,0), WHITE),
    ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ("FONTNAME", (0,1), (0,-1), "Courier-Bold"),
    ("FONTSIZE", (0,0), (-1,-1), 9.5),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LIGHT]),
    ("GRID", (0,0), (-1,-1), 0.3, LIGHT2),
    ("LEFTPADDING", (0,0), (-1,-1), 8),
    ("TOPPADDING", (0,0), (-1,-1), 5),
    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
]))
story.append(t3)

story.append(Spacer(1, 0.8*cm))
story.append(Paragraph(
    "Este documento es un mapa, no un manual exhaustivo. Para detalles técnicos: "
    "<b>docs/superpowers/specs/</b> y <b>docs/knowledge-base/</b>.", SMALL))

# Build
doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
print(f"OK -> {OUT}")
