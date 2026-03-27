"""Regenerate infographics with higher quality prompts using gemini-3-pro-image-preview."""
import os
import io
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image

API_KEY = "AIzaSyDFzEqrAAa1kgHQ8GS9pZEXdtvDj02_VF4"
OUTPUT_DIR = Path(r"D:\OneDrive\GitHub\traiding-agentic\docs\02-2026")
MODEL = "gemini-3-pro-image-preview"

client = genai.Client(api_key=API_KEY)

def generate(prompt: str, filename: str):
    print(f"\nGenerating: {filename}...")
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )
    path = OUTPUT_DIR / filename
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            img = Image.open(io.BytesIO(part.inline_data.data))
            # Save as high quality PNG
            img.save(str(path), optimize=False)
            print(f"  OK: {img.size[0]}x{img.size[1]} -> {path}")
            return True
    print("  FAILED: no image returned")
    return False

# Infographic 1: System Overview
generate(
    prompt="""Generate a high-quality, clean, professional infographic image in SPANISH.

Title at the top in large bold text: "Sistema de Trading Agentico"
Subtitle: "Como Funciona - Vision General"

The infographic should show 3 phases connected by large curved arrows flowing left to right:

PHASE 1 (Left column, blue background card):
Header: "FASE 1: INVESTIGACION"
Icon: magnifying glass over documents
Bullet points:
- 3 agentes de IA leen papers academicos
- Extraen estrategias e insights clave
- Evaluan credibilidad y relevancia
- Almacenan en base de datos vectorial

PHASE 2 (Center column, dark blue background card):
Header: "FASE 2: GUIA MAESTRA"
Icon: open book with a star/badge
Bullet points:
- La IA sintetiza todos los hallazgos
- Resuelve contradicciones entre papers
- Rankea estrategias por evidencia
- Genera guia de trading completa

PHASE 3 (Right column, green background card):
Header: "FASE 3: TRADING BOT"
Icon: robot with chart trending up
Bullet points:
- El bot sigue la guia automaticamente
- Risk Manager protege el capital
- Paper trading en Binance Testnet
- Monitoreo en dashboard en tiempo real

At the very bottom, a horizontal banner with circular arrow icon:
"Ciclo continuo: nuevos papers → nueva guia → bot actualizado"

Design requirements:
- White background, clean modern design
- Color scheme: dark navy (#16213e), red accent (#e94560), white text on dark cards
- High contrast, very readable text
- Professional corporate style, similar to McKinsey or BCG consulting slides
- Landscape format (wider than tall)
- All text in Spanish
- No watermarks or logos
- Sharp, crisp rendering""",
    filename="infographic_1_system_overview.png"
)

# Infographic 2: Trading Decision Flow
generate(
    prompt="""Generate a high-quality, clean, professional infographic image in SPANISH.

Title at the top in large bold text: "Flujo de Decision del Trading Bot"

The infographic should show a TOP-TO-BOTTOM decision flowchart:

TOP SECTION (input data):
A wide blue box: "Datos de Mercado BTC en Tiempo Real"
With 3 sub-items in a row: "Precio" | "Volumen" | "Indicadores Tecnicos"

MIDDLE SECTION (analysis):
Arrow down to a large central box: "IA Analiza Indicadores"
Inside this box, show 4 indicators in a 2x2 grid:
- SMA 10 vs SMA 50 → Tendencia
- RSI 14 → Sobrecompra / Sobreventa
- Bollinger Bands → Volatilidad
- Volumen → Interes del mercado

BOTTOM SECTION (4 decisions):
From the analysis box, 4 arrows spread down to 4 colored boxes:

1. GREEN box with up-arrow icon: "MOMENTUM LONG"
   Subtitle: "Comprar - tendencia alcista fuerte"

2. BLUE box with bounce icon: "MEAN REVERSION"
   Subtitle: "Comprar en sobreventa"

3. GRAY box with pause icon: "HOLD"
   Subtitle: "Esperar - sin senal clara"

4. ORANGE box with exit icon: "EXIT"
   Subtitle: "Cerrar posicion"

RIGHT SIDE: A prominent RED shield/badge labeled "RISK MANAGER"
With checkmarks:
✓ Max perdida diaria: -2%
✓ Stop-loss: -1.5%
✓ Take-profit: +3%
✓ 1 posicion a la vez
Bold red text: "Reglas fijas - La IA NO puede cambiarlas"

FOOTER: Dark banner: "Binance Testnet - Paper Trading - Sin dinero real"

Design requirements:
- White background, clean modern design
- Color scheme: dark navy (#16213e), red for risk (#e94560), green for buy, gray for hold
- High contrast, very readable text, large font sizes
- Professional corporate style
- Landscape format (wider than tall)
- All text in Spanish
- No watermarks or logos
- Sharp, crisp rendering""",
    filename="infographic_2_trading_strategy.png"
)

print("\nDone!")
