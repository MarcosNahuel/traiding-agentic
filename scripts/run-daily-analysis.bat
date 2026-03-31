@echo off
REM ============================================================================
REM Trading Agentic — Daily Strategic Analysis via Claude Code
REM Ejecutar con Windows Task Scheduler a las 7:00 AM
REM ============================================================================

setlocal EnableDelayedExpansion

REM --- Configuracion ---
set "REPO_DIR=D:\OneDrive\GitHub\traiding-agentic"
set "PROMPT_FILE=%REPO_DIR%\prompts\daily-strategic-analysis.md"
set "LOG_DIR=%REPO_DIR%\logs"
set "DATE=%date:~6,4%-%date:~3,2%-%date:~0,2%"
set "LOG_FILE=%LOG_DIR%\claude-daily-%DATE%.log"

REM --- Crear directorio de logs si no existe ---
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%DATE% %time%] Starting daily analysis... >> "%LOG_FILE%"

REM --- Verificar que Claude Code esta instalado ---
where claude >nul 2>&1
if errorlevel 1 (
    echo [%DATE% %time%] ERROR: claude command not found >> "%LOG_FILE%"
    exit /b 1
)

REM --- Verificar que el prompt existe ---
if not exist "%PROMPT_FILE%" (
    echo [%DATE% %time%] ERROR: Prompt file not found: %PROMPT_FILE% >> "%LOG_FILE%"
    exit /b 1
)

REM --- Leer el prompt y reemplazar {DATE} ---
set "PROMPT_CONTENT="
for /f "usebackq delims=" %%a in ("%PROMPT_FILE%") do (
    set "LINE=%%a"
    set "PROMPT_CONTENT=!PROMPT_CONTENT!!LINE! "
)

REM --- Ejecutar Claude Code ---
echo [%DATE% %time%] Running claude -p ... >> "%LOG_FILE%"

cd /d "%REPO_DIR%"
claude -p "Hoy es %DATE%. Ejecuta el analisis estrategico diario siguiendo las instrucciones en prompts/daily-strategic-analysis.md. Lee ese archivo primero y segui las 5 fases en orden." --dangerously-skip-permissions --verbose >> "%LOG_FILE%" 2>&1

set "EXIT_CODE=%errorlevel%"

echo [%DATE% %time%] Claude exited with code %EXIT_CODE% >> "%LOG_FILE%"

REM --- Si fallo, intentar notificar por Telegram ---
if not "%EXIT_CODE%"=="0" (
    echo [%DATE% %time%] Analysis failed. Check log: %LOG_FILE% >> "%LOG_FILE%"
)

echo [%DATE% %time%] Daily analysis complete. >> "%LOG_FILE%"

endlocal
exit /b %EXIT_CODE%
