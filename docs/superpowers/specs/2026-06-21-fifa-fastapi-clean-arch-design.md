# FIFA 世界盃多代理 — FastAPI 服務化（Clean Architecture）設計

日期：2026-06-21
狀態：設計定稿，待實作計畫

## 1. 目標

把現有的 CLI 多代理問答系統（OpenAI Agents SDK 驅動的 `triage_agent`）包成一個
**FastAPI HTTP 服務**，部署到 **GCP Cloud Run**，並依專案既有的 `clean-arch` 技能
（Clean Architecture + Hexagonal / Ports & Adapters）重構分層。

### 非目標（明確排除）
- 不做 SSE 串流、不做非同步任務佇列（job + 輪詢）。
- 不使用 VPC、不使用 MongoDB、不使用 Redis / Firestore 等外部狀態儲存。
- 不保留 CLI 入口。

## 2. 關鍵決策（已與使用者確認）

| 決策 | 結論 | 理由 |
|------|------|------|
| 互動模式 | 一次請求 → 回完整 JSON（同步） | 最簡單、好測試；不需 async 串流 |
| 部署目標 | GCP Cloud Run，`max-instances=1` | 簡單部署；單實例 → 免外部狀態儲存 |
| 認證 | `X-API-Key` header | 防止他人濫用、燒 OpenAI / API-Football 額度 |
| 架構 | Clean Architecture + Hexagonal，依 `clean-arch` 技能命名 | 業界標準（Uncle Bob + Cockburn），使用者既有慣例 |
| CLI | 刪除 `main.py`（CLI 入口）與 CLI 專屬測試 | 功能完整由 FastAPI 提供 |
| 儲存 | 僅 SQLite adapter，藏在 Protocol 之後 | 單實例下正確；日後換外部儲存只需新 adapter |

### 為何單實例就免外部儲存
- 額度的**真實來源**是 API-Football 回應的 `x-ratelimit-requests-remaining` header；
  本地計數只是「打 API 前的預檢」。
- 快取 TTL 很長（fixtures 6h、standings 1h、teams 30d…），實際打 API 次數很少。
- `max-instances=1` → 同一時間只有一個實例，本地 SQLite 計數即可。冷啟動歸零無妨，
  第一次真實呼叫會由 API header 校正。

## 3. 分層架構（依 `clean-arch` 技能命名）

依賴方向一律朝內：`api → use_cases → services → protocols ← adapters`；
`core/container` 在最外層做組裝（composition root）。

```
api/v1/
  routes.py        # POST /ask、GET /healthz
  deps.py          # require_api_key 認證 + 依賴注入
use_cases/
  answer_question.py     # AnswerQuestionUseCase：驗證 → 呼叫 QA engine → 回 Answer
services/
  qa_service.py          # 依賴 QAEngineProtocol
  quota_service.py       # 額度政策（每日上限、每分鐘限流），依賴 QuotaStoreProtocol
protocols/
  qa_engine.py           # QAEngineProtocol.answer(question) -> Answer
  football_data.py       # FootballDataProtocol（teams/squad/fixtures/standings/injuries/live...）
  cache_store.py         # CacheStoreProtocol（get/set with TTL）
  quota_store.py         # QuotaStoreProtocol（remaining/consume + 每分鐘限流）
adapters/
  openai_agents_adapter.py   # 實作 QAEngineProtocol：包 Runner + triage_agent + function_tools
  apifootball_adapter.py     # 實作 FootballDataProtocol（搬移自 tools/apifootball.py 抓取邏輯）
  sqlite_store_adapter.py    # 實作 CacheStore + QuotaStore
core/
  config.py        # pydantic-settings：讀環境變數
  container.py     # composition root：依設定組裝 adapter 注入 protocol
schemas/
  qa.py            # AskRequest / AskResponse
main.py            # FastAPI app 入口（取代原 CLI main.py）
Dockerfile
deploy.sh          # Cloud Run 部署腳本（已存在，需填 secrets / 對齊本專案）
```

### 各層職責對照（技能慣例）
| 層 | 可依賴 |
|----|--------|
| `api/` | use_cases, schemas |
| `use_cases/` | services, protocols |
| `services/` | protocols, schemas |
| `protocols/` | 無 |
| `adapters/` | 外部 SDK（openai-agents、httpx、sqlite3） |
| `core/` | 設定、組裝 |

### 命名慣例（技能規定）
- Protocol：`<Name>Protocol`（如 `QAEngineProtocol`）
- Adapter：`<Provider>Adapter`（如 `OpenAIAgentsAdapter`、`ApiFootballAdapter`）
- Service：`<Domain>Service`（如 `QuotaService`）
- Use Case：`<Action><Domain>UseCase`（如 `AnswerQuestionUseCase`）

## 4. 關鍵設計：依賴反轉穿過 agent 工具層

現況：`@function_tool` 直接 `import` 並呼叫 `tools/apifootball.py`（直接碰 sqlite3 + httpx）。
重構後這些工具屬於 `OpenAIAgentsAdapter` 的內部，必須改成呼叫注入的
`FootballDataProtocol`，不可直接碰 SQLite / httpx。

做法：`core/container.py` 建好 `FootballDataProtocol` 實例後，於 app 啟動（FastAPI lifespan）
呼叫 `bind_football_port(port)` 綁定到 agent 工具模組；工具函式內改呼叫被注入的 port。
如此 agent 層對 API-Football / 儲存的依賴即被反轉。

`wc_agents/`（triage、specialists、prompts）視為 `OpenAIAgentsAdapter` 的內部組件保留。
注意：agent 系統提示須維持 XML-tag 結構（既有專案慣例）。

## 5. `/ask` 請求流程

1. `require_api_key` 依賴：檢查 `X-API-Key` 是否在 `WC_API_KEYS`（env，逗號分隔）。
   缺少或不符 → **401**。
2. 驗證 `AskRequest{ question: str }`：非空、長度上限（如 ≤ 2000 字）。不符 → **422**。
3. `AnswerQuestionUseCase.execute(question)`：把阻塞的 `Runner.run_sync(triage_agent, q)`
   丟到 threadpool（`anyio.to_thread.run_sync`）執行，避免卡住 event loop。
4. 回 `AskResponse{ answer: str, model: str }`，HTTP 200。

### 錯誤對應（集中於 FastAPI exception handler）
| 例外 | HTTP | 說明 |
|------|------|------|
| 認證失敗 | 401 | 缺 / 錯 API key |
| 驗證失敗 | 422 | 問題為空或過長 |
| `QuotaExhausted` | 429 | 附 retry 提示 |
| 上游 API 失敗（RuntimeError） | 502 | API-Football 非 200 或回 errors |
| 其他未預期 | 500 | 記 log，不外洩內部訊息 |

### 健康檢查
`GET /healthz` → `200 {"status":"ok"}`，不需認證，供 Cloud Run 探活。

## 6. 設定（core/config.py，pydantic-settings）

| 環境變數 | 預設 | 用途 |
|----------|------|------|
| `OPENAI_API_KEY` | （必填） | OpenAI |
| `APIFOOTBALL_KEY` | （必填） | API-Football |
| `TAVILY_KEY` | （必填） | 新聞搜尋 |
| `WC_API_KEYS` | （必填） | 服務自身的 API key（逗號分隔可多把） |
| `OPENAI_DEFAULT_MODEL` | `gpt-4o-mini` | 驅動所有 agent |
| `WC_SEASON` | `2022` | 賽季 |
| `STORAGE_BACKEND` | `sqlite` | 預留；目前僅 sqlite |
| `PORT` | `8887` | Cloud Run 注入；uvicorn 綁 `0.0.0.0:$PORT` |

機密（前四項 + `WC_API_KEYS`）一律走 **GCP Secret Manager**，部署時用
`--update-secrets` 注入，不明文進 git 或部署指令。

## 7. 部署（GCP Cloud Run，簡單版）

- **Dockerfile**：Python 3.12 base、`pip install -r requirements.txt`（新增 `fastapi`、
  `uvicorn[standard]`、`pydantic-settings`）、`CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8887}`。
  SQLite 檔放可寫路徑（如 `/tmp`，Cloud Run 容器檔案系統為 ephemeral tmpfs，符合單實例需求）。
- **deploy.sh**（已存在，bash）：填入 `project_id` / `image_name` / `service_name` /
  `service_account`、`--update-secrets=` 填上述機密、確認 `--max-instances 1`、`--port 8887`
  與 Dockerfile 一致、`--allow-unauthenticated`（因已有 X-API-Key 層）。
  保留五步：set project → Artifact Registry 認證 → buildx build (linux/amd64) → push → run deploy。
- **無 VPC、無外部 DB**。

## 8. 測試策略

- 既有單元測試（`tests/test_apifootball*.py`、`test_cache.py`、`test_quota.py`、
  `test_web.py`、`test_stars.py`…）：搬移後更新 import，改為測 adapter 與 Protocol 契約。
- 新增 `tests/test_api.py`：FastAPI `TestClient` + 假 in-memory store + mock 掉 QA engine
  （不真打 agent / 外部 API），測 401 / 422 / 200 / 429。
- Protocol 契約測試：同一組測試同時驗 SQLite adapter（與未來任何 adapter）。
- CI（既有 `.github/workflows/ci.yml`）：matrix pytest 不變，新增依賴後仍綠。

## 9. 連帶影響與風險

- **大量檔案搬移**：tools / db / wc_agents 內容重新分配到 adapters / services / protocols；
  測試 import 需同步更新。這是選擇完整 Clean Architecture 的預期代價。
- **冷啟動額度歸零**：可接受（API header 為真實來源、快取 TTL 長）。若要更穩可將
  `min-instances` 設 1（保溫，但有成本）——預設不開。
- **teams 快取冷啟動為空**：`_find_team_id` 首次呼叫會 lazy 補上（耗 1～2 次 API）；
  維持 lazy，不在啟動時主動 seed（避免每次冷啟動燒額度）。

## 10. 交付物清單

1. `api/`、`use_cases/`、`services/`、`protocols/`、`adapters/`、`core/`、`schemas/` 分層程式碼
2. `main.py`（FastAPI app，取代 CLI）
3. `Dockerfile`
4. `deploy.sh`（對齊本專案、填 secrets 佔位）
5. 更新後的測試 + 新增 `tests/test_api.py`
6. 更新 `requirements.txt`、`.env.example`、`README.md`（啟動與部署說明）
7. 移除 CLI：原 `main.py` 的 `ask()` + `__main__`（`input()`）互動行為刪除，
   `main.py` 重新定位為 FastAPI app 入口；無其他 CLI 專屬碼或測試
</content>
</invoke>
