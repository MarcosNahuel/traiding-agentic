# Retiro de servicios — 20/10/2026
## Decisión de Nahuel
El 20/10/2026 Nahuel pidió retirar Trading, incluidos sus recursos de ejecución y base de datos, como parte de la limpieza de infraestructura. Antes de eliminar recursos pidió dejar la decisión en el proyecto y conservar el worker en el repositorio para poder reconstruirlo más adelante.

El código y el historial Git se conservan. La futura reactivación necesita una nueva orden: un push o un documento anterior de despliegue no autorizan arrancar servicios.

## Código conservado
- Repositorio: MarcosNahuel/traiding-agentic.
- Base remota verificada antes del retiro: `e4269b85a04187df693a6a98166346f6337c59d8`.
- Worker/backend: [`backend/`](../../backend/), con Dockerfile, dependencias y código ya versionados en main.
- Las credenciales no se copian al repositorio. No se afirma equivalencia byte a byte entre el código de main y la imagen desplegada.

## Inventario del retiro
| Recurso | Identidad |
|---|---|
| Backend Dokploy/VPS | `app-connect-bluetooth-microchip-xaidvw` |
| applicationId Dokploy | `m8vNSwbx_t0ckLFEh7mgZ` |
| Frontend Vercel | `traiding-agentic` |
| projectId Vercel | `prj_pKJyid3iv8HnJBVLcsGXjw8eF2xJ` |
| Base configurada en Supabase Cloud | `zaqpiuwacinvebfttygm` |

La base configurada es externa al VPS. El backend inspeccionado no monta un volumen de base de datos propio. El retiro de esta base no libera memoria PostgreSQL en el VPS.

## Estado comprobado antes de borrar
- Backend detenido desde Dokploy: cero réplicas deseadas y cero réplicas activas.
- Autodeploy de Dokploy desactivado para que un push no lo reactive.
- Configuración de los dos servicios retirados preservada fuera de Git, cifrada con DPAPI del usuario en MSI.
- Código del worker verificado en GitHub antes de retirar infraestructura.
- Eliminación de recursos VPS, frontend y base cloud: pendiente de reconciliar con el recibo final. Este apartado no afirma una eliminación todavía.

## Para reconstruirlo más adelante
1. Partir del código conservado y revisar sus Dockerfiles y dependencias.
2. Si la base anterior fue eliminada, crear una base nueva y aplicar las migraciones versionadas; los datos descartados no se dan por recuperables.
3. Emitir credenciales nuevas y configurarlas por el canal de secretos; no reutilizar valores de ejemplos ni copiarlos a Git.
4. Crear los servicios necesarios y configurar sus destinos exactos. Los IDs y dominios anteriores son referencias históricas, no recursos garantizados.
5. Verificar salud, acceso a la base y el recorrido funcional con ejecución externa desactivada; la activación efectiva requiere la nueva orden de Nahuel.

## Alcance protegido
Esta limpieza se limita a los recursos propios de Trading. Los mensajes, tareas y jobs de Capataz/YO viven en infraestructura separada y se conservan.
