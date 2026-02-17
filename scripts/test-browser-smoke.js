const { chromium } = require("playwright");

const BASE_URL = process.env.BASE_URL || "https://traiding-agentic.vercel.app";
const ROUTES = [
  "/",
  "/sources",
  "/strategies",
  "/guides",
  "/chat",
  "/logs",
  "/portfolio",
  "/trades",
];

async function testRoute(context, route) {
  const page = await context.newPage();
  const pageErrors = [];
  const consoleErrors = [];
  const requestFailures = [];

  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  page.on("requestfailed", (request) => {
    const failure = request.failure();
    requestFailures.push(
      `${request.method()} ${request.url()} => ${failure ? failure.errorText : "unknown"}`
    );
  });

  let status = null;
  let hasApplicationErrorText = false;

  try {
    const response = await page.goto(`${BASE_URL}${route}`, {
      waitUntil: "networkidle",
      timeout: 60000,
    });

    status = response ? response.status() : null;
    await page.waitForTimeout(1000);

    const bodyText = await page.innerText("body");
    hasApplicationErrorText = bodyText.includes(
      "Application error: a client-side exception has occurred while loading"
    );
  } catch (error) {
    pageErrors.push(`Navigation failed: ${String(error)}`);
  }

  await page.close();

  return {
    route,
    status,
    hasApplicationErrorText,
    pageErrors,
    consoleErrors,
    requestFailures,
    ok:
      status === 200 &&
      !hasApplicationErrorText &&
      pageErrors.length === 0 &&
      consoleErrors.length === 0,
  };
}

async function main() {
  const browser = await chromium.launch({ headless: true });

  const context = await browser.newContext();
  const results = [];

  for (const route of ROUTES) {
    results.push(await testRoute(context, route));
  }

  await context.close();
  await browser.close();

  const failing = results.filter((r) => !r.ok);
  console.log(JSON.stringify({ baseUrl: BASE_URL, results, failing }, null, 2));

  if (failing.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
