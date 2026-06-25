# FIFA 2026 世界盃 Multi-Agent 問答系統

用 **OpenAI Agents SDK** 打造的多代理（multi-agent）系統，可多方查詢 2026 世界盃的**陣容、賽程、球星看點、困難點**。一個 Triage agent 判斷意圖後，handoff 給四個專責 agent；所有外部資料經 SQLite 快取，守住 API-Football 免費額度。

服務以 **FastAPI（Clean Architecture / 依賴反轉）** 提供 HTTP API，並附一個瀏覽器聊天頁面，最後以 **GitHub Actions CI/CD** 自動部署到 **Cloud Run（私有）**。

```
瀏覽器 chat.html ─► POST /chat ─┐
X-API-Key 用戶端 ─► POST /ask ──┤
                                 ▼
                          AnswerQuestionUseCase
                                 │
使用者問題 → Triage Agent ──handoff──┬─► 陣容 Agent (Squad)
                                     ├─► 賽程 Agent (Fixture)
                                     ├─► 球星 Agent (Star)
                                     └─► 看點 Agent (Insight)
                                          │
              adapters/ ── API-Football · Tavily 新聞 · 中文名解析
                                          │
              SQLite TTL 快取 · 每日配額 / 每分鐘限流
```

## 需要的 API Key（三把）

| 變數 | 用途 | 取得 |
|------|------|------|
| `OPENAI_API_KEY` | 驅動 agent | platform.openai.com |
| `APIFOOTBALL_KEY` | 陣容/賽程/數據/傷兵 | api-football.com（免費方案 100 次/天、10 次/分） |
| `TAVILY_KEY` | 英文新聞搜尋（看點） | tavily.com（免費 1,000 次/月） |

另有 `WC_API_KEYS`（逗號分隔的字串）作為 `/ask` 端點的 `X-API-Key` 白名單，用來保護需要驗證的後端入口。

## 安裝

```bash
cd /Users/Jimmy_1/fifa
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # 填入上面的 key
```

## 初始化資料（第一次必跑）

把 48 隊的隊伍/陣容/賽程灌進本地 SQLite 快取。會打約 50 次 API（已內建每 6 秒節流以守住「10 次/分」），**建議獨立一天執行**，避免和當天查詢共用配額。中斷後重跑會跳過已抓的隊伍。

```bash
python init_db.py
```

### （選用）建立球星看點檔

老將/新秀分類與看點故事不在 API 內，改在 **Claude Code** 內開一個 agent，依 [`build_stars.md`](build_stars.md) 的指示用 Wikipedia + 新聞產出 `data/star_players.json`。沒有這個檔系統仍可運作，只是球星 Agent 會改用即時 web search 補。

## 啟動服務

> **注意：CLI（`python main.py`）已移除，`main.py` 現在是 FastAPI app。服務為純 HTTP API。**

本地啟動（開發用）：

```bash
uvicorn main:app --reload --port 8887
```

### 端點一覽

| 方法 | 路徑 | 說明 | 驗證 |
|------|------|------|------|
| `GET` | `/` | 聊天網頁（`static/chat.html`） | 無 |
| `POST` | `/chat` | 前端入口，API key 留在伺服器端，瀏覽器看不到 | 無 |
| `POST` | `/ask` | 後端入口，需帶 `X-API-Key` | `WC_API_KEYS` 白名單 |
| `GET` | `/healthz` | 健康檢查 | 無 |
| `GET` | `/openapi.json` | OpenAPI schema（CI smoke test 用） | 無 |

`/chat` 與 `/ask` 共用同一個 `AnswerQuestionUseCase`，因此 `main.py` 的例外處理（配額 429 / 驗證 422 / 上游錯誤 502）對兩者一致生效。

呼叫 `/ask`：

```bash
curl -H "X-API-Key: <your-api-key>" \
     -H "Content-Type: application/json" \
     -d '{"question":"阿根廷這次帶哪些人？"}' \
     http://localhost:8887/ask
```

打開瀏覽器到 `http://localhost:8887/` 即可用聊天頁面（走公開的 `/chat`，不需 key）。

## 前端聊天頁

`static/chat.html` 是單檔的世界盃風格聊天介面（Noto Sans/Serif TC + Anton，綠茵 + 金色配色），由 `GET /` 直接吐出，向公開的 `POST /chat` 送問題。由於 API key 全在伺服器端，瀏覽器端不需要、也拿不到任何金鑰。

## 部署（Cloud Run，私有）

服務以 **`--no-allow-unauthenticated`** 部署為**私有**：Cloud Run 的 IAM 層會擋下所有匿名請求（回 403），只有被授予 `run.invoker` 的 Google 帳號能存取。

1. 在 GCP Secret Manager 建立以下 Secret（若尚未存在）：

   ```bash
   echo -n "$OPENAI_API_KEY"   | gcloud secrets create OPENAI_API_KEY   --data-file=-
   echo -n "$APIFOOTBALL_KEY"  | gcloud secrets create APIFOOTBALL_KEY  --data-file=-
   echo -n "$TAVILY_KEY"       | gcloud secrets create TAVILY_KEY       --data-file=-
   echo -n "key1,key2"         | gcloud secrets create WC_API_KEYS      --data-file=-
   ```

2. 複製範本並填入你的部署設定（`gcp_Dev.sh` 已被 `.gitignore`，含環境專屬設定不進版控）：

   ```bash
   cp gcp_Dev.sh.example gcp_Dev.sh
   # 填入 gcp_Dev.sh 頂部的 project_id、image_name、service_name、service_account
   bash gcp_Dev.sh
   ```

   部署採 **單實例**（`--max-instances 1`），以確保 API-Football 每日 100 次配額的計數正確（SQLite 為唯一的每日配額儲存）。若需水平擴展，需改用外部配額儲存（如 Redis / Firestore）。

### 開啟私有服務（`open_app.sh`）

服務是私有的，無法用瀏覽器直接連。`open_app.sh` 會在本機開一個帶身分的代理，讓你逛聊天頁面：

```bash
./open_app.sh           # 預設 http://localhost:8080
./open_app.sh 9000      # 改用 localhost:9000
```

腳本會先檢查目前 `gcloud` 登入帳號是否在授權名單內（預設 `your-account@example.com`，與 Cloud Run 的 `run.invoker` IAM 一致），通過才啟動 `gcloud run services proxy`。用完按 `Ctrl+C` 關閉。

## CI/CD（GitHub Actions）

| 工作流程 | 觸發 | 做什麼 |
|----------|------|--------|
| `.github/workflows/ci.yml` | push 任何分支、對 main 開 PR | 在 Python 3.12 / 3.13 矩陣上跑 `pytest` |
| `.github/workflows/deploy.yml` | push 到 `main` | 先過測試閘門 → 用 **WIF（Workload Identity Federation）無金鑰認證** → `gcloud run deploy --source .` → 私有部署 → smoke test |

部署用 WIF 換取 OIDC token，無需把 service account 金鑰存進 GitHub。Smoke test 對已部署的 URL 打匿名 `GET /`，因為服務私有，**回 403 正好證明鎖定生效且 revision 已上線**——故接受 `2xx / 401 / 403` 為成功，只有 `5xx / 000` 才算失敗。

## 即時比分與免費額度

即時比分用 `/fixtures?live=all`（一次回所有進行中的比賽），更新間隔為**自適應 TTL**：

```
TTL = 距 UTC 午夜重置的剩餘秒數 ÷ 保留給 live 的配額
```

這保證**無論一天幾場都不會爆 100 次/天**；代價是小組賽爆滿日的更新間隔會拉長到數分鐘。要做到穩定的 30–90 秒即時更新需升級 API-Football 付費方案。

## 專案結構（Clean Architecture）

依賴方向一律由外向內指向 `core` / `protocols`，外層（adapters、api）可替換而不動內層。

```
config.py            常數：League/Season/TTL/新聞網域/額度 + 讀 .env
main.py              FastAPI app：掛 router + 例外處理（429 / 422 / 502）
api/v1/
  routes.py          路由：/ /chat /ask /healthz
  deps.py            DI：build_use_case 單例 + require_api_key 驗證
schemas/qa.py        AskRequest / AskResponse（Pydantic）
use_cases/
  answer_question.py AnswerQuestionUseCase（一個問題 → 一個答案）
services/
  qa_service.py      把阻塞引擎丟到 threadpool 跑
  quota_service.py   配額服務 + QuotaExhausted 例外
protocols/           介面（依賴反轉的抽象邊界）
  qa_engine.py · football_data.py · cache_store.py · quota_store.py
core/container.py    composition root：組裝 adapters → use case
adapters/            介面的具體實作
  openai_agents_adapter.py   QAEngine：Triage + 四專家 agent
  apifootball_adapter.py     API-Football 請求 + function tools + 自適應 live TTL
  news_adapter.py            Tavily web search（限英文新聞站）
  resolve_adapter.py         resolve_entity（中文名 → 拉丁名）
  stars_adapter.py           讀 data/star_players.json
  sqlite_store_adapter.py    SQLite TTL 快取（WAL + RLock 序列化寫入）
  agent_tools.py             包裝給 agent 用的 function tools
wc_agents/           （注意：不可命名為 agents/，會遮蔽 OpenAI SDK）
  prompts.py         5 份 XML 結構 system prompt
  specialists.py     Squad / Fixture / Star / Insight 四個 agent
  triage.py          Triage agent（handoffs）
static/chat.html     瀏覽器聊天頁面
init_db.py           一次性初始化（節流 + 可續跑）
docs/superpowers/    設計 spec 與實作計畫
.github/workflows/   ci.yml（測試矩陣）+ deploy.yml（WIF → Cloud Run）
```

## 測試

```bash
pytest -q          # 62 個測試，全程用 mock，不需 API key
```

## 簡報

`presentation.html` 是單檔技術簡報（〈FIFA 2026 多代理 QA 系統 — 技術簡報〉），用瀏覽器直接打開即可播放。

## 設計文件

- 設計：`docs/superpowers/specs/2026-06-17-fifa-worldcup-multi-agent-design.md`
- 實作計畫：`docs/superpowers/plans/2026-06-17-fifa-worldcup-multi-agent.md`

未來擴充（複合問題、把專家當工具的 Orchestrator）見 spec §6。
