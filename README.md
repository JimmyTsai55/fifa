# FIFA 2026 世界盃 Multi-Agent 問答系統

用 **OpenAI Agents SDK** 打造的多代理（multi-agent）系統，可多方查詢 2026 世界盃的**陣容、賽程、球星看點、困難點**。一個 Triage agent 判斷意圖後，handoff 給四個專責 agent；所有外部資料經 SQLite 快取，守住 API-Football 免費額度。

```
使用者問題 → Triage Agent ──handoff──┬─► 陣容 Agent (Squad)
                                     ├─► 賽程 Agent (Fixture)
                                     ├─► 球星 Agent (Star)
                                     └─► 看點 Agent (Insight)
                                          │
              工具層 tools/ ── API-Football · Tavily 新聞 · 中文名解析
                                          │
              資料層 db/ ──── SQLite TTL 快取 · 配額/限流
```

## 需要的 API Key（三把）

| 變數 | 用途 | 取得 |
|------|------|------|
| `OPENAI_API_KEY` | 驅動 agent | platform.openai.com |
| `APIFOOTBALL_KEY` | 陣容/賽程/數據/傷兵 | api-football.com（免費方案 100 次/天、10 次/分） |
| `TAVILY_KEY` | 英文新聞搜尋（看點） | tavily.com（免費 1,000 次/月） |

## 安裝

```bash
cd /Users/Jimmy_1/fifa
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # 填入上面三把 key
```

## 初始化資料（第一次必跑）

把 48 隊的隊伍/陣容/賽程灌進本地 SQLite 快取。會打約 50 次 API（已內建每 6 秒節流以守住「10 次/分」），**建議獨立一天執行**，避免和當天查詢共用配額。中斷後重跑會跳過已抓的隊伍。

```bash
python init_db.py
```

### （選用）建立球星看點檔

老將/新秀分類與看點故事不在 API 內，改在 **Claude Code** 內開一個 agent，依 [`build_stars.md`](build_stars.md) 的指示用 Wikipedia + 新聞產出 `data/star_players.json`。沒有這個檔系統仍可運作，只是球星 Agent 會改用即時 web search 補。

## 啟動服務

> **注意：CLI（`python main.py`）已移除，服務改為 HTTP API。**

本地啟動（開發用）：

```bash
uvicorn main:app --reload --port 8887
```

呼叫 `/ask` 端點：

```bash
curl -H "X-API-Key: <your-api-key>" \
     -H "Content-Type: application/json" \
     -d '{"question":"阿根廷這次帶哪些人？"}' \
     http://localhost:8887/ask
```

## 部署（Cloud Run）

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

   部署採 **單實例**（`--max-instances 1`），以確保 API-Football 每日 100 次配額的計數正確。若需水平擴展，需改用外部配額儲存（如 Redis / Firestore）。

## 即時比分與免費額度

即時比分用 `/fixtures?live=all`（一次回所有進行中的比賽），更新間隔為**自適應 TTL**：

```
TTL = 距 UTC 午夜重置的剩餘秒數 ÷ 保留給 live 的配額
```

這保證**無論一天幾場都不會爆 100 次/天**；代價是小組賽爆滿日的更新間隔會拉長到數分鐘。要做到穩定的 30–90 秒即時更新需升級 API-Football 付費方案。

## 專案結構

```
config.py            常數：League/Season/TTL/新聞網域/額度 + 讀 .env
db/
  schema.py          SQLite 建表 + WAL + 連線單例
  cache.py           get_or_fetch（TTL + 過期時回舊資料的 fallback）
  quota.py           每日配額（讀 ratelimit header）+ 每分鐘 RateLimiter
tools/
  apifootball.py     API-Football 請求層 + 7 個 function tool + 自適應 live TTL
  resolve.py         resolve_entity（中文名 → 拉丁名）
  web.py             Tavily web_search（限英文新聞站）
  stars.py           讀取 data/star_players.json
wc_agents/           （注意：不可命名為 agents/，會遮蔽 OpenAI SDK）
  prompts.py         5 份 XML 結構 system prompt
  specialists.py     Squad / Fixture / Star / Insight 四個 agent
  triage.py          Triage agent（handoffs）
main.py              CLI 進入點
init_db.py           一次性初始化（節流 + 可續跑）
docs/superpowers/    設計 spec 與實作計畫
```

## 測試

```bash
pytest -q          # 35 個單元測試，全程用 mock，不需 API key
```

## 設計文件

- 設計：`docs/superpowers/specs/2026-06-17-fifa-worldcup-multi-agent-design.md`
- 實作計畫：`docs/superpowers/plans/2026-06-17-fifa-worldcup-multi-agent.md`

未來擴充（複合問題、把專家當工具的 Orchestrator）見 spec §6。
