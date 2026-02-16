#!/bin/bash

# 🧪 Production Verification Script
# Run this after fixing the Supabase token to verify everything works

echo "🧪 Testing Production Deployment..."
echo "URL: https://traiding-agentic.vercel.app"
echo ""

PASS=0
FAIL=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health endpoint
echo "📡 Test 1: Health Check"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" https://traiding-agentic.vercel.app/api/health)
if [ "$HEALTH" -eq 200 ]; then
  echo -e "${GREEN}✅ PASS${NC} - Health endpoint returned 200"
  ((PASS++))
else
  echo -e "${RED}❌ FAIL${NC} - Health endpoint returned $HEALTH"
  ((FAIL++))
fi
echo ""

# Test 2: Environment variables
echo "🔐 Test 2: Environment Variables"
ENV_CHECK=$(curl -s https://traiding-agentic.vercel.app/api/diagnostic)
if echo "$ENV_CHECK" | grep -q '"exists":true'; then
  echo -e "${GREEN}✅ PASS${NC} - Environment variables are present"
  ((PASS++))
else
  echo -e "${RED}❌ FAIL${NC} - Some environment variables are missing"
  ((FAIL++))
fi
echo ""

# Test 3: JWT Token Validation
echo "🔑 Test 3: JWT Token Validation"
JWT_CHECK=$(curl -s https://traiding-agentic.vercel.app/api/diagnostic/jwt)
if echo "$JWT_CHECK" | grep -q '"match":true'; then
  echo -e "${GREEN}✅ PASS${NC} - JWT token is valid and matches URL"
  ((PASS++))
else
  echo -e "${RED}❌ FAIL${NC} - JWT token is invalid or doesn't match"
  echo "Response: $JWT_CHECK"
  ((FAIL++))
fi
echo ""

# Test 4: Supabase Connection
echo "🗄️  Test 4: Supabase Connection"
SUPABASE_CHECK=$(curl -s https://traiding-agentic.vercel.app/api/diagnostic/supabase)
if echo "$SUPABASE_CHECK" | grep -q '"step":"query_sources","status":"success"'; then
  echo -e "${GREEN}✅ PASS${NC} - Supabase queries work correctly"
  ((PASS++))
else
  echo -e "${RED}❌ FAIL${NC} - Supabase connection has errors"
  echo "Response: $SUPABASE_CHECK"
  ((FAIL++))
fi
echo ""

# Test 5: Sources API
echo "📄 Test 5: Sources API"
SOURCES=$(curl -s -o /dev/null -w "%{http_code}" https://traiding-agentic.vercel.app/api/sources)
if [ "$SOURCES" -eq 200 ]; then
  echo -e "${GREEN}✅ PASS${NC} - Sources API returned 200"
  ((PASS++))
else
  echo -e "${RED}❌ FAIL${NC} - Sources API returned $SOURCES"
  ((FAIL++))
fi
echo ""

# Test 6: Strategies API
echo "📊 Test 6: Strategies API"
STRATEGIES=$(curl -s -o /dev/null -w "%{http_code}" https://traiding-agentic.vercel.app/api/strategies)
if [ "$STRATEGIES" -eq 200 ]; then
  echo -e "${GREEN}✅ PASS${NC} - Strategies API returned 200"
  ((PASS++))
else
  echo -e "${RED}❌ FAIL${NC} - Strategies API returned $STRATEGIES"
  ((FAIL++))
fi
echo ""

# Test 7: Guides API
echo "📖 Test 7: Guides API"
GUIDES=$(curl -s -o /dev/null -w "%{http_code}" https://traiding-agentic.vercel.app/api/guides)
if [ "$GUIDES" -eq 200 ]; then
  echo -e "${GREEN}✅ PASS${NC} - Guides API returned 200"
  ((PASS++))
else
  echo -e "${RED}❌ FAIL${NC} - Guides API returned $GUIDES"
  ((FAIL++))
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "✅ Passed: ${GREEN}$PASS${NC}"
echo -e "❌ Failed: ${RED}$FAIL${NC}"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}🎉 ALL TESTS PASSED!${NC}"
  echo "Production deployment is fully functional."
  echo ""
  echo "Next steps:"
  echo "1. Try adding a test paper via POST /api/sources"
  echo "2. Check the agent logs to see processing"
  echo "3. Once 5+ papers are processed, a guide will auto-generate"
  exit 0
else
  echo -e "${RED}⚠️  SOME TESTS FAILED${NC}"
  echo "Please review the errors above and:"
  echo "1. Check if SUPABASE_SERVICE_ROLE_KEY is correct in Vercel"
  echo "2. Verify the token is complete (200+ characters)"
  echo "3. Redeploy after making changes"
  echo ""
  echo "For detailed troubleshooting, see:"
  echo "- docs/QUICK-FIX-GUIDE.md"
  echo "- docs/PRODUCTION-TEST-REPORT.md"
  exit 1
fi
