"""
Script to generate infographic images using Gemini API and create MAXI.pdf
"""
import os
import base64
import json
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
import io

# Config
API_KEY = "AIzaSyDFzEqrAAa1kgHQ8GS9pZEXdtvDj02_VF4"
OUTPUT_DIR = Path(r"D:\OneDrive\GitHub\traiding-agentic\docs\02-2026")
MODEL = "gemini-3-pro-image-preview"

client = genai.Client(api_key=API_KEY)

def generate_infographic(prompt: str, filename: str) -> str:
    """Generate an infographic image using Gemini and save it."""
    image_path = OUTPUT_DIR / filename

    print(f"Generating: {filename} with {MODEL}...")
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_data = part.inline_data.data
                img = Image.open(io.BytesIO(img_data))
                img.save(str(image_path))
                print(f"  Saved: {image_path} ({img.size[0]}x{img.size[1]})")
                return str(image_path)

        print(f"  No image in response")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"  WARNING: No image generated for {filename}")
    return ""


def create_pdf():
    """Create MAXI.pdf with content and infographics using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
        Table, TableStyle, PageBreak, HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

    pdf_path = str(OUTPUT_DIR / "MAXI.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=28,
        spaceAfter=6,
        textColor=HexColor('#1a1a2e'),
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        spaceAfter=20,
        textColor=HexColor('#4a4a6a'),
        fontName='Helvetica',
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading1'],
        fontSize=20,
        spaceBefore=24,
        spaceAfter=12,
        textColor=HexColor('#16213e'),
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        'SubSection',
        parent=styles['Heading2'],
        fontSize=15,
        spaceBefore=16,
        spaceAfter=8,
        textColor=HexColor('#0f3460'),
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'BodyText2',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        leading=16,
        textColor=HexColor('#2d2d2d'),
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        'BulletItem',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=4,
        leading=15,
        leftIndent=20,
        textColor=HexColor('#2d2d2d'),
    ))
    styles.add(ParagraphStyle(
        'Highlight',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8,
        leading=16,
        textColor=HexColor('#e94560'),
        fontName='Helvetica-Bold',
    ))
    styles.add(ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontSize=9,
        spaceAfter=12,
        textColor=HexColor('#666666'),
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique',
    ))

    elements = []

    # ─── COVER PAGE ───
    elements.append(Spacer(1, 4*cm))
    elements.append(Paragraph("Proyecto Trading Agentico", styles['CustomTitle']))
    elements.append(Paragraph("Guia de Estrategia y Operaciones para Maximiliano", styles['CustomSubtitle']))
    elements.append(Spacer(1, 1*cm))
    elements.append(HRFlowable(width="60%", thickness=2, color=HexColor('#e94560'), spaceAfter=20))
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("Febrero 2026", styles['CustomSubtitle']))
    elements.append(Paragraph("Documento confidencial - Equipo de Desarrollo", styles['Caption']))
    elements.append(PageBreak())

    # ─── SECTION 1: QUE ESTAMOS CONSTRUYENDO ───
    elements.append(Paragraph("1. Que Estamos Construyendo", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560'), spaceAfter=12))

    elements.append(Paragraph(
        "Imaginate un equipo de analistas que trabajan 24/7 leyendo papers academicos de trading, "
        "extrayendo las mejores estrategias, y armando un manual de operaciones. Despues, ese manual "
        "se lo damos a un bot que opera en el mercado de Bitcoin siguiendo esas instrucciones.",
        styles['BodyText2']
    ))
    elements.append(Paragraph(
        "Eso es exactamente lo que estamos construyendo, pero con inteligencia artificial.",
        styles['Highlight']
    ))

    elements.append(Paragraph("El sistema tiene dos grandes partes:", styles['BodyText2']))
    elements.append(Paragraph(
        "<b>1. El Investigador (Fase 1):</b> Una IA que lee papers de trading, entiende las estrategias, "
        "y genera una guia maestra de operaciones.",
        styles['BulletItem']
    ))
    elements.append(Paragraph(
        "<b>2. El Trader (Fase 2):</b> Un bot que usa esa guia para operar BTC en modo simulado "
        "(paper trading en Binance Testnet, sin dinero real).",
        styles['BulletItem']
    ))

    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("Por que empezamos por la investigacion?", styles['SubSection']))
    elements.append(Paragraph(
        "Muchos bots de trading fracasan porque alguien programa una estrategia que 'le parece buena' "
        "sin evidencia solida. Nosotros hacemos lo contrario: primero investigamos que funciona con datos "
        "reales de papers academicos, despues sintetizamos todo en una estrategia probada, y recien ahi "
        "le damos esa estrategia al bot.",
        styles['BodyText2']
    ))
    elements.append(Paragraph(
        "Es como en medicina: primero estudias la evidencia, despues tratas al paciente.",
        styles['Highlight']
    ))

    # ─── INFOGRAPHIC 1 ───
    img1_path = str(OUTPUT_DIR / "infographic_1_system_overview.png")
    if os.path.exists(img1_path):
        elements.append(Spacer(1, 0.5*cm))
        img = RLImage(img1_path, width=16*cm, height=10*cm)
        img.hAlign = 'CENTER'
        elements.append(img)
        elements.append(Paragraph("Infograma 1: Vision general del sistema de investigacion y trading", styles['Caption']))

    elements.append(PageBreak())

    # ─── SECTION 2: LOS 3 AGENTES ───
    elements.append(Paragraph("2. Los 3 Agentes de Investigacion", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560'), spaceAfter=12))

    # Agent 1
    elements.append(Paragraph("Agente 1: El Curador de Fuentes", styles['SubSection']))
    elements.append(Paragraph(
        "Evalua si un paper o articulo vale la pena leerlo. Le damos una URL y el agente lo evalua "
        "en 4 dimensiones: Relevancia (habla de BTC?), Credibilidad (esta publicado en un journal serio?), "
        "Aplicabilidad (se puede implementar con ~$10K?), y Actualidad (datos recientes?).",
        styles['BodyText2']
    ))
    elements.append(Paragraph(
        "Si el score promedio es 6 o mas, lo aprueba. Si no, lo descarta y explica por que.",
        styles['BodyText2']
    ))

    # Agent 2
    elements.append(Paragraph("Agente 2: El Lector de Papers", styles['SubSection']))
    elements.append(Paragraph(
        "Lee cada paper aprobado y extrae informacion estructurada: estrategias de trading con "
        "todos los detalles (indicadores, reglas de entrada/salida, resultados de backtest, limitaciones), "
        "insights importantes, advertencias de riesgo, y contradicciones con otros papers.",
        styles['BodyText2']
    ))

    # Agent 3
    elements.append(Paragraph("Agente 3: El Sintetizador", styles['SubSection']))
    elements.append(Paragraph(
        "El mas importante. Toma TODO lo que extrajeron los papers y genera la 'Guia Maestra de Trading'. "
        "Encuentra patrones comunes ('5 de 8 papers dicen que RSI adaptativo funciona mejor'), resuelve "
        "contradicciones (da mas peso al paper con mejor backtest y datos mas recientes), rankea "
        "estrategias por evidencia acumulada, y genera un documento que dice exactamente que hacer.",
        styles['BodyText2']
    ))
    elements.append(Paragraph(
        "Cada vez que agregamos nuevos papers, se regenera la guia. El bot se actualiza automaticamente.",
        styles['Highlight']
    ))

    elements.append(PageBreak())

    # ─── SECTION 3: ESTRATEGIA DE TRADING ───
    elements.append(Paragraph("3. Estrategia de Trading Completa", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560'), spaceAfter=12))

    elements.append(Paragraph("Contexto General", styles['SubSection']))

    # Context table
    context_data = [
        ['Parametro', 'Valor'],
        ['Par de trading', 'BTCUSDT'],
        ['Exchange', 'Binance Testnet (simulado)'],
        ['Capital', '10,000 USDT'],
        ['Tamanio por operacion', '0.001 BTC (~$100 USD)'],
        ['Timeframe', 'Velas de 1 min, decisiones cada 5 min'],
        ['Estilo', 'Intraday a swing'],
        ['Leverage', 'Ninguno (1x)'],
    ]
    context_table = Table(context_data, colWidths=[6*cm, 10*cm])
    context_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#16213e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f0f0f5')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(context_table)
    elements.append(Spacer(1, 0.5*cm))

    # Indicators
    elements.append(Paragraph("Indicadores Tecnicos", styles['SubSection']))

    ind_data = [
        ['Indicador', 'Configuracion', 'Uso'],
        ['SMA 10', 'Media movil simple 10 periodos', 'Tendencia corto plazo'],
        ['SMA 50', 'Media movil simple 50 periodos', 'Tendencia mediano plazo'],
        ['RSI 14', 'Relative Strength Index 14p', 'Sobrecompra (>70) / Sobreventa (<30)'],
        ['Bollinger Bands', 'SMA 20 +/- 2 std dev', 'Volatilidad y extremos'],
        ['Volumen Avg 20', 'Media volumen 20 periodos', 'Confirmar interes del mercado'],
        ['ATR 14', 'Average True Range 14p', 'Medir volatilidad para stop-loss'],
    ]
    ind_table = Table(ind_data, colWidths=[3.5*cm, 5.5*cm, 7*cm])
    ind_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0f3460')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f8f8fc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f8f8fc'), HexColor('#eeeef5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(ind_table)
    elements.append(Spacer(1, 0.5*cm))

    # Strategies - wrapped in KeepTogether to avoid page split
    strategy_block = []
    strategy_block.append(Paragraph("Las 4 Estrategias del Bot", styles['SubSection']))

    # Strategy 1
    strategy_block.append(Paragraph("<b>Estrategia 1: Momentum Long (compra por tendencia)</b>", styles['BodyText2']))
    strategy_block.append(Paragraph("Cuando se activa: Mercado en tendencia alcista clara", styles['BulletItem']))
    strategy_block.append(Paragraph("Entrada: SMA 10 cruza por encima de SMA 50 + RSI entre 40-65 + Volumen >120% promedio", styles['BulletItem']))
    strategy_block.append(Paragraph("Salida: Take-profit +3% / Stop-loss -1.5% / RSI >75 / SMA cruce bajista", styles['BulletItem']))
    strategy_block.append(Spacer(1, 0.2*cm))

    # Strategy 2
    strategy_block.append(Paragraph("<b>Estrategia 2: Mean Reversion (compra en sobreventa)</b>", styles['BodyText2']))
    strategy_block.append(Paragraph("Cuando se activa: Mercado lateral o despues de caida brusca", styles['BulletItem']))
    strategy_block.append(Paragraph("Entrada: Precio toca Bollinger inferior + RSI <25 + SMA 50 plana + Volumen decreciente", styles['BulletItem']))
    strategy_block.append(Paragraph("Salida: Precio llega a SMA 20 / Stop-loss -1.5% / RSI >50 / Timeout 2 horas", styles['BulletItem']))
    strategy_block.append(Spacer(1, 0.2*cm))

    # Strategy 3
    strategy_block.append(Paragraph("<b>Estrategia 3: Hold (no hacer nada)</b>", styles['BodyText2']))
    strategy_block.append(Paragraph("Cuando se activa: RSI entre 40-60, SMAs muy cerca, volumen bajo promedio", styles['BulletItem']))
    strategy_block.append(Paragraph("Es la decision mas frecuente e inteligente en mercados indecisos. No forzar trades.", styles['BulletItem']))
    strategy_block.append(Spacer(1, 0.2*cm))

    # Strategy 4
    strategy_block.append(Paragraph("<b>Estrategia 4: Exit Position (cerrar posicion)</b>", styles['BodyText2']))
    strategy_block.append(Paragraph("Se alcanzo stop-loss/take-profit, cambio de condiciones, o riesgo elevado.", styles['BulletItem']))

    elements.append(KeepTogether(strategy_block))

    elements.append(PageBreak())

    # ─── SECTION 4: RISK MANAGEMENT ───
    elements.append(Paragraph("4. Gestion de Riesgo (Automatica)", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560'), spaceAfter=12))

    elements.append(Paragraph(
        "Estas reglas son AUTOMATICAS y NO las controla la IA. Son codigo fijo. "
        "Incluso si la IA dice 'compra', si se excedio un limite, no se ejecuta.",
        styles['Highlight']
    ))

    risk_data = [
        ['Regla', 'Limite', 'Razon'],
        ['Perdida diaria maxima', '-2% ($200)', 'Proteger capital'],
        ['Tamanio de posicion', '0.001 BTC (~$100)', 'Max 1% del capital por trade'],
        ['Posiciones abiertas', '1 a la vez', 'No sobreexponerse'],
        ['Stop-loss automatico', '-1.5% desde entrada', 'No negociable'],
        ['Take-profit automatico', '+3% desde entrada', 'Tomar ganancia'],
        ['Cooldown post-perdida', '30 minutos', 'Evitar revenge trading'],
        ['Leverage maximo', '1x (sin apalancamiento)', 'Solo capital propio'],
    ]
    risk_table = Table(risk_data, colWidths=[4.5*cm, 4*cm, 7.5*cm])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#e94560')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#fff5f5')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#fff5f5'), HexColor('#ffe8e8')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(risk_table)

    # ─── INFOGRAPHIC 2 ───
    img2_path = str(OUTPUT_DIR / "infographic_2_trading_strategy.png")
    if os.path.exists(img2_path):
        elements.append(Spacer(1, 0.8*cm))
        img2 = RLImage(img2_path, width=16*cm, height=10*cm)
        img2.hAlign = 'CENTER'
        elements.append(img2)
        elements.append(Paragraph("Infograma 2: Flujo de decision del trading bot y gestion de riesgo", styles['Caption']))

    elements.append(PageBreak())

    # ─── SECTION 5: TESTING ───
    elements.append(Paragraph("5. Testing y Validacion", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560'), spaceAfter=12))

    elements.append(Paragraph("Fase 1: Validacion de la Investigacion", styles['SubSection']))
    elements.append(Paragraph(
        "<b>Test con papers conocidos:</b> Le damos papers clasicos (Gatev sobre pairs trading, "
        "estudios de momentum en crypto) y verificamos que extraiga las estrategias correctamente.",
        styles['BulletItem']
    ))
    elements.append(Paragraph(
        "<b>Test de contradicciones:</b> Papers que se contradicen para ver si el sintetizador "
        "resuelve el conflicto correctamente.",
        styles['BulletItem']
    ))
    elements.append(Paragraph(
        "<b>Test de calidad de guia:</b> Maxi revisa la guia como trader. Los entry/exit rules "
        "tienen sentido? Los indicadores estan bien?",
        styles['BulletItem']
    ))

    elements.append(Paragraph("Fase 2: Paper Trading (simulado)", styles['SubSection']))
    elements.append(Paragraph(
        "El bot opera con dinero ficticio en Binance Testnet. Los precios son similares a los reales "
        "pero no hay riesgo.",
        styles['BodyText2']
    ))

    metrics_data = [
        ['Metrica', 'Target', 'Que mide'],
        ['Win Rate', '> 55%', '% de operaciones ganadoras'],
        ['Profit Factor', '> 1.5', 'Ganancia total / Perdida total'],
        ['Sharpe Ratio', '> 1.0', 'Retorno ajustado por riesgo'],
        ['Max Drawdown', '< 10%', 'Peor caida del capital'],
        ['Trades por dia', '3-8', 'Actividad del bot'],
    ]
    metrics_table = Table(metrics_data, colWidths=[4*cm, 3*cm, 9*cm])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#16213e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f0f0f5')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f0f0f5'), HexColor('#e4e4ef')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph("Criterios Go/No-Go para dinero real", styles['SubSection']))
    elements.append(Paragraph("Win rate >55% sostenido por 2 semanas", styles['BulletItem']))
    elements.append(Paragraph("Max drawdown <10%", styles['BulletItem']))
    elements.append(Paragraph("Profit factor >1.5", styles['BulletItem']))
    elements.append(Paragraph("Sin errores de sistema en 48 horas", styles['BulletItem']))
    elements.append(Paragraph("Revision de Maxi aprobada", styles['BulletItem']))

    elements.append(PageBreak())

    # ─── SECTION 6: TU ROL ───
    elements.append(Paragraph("6. Tu Rol en el Proyecto, Maxi", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560'), spaceAfter=12))

    elements.append(Paragraph("Fase 1 (ahora):", styles['SubSection']))
    elements.append(Paragraph("<b>Fuentes:</b> Pasanos URLs de papers y articulos de trading que consideres valiosos", styles['BulletItem']))
    elements.append(Paragraph("<b>Revision de estrategias:</b> Validar que las estrategias extraidas tengan sentido", styles['BulletItem']))
    elements.append(Paragraph("<b>Revision de la guia:</b> La guia maestra necesita tu ojo critico", styles['BulletItem']))
    elements.append(Paragraph("<b>Feedback:</b> 'Este indicador esta mal', 'en mi experiencia esto no funciona asi'", styles['BulletItem']))

    elements.append(Paragraph("Fase 2 (despues):", styles['SubSection']))
    elements.append(Paragraph("<b>Parametros de riesgo:</b> Calibrar stop-loss, take-profit, position sizing", styles['BulletItem']))
    elements.append(Paragraph("<b>Analisis:</b> Revisar trades del bot y diagnosticar que hace bien/mal", styles['BulletItem']))
    elements.append(Paragraph("<b>Ajustes:</b> Proponer cambios basados en resultados", styles['BulletItem']))
    elements.append(Paragraph("<b>Go/No-Go:</b> Tu aprobacion es necesaria antes de pasar a real", styles['BulletItem']))

    elements.append(Spacer(1, 1*cm))

    # Cronograma
    elements.append(Paragraph("7. Cronograma", styles['SectionHeader']))
    elements.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560'), spaceAfter=12))

    crono_data = [
        ['Semana', 'Que hacemos', 'Tu participacion'],
        ['1', 'Setup tecnico (DB, infra)', 'Nada, puro codigo'],
        ['2', 'Source Agent + Reader Agent', 'Pasanos 5-10 URLs de papers'],
        ['3', 'Synthesis Agent + Dashboard + Chat', 'Revision de la guia maestra'],
        ['4', 'Pulir + preparar Fase 2', 'Feedback final sobre estrategia'],
        ['5-6', 'Trading Bot en testnet', 'Monitorear operaciones'],
        ['7-8', 'Ajustes basados en resultados', 'Calibrar parametros'],
    ]
    crono_table = Table(crono_data, colWidths=[2*cm, 6.5*cm, 7.5*cm])
    crono_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#16213e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f0f0f5')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f0f0f5'), HexColor('#e4e4ef')]),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(crono_table)

    elements.append(Spacer(1, 1.5*cm))
    elements.append(HRFlowable(width="40%", thickness=1, color=HexColor('#cccccc'), spaceAfter=12))
    elements.append(Paragraph(
        "Documento generado el 15 de febrero de 2026. Se actualizara a medida que el proyecto avance.",
        styles['Caption']
    ))

    # Build PDF
    print(f"Building PDF: {pdf_path}")
    doc.build(elements)
    print(f"PDF created successfully: {pdf_path}")
    return pdf_path


def main():
    print("=" * 60)
    print("MAXI.pdf Generator")
    print("=" * 60)

    # Generate infographic 1: System Overview
    try:
        generate_infographic(
            prompt="""Create a professional infographic diagram.

            Title: "Sistema de Trading Agentico - Como Funciona"

            Show a visual flow with these 3 steps connected by arrows:

            Step 1 (left): "INVESTIGACION" - Icon of papers/documents
            - 3 AI agents read trading papers
            - They extract strategies and insights
            - Sources are evaluated and scored

            Step 2 (center): "GUIA MAESTRA" - Icon of a guide/book
            - AI synthesizes all findings
            - Resolves contradictions between papers
            - Generates a complete trading guide

            Step 3 (right): "TRADING BOT" - Icon of a robot/chart
            - Bot follows the guide automatically
            - Risk manager protects capital
            - Paper trading on Binance Testnet

            At the bottom show a circular arrow indicating "Ciclo continuo: nuevos papers -> nueva guia -> bot actualizado"

            Use a clean, modern design with dark blue (#16213e) and red (#e94560) accent colors on white background.
            Make it look professional and easy to understand for a non-technical person.
            The text should be in Spanish.
            Make the image wide format (landscape), approximately 1600x1000 pixels.""",
            filename="infographic_1_system_overview.png"
        )
    except Exception as e:
        print(f"Error generating infographic 1: {e}")

    # Generate infographic 2: Trading Strategy Flow
    try:
        generate_infographic(
            prompt="""Create a professional infographic diagram.

            Title: "Estrategia de Trading: Flujo de Decision"

            Show a decision flowchart:

            TOP: "Datos de Mercado BTC" (price, volume, indicators)
            Arrow down to:

            CENTER: "IA Analiza Indicadores" showing:
            - SMA 10 vs SMA 50 (tendencia)
            - RSI 14 (sobrecompra/sobreventa)
            - Bollinger Bands (volatilidad)
            - Volumen (interes del mercado)

            From center, 4 arrows to 4 possible decisions:

            1. GREEN box: "MOMENTUM LONG" - Comprar (tendencia alcista fuerte)
            2. BLUE box: "MEAN REVERSION" - Comprar en sobreventa (precio muy bajo)
            3. GRAY box: "HOLD" - Esperar (sin senal clara)
            4. ORANGE box: "EXIT" - Cerrar posicion

            On the RIGHT side, a RED shield labeled "RISK MANAGER" with rules:
            - Max perdida diaria: -2%
            - Stop-loss: -1.5%
            - Take-profit: +3%
            - 1 posicion a la vez
            Text: "Reglas fijas - La IA NO puede cambiarlas"

            At bottom: "Binance Testnet (Paper Trading - Sin dinero real)"

            Use clean modern design, dark blue (#16213e) and red (#e94560) accent colors on white background.
            Professional and easy to understand for a trader (not a developer).
            Text in Spanish.
            Make the image wide format (landscape), approximately 1600x1000 pixels.""",
            filename="infographic_2_trading_strategy.png"
        )
    except Exception as e:
        print(f"Error generating infographic 2: {e}")

    # Create PDF
    create_pdf()

    print("\n" + "=" * 60)
    print("DONE!")
    print(f"Files saved to: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
