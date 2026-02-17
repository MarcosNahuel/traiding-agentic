#!/bin/bash

# ============================================
# Script de verificación de deployment
# ============================================

# ⚠️ CAMBIAR ESTA URL por tu dominio real
BASE_URL="https://trading.tudominio.com"

echo "🧪 Verificando deployment en: $BASE_URL"
echo "============================================"
echo ""

# Test 1: Health Check
echo "1️⃣ Health Check..."
curl -s "$BASE_URL/api/health" | jq . || echo "❌ Failed"
echo ""

# Test 2: Binance Connection
echo "2️⃣ Binance Connection..."
curl -s "$BASE_URL/api/binance/test" | jq . || echo "❌ Failed"
echo ""

# Test 3: Portfolio
echo "3️⃣ Portfolio..."
curl -s "$BASE_URL/api/portfolio" | jq . || echo "❌ Failed"
echo ""

# Test 4: Verificar logs de startup
echo "4️⃣ Verificando modo de Binance..."
echo "   → Revisá los logs en EasyPanel"
echo "   → Debe decir: '🎯 Binance Direct Mode: Enabled'"
echo ""

echo "============================================"
echo "✅ Si todos los tests pasaron, estás listo!"
echo "🎯 Podés empezar a tradear desde Brasil 🇧🇷"
echo ""
echo "Próximos pasos:"
echo "  1. Ejecutar primer trade de prueba"
echo "  2. Configurar Telegram alerts"
echo "  3. Activar trading automático"
