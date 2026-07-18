# Config Safety — не ломай конфиги

## Главное правило
**Перед ЛЮБОЙ правкой конфигурационных файлов агентов** (.jsonc, .json, .yaml, .yml, .toml):
1. `firecrawl_search` найти актуальную документацию (не гадать URL через webfetch)
2. Сверить ВСЕ ключи с примерами из документации
3. После записи — `read` файла, сверить с документацией повторно
4. Проверить индикатор/статус инструмента (TUI badge, `pm2 status`, etc.)

## Критические файлы
- `~/.config/kilo/kilo.jsonc` — конфиг Kilo (indexing, MCP, providers, agents)
- `~/.config/opencode/opencode.json` — конфиг OpenCode
- `~/.hermes/config.yaml` — конфиг Hermes
- `kilo.jsonc` в корне проекта
- `.env` и `ecosystem.config.js` на серверах

## Документация по первому требованию
| Инструмент | Docs URL |
|---|---|
| Kilo Code Indexing | https://kilo.ai/docs/customize/context/codebase-indexing |
| Kilo Config (общий) | https://kilo.ai/docs/customize |
| Kilo MCP Servers | https://kilo.ai/docs/automate/tools |
| Kilo Agents/Custom Subagents | https://kilo.ai/docs/customize/custom-subagents |
| OpenCode Config | https://opencode.ai/docs/config |
| Hermes Config | ~/.hermes/config.yaml (встроенная справка) |

## Провайдеры: ключи конфигурации
- ВСЕГДА использовать точное имя провайдера как ключ (с дефисами, без camelCase)
- `openai-compatible` → ключ `"openai-compatible"`, НЕ `"openaiCompatible"`
- `vercel-ai-gateway` → ключ `"vercel-ai-gateway"`
- Проверять в документации, не придумывать

## Анти-паттерны
- ❌ `webfetch` с guessed URL → 404
- ❌ Писать ключи по памяти/аналогии
- ❌ Пропускать verification-step после edit
- ✅ `firecrawl_search` → найти docs → `firecrawl_scrape` → сверить → edit → verify
