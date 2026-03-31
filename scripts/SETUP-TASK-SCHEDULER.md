# Setup: Windows Task Scheduler para Daily Analysis

## Prerequisitos

1. Claude Code instalado y logueado (`claude` funciona en terminal)
2. El repo clonado en `D:\OneDrive\GitHub\traiding-agentic`
3. Variables de Telegram configuradas en `backend/.env`

## Opcion A: Setup via GUI

1. Abrir **Task Scheduler** (Win+R → `taskschd.msc`)
2. Click **Create Task** (no "Basic Task")

### Tab: General
- Name: `Trading Agentic - Daily Claude Analysis`
- Description: `Analisis estrategico diario con Claude Code`
- Run whether user is logged on or not: **NO** (dejar "only when logged on" para que Claude tenga acceso al display)
- Run with highest privileges: **SI**

### Tab: Triggers
- Click **New...**
- Begin the task: **On a schedule**
- Daily, Start: **07:00:00**
- Recur every: **1** day
- Enabled: **SI**

### Tab: Actions
- Click **New...**
- Action: **Start a program**
- Program/script: `D:\OneDrive\GitHub\traiding-agentic\scripts\run-daily-analysis.bat`
- Start in: `D:\OneDrive\GitHub\traiding-agentic`

### Tab: Conditions
- Start only if the computer is on AC power: **Desmarcar** (para laptops)
- Wake the computer to run this task: **SI** (opcional)

### Tab: Settings
- Allow task to be run on demand: **SI**
- Stop the task if it runs longer than: **30 minutes**
- If the task fails, restart every: **5 minutes**, up to **2** times
- If the task is already running: **Do not start a new instance**

3. Click **OK**

## Opcion B: Setup via PowerShell (una linea)

Abrir PowerShell como Admin:

```powershell
$action = New-ScheduledTaskAction -Execute "D:\OneDrive\GitHub\traiding-agentic\scripts\run-daily-analysis.bat" -WorkingDirectory "D:\OneDrive\GitHub\traiding-agentic"
$trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "Trading-Claude-DailyAnalysis" -Action $action -Trigger $trigger -Settings $settings -Description "Analisis estrategico diario con Claude Code"
```

## Opcion C: Setup via schtasks (CMD)

```cmd
schtasks /create /tn "Trading-Claude-DailyAnalysis" /tr "D:\OneDrive\GitHub\traiding-agentic\scripts\run-daily-analysis.bat" /sc daily /st 07:00 /rl highest /f
```

## Verificar que funciona

1. En Task Scheduler, click derecho sobre la tarea → **Run**
2. Verificar que se crea el log en `logs/claude-daily-YYYY-MM-DD.log`
3. Verificar que llega el mensaje de Telegram

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| `claude command not found` | Verificar que Claude Code esta en el PATH del sistema |
| No llega Telegram | Verificar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en backend/.env |
| Claude pide permisos | El script usa `--dangerously-skip-permissions` — verificar que Claude Code lo soporte |
| Timeout a los 30 min | Aumentar el limite en Settings o simplificar el prompt |
| PC en sleep | Habilitar "Wake the computer" en Conditions |

## Logs

Los logs se guardan en `logs/claude-daily-YYYY-MM-DD.log`. Revisar si algo falla.
Para ver el ultimo log rapido:

```powershell
Get-Content (Get-ChildItem D:\OneDrive\GitHub\traiding-agentic\logs\claude-daily-*.log | Sort-Object LastWriteTime | Select-Object -Last 1)
```
