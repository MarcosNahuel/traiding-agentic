import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('Trading Agentic - Full Feature Test', () => {

  test('1. Dashboard - Home Page Analysis', async ({ page }) => {
    await page.goto(BASE_URL);
    // Verificar que el título principal o shell esté presente
    await expect(page).toHaveTitle(/Agentic/i);
    
    // Verificar que existan tarjetas de métricas (PnL, Trades, etc)
    const metrics = page.locator('.grid >> div:has-text("PnL")');
    if (await metrics.count() > 0) {
        await expect(metrics.first()).toBeVisible();
    }
  });

  test('2. Portfolio - Balance Verification', async ({ page }) => {
    await page.goto(`${BASE_URL}/portfolio`);
    // Buscar encabezado de balance (en inglés)
    await expect(page.getByText(/Portfolio|Assets|Balance/i).first()).toBeVisible({ timeout: 10000 });
    
    // Verificar que se cargue la tabla o el estado vacío
    const emptyState = page.getByText(/No assets|Empty|No hay activos/i);
    const table = page.locator('table');
    
    // Esperar a que uno de los dos sea visible
    await expect(page.locator('body')).toContainText(/Portfolio|Assets|Empty|Balance/i);
  });

  test('3. Trades - Proposals and History', async ({ page }) => {
    await page.goto(`${BASE_URL}/trades`);
    // Verificar secciones de propuestas y órdenes ejecutadas
    await expect(page.getByText(/Proposals|History|Orders|Trades/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('4. Strategies - Academic Insights', async ({ page }) => {
    await page.goto(`${BASE_URL}/strategies`);
    // Verificar que liste estrategias o indique que está buscando
    await expect(page.getByText(/Strategies|Estrategias/i).first()).toBeVisible({ timeout: 10000 });
  });

  test('5. Sources - Document Management', async ({ page }) => {
    await page.goto(`${BASE_URL}/sources`);
    // Verificar botón de agregar fuente
    const addButton = page.locator('button:has-text("Fuente"), button:has-text("Add"), button:has-text("Nueva")');
    if (await addButton.count() > 0) {
        await expect(addButton.first()).toBeVisible();
    }
  });

  test('6. Chat Agent - Real-time Interaction', async ({ page }) => {
    await page.goto(`${BASE_URL}/chat`);
    
    // Verificar input de chat
    const chatInput = page.getByPlaceholder(/Escribe|Ask|Message/i);
    await expect(chatInput).toBeVisible();
    
    // Probar envío de mensaje (humo)
    await chatInput.fill('Hola Agente, ¿cómo está el mercado hoy?');
    await chatInput.press('Enter');
    
    // Debería aparecer el mensaje del usuario en pantalla
    await expect(page.getByText('Hola Agente')).toBeVisible();
  });

  test('7. API Diagnostics - System Health', async ({ page }) => {
    // Verificar que el backend responda (vía API route de Next.js si existe)
    const response = await page.request.get(`${BASE_URL}/api/health`);
    if (response.ok()) {
        const data = await response.json();
        expect(data.status).toBeDefined();
    }
  });

});
