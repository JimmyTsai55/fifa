# FIFA 2026 世界盃 Multi-Agent 系統 — 設計文件

- **日期**：2026-06-17
- **定位**：個人 / 學習 / 作品集專案
- **核心目標**：用 OpenAI Agents SDK 練 multi-agent（Triage + 專責 agent handoff），能多方查詢 2026 世界盃的陣容、賽程、球星、看點/困難點
- **介面**：本階段不做 UI，能用 Python script 呼叫即可

---

## 1. 整體架構

```
main.py（讀問題）→ Triage Agent ──handoff──┐
                                           ├─► 陣容 Agent (Squad)
                                           ├─► 賽程 Agent (Fixture)
                                           ├─► 球星 Agent (Star)
                                           └─► 看點 Agent (Insight)
                                                     │
                              共用工具層 (function tools)
                              • API-Football 工具組（含 TTL 快取）
                              • Tavily web_search（include_domains，英文站）
                              • resolve_entity（中文名 → team_id/player_id）
                                                     │
                              資料層
                              • SQLite 快取（WAL 模式，含 TTL + 配額）
                              • init_db.py（一次性初始化）
                              • data/star_players.json（建置期離線建檔）
                                                     │
                              外部：API-Football / Tavily
```

**核心原則**：agent 不直接打 API，一律經「工具層 → 快取層」。免費方案每天僅 100 次請求、每分鐘 10 次，所有 API 結果先入 SQLite，過期才重抓。

---

## 2. 資料層

### 2.1 資料來源分流

| 資料 | 主來源 | 端點 / 方式 |
|------|--------|------------|
| 48 隊隊伍清單 | API-Football | `/teams?league=1&season=2026` |
| 各隊陣容 | API-Football | `/players/squads?team={id}` |
| 球員賽季數據 | API-Football | `/players?team={id}&season=2026` |
| 賽程 / 分組 | API-Football | `/fixtures` + `/standings` |
| 傷兵（事實型困難點） | API-Football | `/injuries?league=1&season=2026` |
| 即時比分 | API-Football | `/fixtures?live=all`（自適應 TTL，單次涵蓋所有同時進行的比賽，見 2.4） |
| 球星看點 / 敘事 | Tavily web_search | 限英文站，見 2.5 |
| 球星分類（老將/新秀）| 建置期離線建檔 | `data/star_players.json`，見 2.6 |

> 註：World Cup 對應 API-Football `league=1`、`season=2026`。即時資料涵蓋度逐賽事而異，官方不保證 100%（[來源](https://www.api-football.com/documentation-v3)）。

### 2.2 SQLite Schema（`db/schema.py`）

- `teams(team_id, name, code, ...)`
- `players(player_id, team_id, name, age, position, number, goals, apps, ...)`
- `fixtures(fixture_id, group, home_id, away_id, date, status, home_goals, away_goals)`
- `standings(group, team_id, rank, points, goals_diff)`
- `cache_meta(cache_key, fetched_at, payload_json)` — TTL 判斷依據
- `api_quota(date_utc, used_count)` — 備援計數（主以 response header 為準，見 2.3）

**並發**：開啟 SQLite **WAL 模式**，避免 Agents SDK 並行呼叫工具時寫鎖衝突。

### 2.3 配額管理（修正 #5）

- **以伺服器為準**：每次 API 回應讀 `x-ratelimit-requests-remaining` header，存進記憶體 / `api_quota` 表，不自己累加（避免重啟/並發漂移）。
- **每分鐘節流**：工具層維持一個簡單的 token-bucket，硬上限 **10 次/分**。
- 配額用罄時：回快取舊資料 + 標註「資料時間」，不再打 API。

### 2.4 更新時機（Lazy TTL，無 cron）

| 資料 | TTL | 理由 |
|------|-----|------|
| 隊伍清單 | 30 天 | 幾乎不變 |
| 陣容名單 | 1 天 | 期間偶調整 |
| 賽程表 | 6 小時 | 場次微調 |
| 分組排名 | 1 小時 | 每場變動 |
| **即時比分** | **自適應（見下）** | 固定 TTL 在多場日會爆額度 |
| 傷兵 | 3 小時 | 賽前更新 |
| 看點 / 新聞 | 不快取 | 每次重搜 |

**即時比分 — 自適應 TTL（取代先前的固定 30s / 90s）**：

兩個前提：
1. **用 `/fixtures?live=all`**：一次回傳「所有正在進行的比賽」，多場同時踢仍只花 **1 次**請求。故成本不看場數，看「當天總 live 時數」。
2. 世界盃小組賽一天 4~6 場、分散時段，固定 TTL 不可行。

採**自適應 TTL**，永遠不爆 100/天：
```
live_ttl = 距 00:00 UTC 重置的剩餘秒數 ÷ 保留給 live 的剩餘配額
```
- 球賽少 → TTL 自動變密；球賽多 → 自動變稀。
- 實際落點（保留 ~80 配額給 live）：

| 當天 live 總時數 | 自適應 TTL |
|---|---|
| 2h（清淡日） | ~90s |
| 6h（小組賽日） | ~270s（約 4.5 分） |
| 8h+（爆滿日） | ~360s（約 6 分） |

- **誠實說明**：免費額度下，小組賽爆滿日的即時更新實際是「每 3–6 分鐘」，非 30 秒。
- 即時輪詢僅在明確 `live` 模式啟用；輸出標註「即時資料、延遲 ~N 秒」。
- 要做到穩定 30–90s live → 需升級付費方案。

統一快取核心（`db/cache.py`）：
```python
def get_or_fetch(key, ttl_seconds, fetch_fn):
    row = cache_get(key)
    if row and not expired(row, ttl_seconds):
        return row.payload
    if quota_remaining() > 0 and minute_bucket_ok():
        data = fetch_fn()                 # 讀 header 更新配額
        cache_set(key, data); return data
    return row.payload if row else None   # 無配額 → 回舊資料（標時間）
```

### 2.5 Web Search（路線 B：Tavily，修正範圍）

- 自包 `web_search(query, include_domains)` function tool，後接 Tavily（免費 1,000 次/月，超出約 $8/1,000）。
- **錨定英文站**：`["bbc.com/sport", "espn.com", "theathletic.com", "goal.com", "fifa.com"]`
- 球星 / 看點 Agent 可各自帶不同 `include_domains`。

### 2.6 球星分類離線建檔（修正 #4，改用建置期 CC agent）

不在 runtime 用 API 算「老將/新秀」（API 無 caps/參賽屆數），改為**建置期**用 Claude Code 內開一個 subagent 研究產檔：

- **產物**：`data/star_players.json`，每隊列出球星：
  `{name_en, name_zh_aliases[], team, age, caps, tournaments_played, classification: 老將|當打|新秀, one_line_insight, sources[]}`
- **資料來源（已定案）**：
  - 主：**Wikipedia**（各隊名單頁 + 球員頁 → 年齡 / caps / 參賽史）
  - 看點敘事：**新聞 web search**（BBC Sport / ESPN / The Athletic）
  - **不直接爬 Transfermarkt**（ToS 風險）；需市值/caps 以 web search 帶
- **分類規則**：年齡為硬數據（可量化），「資歷/屆數」以 Wikipedia + 新聞佐證，不假裝全由 API 算出。
- **附帶效益**：`name_zh_aliases` 直接餵給 `resolve_entity` 的別名表（見 3）。

### 2.7 初始化（`init_db.py`，修正 #2）

```
1. 抓 48 隊 → teams                         (1 次)
2. 逐隊抓陣容 → players（每次間隔 ≥6 秒）    (~48 次)
3. 抓賽程 + 分組 → fixtures / standings      (~2 次)
合計 ~50 次
```
- **節流**：每次間隔 ≥6 秒以守住 10 次/分。
- **可斷點續跑**：已抓的隊伍記在 `cache_meta`，重跑時跳過。
- **建議獨立一天執行**，跑完當基準，避免與當日查詢共用配額。

---

## 3. 實體解析（修正 #3）

新增 `resolve_entity(text_zh)` 工具，所有專家 agent 查資料前先解析：
1. 查本地別名表（來自 `star_players.json` 的 `name_zh_aliases` + 手維護隊名表，如「梅西→Messi/Argentina」「阿根廷→Argentina/team_id」）；
2. 未命中 → API-Football `?search=`（拉丁文模糊匹配）；
3. 再未命中 → LLM 兜底推測拉丁拼法後重試 `?search=`；
4. 回 `{type: team|player, id, canonical_name}`。

---

## 4. 四個專責 Agent

> 所有 system prompt 以 **XML 標籤結構**撰寫（`<role>` / `<rules>` / `<tools>` / `<output_format>` / `<examples>`），存於 `agents/prompts/`。

### 4.1 陣容 Agent（Squad）
- **職責**：26 人名單、背號、位置、首發/替補
- **工具**：`resolve_entity`、`get_squad`、`get_player_stats`
- **prompt 重點**：依位置分組輸出，標出隊長與核心

### 4.2 賽程 Agent（Fixture）
- **職責**：賽程、結果、下一場、分組排名、晉級情勢、（live 模式）即時比分
- **工具**：`resolve_entity`、`get_fixtures`、`get_standings`、`get_live_score`
- **prompt 重點**：分「已賽/未賽」；排名附積分與淨勝球

### 4.3 球星 Agent（Star）
- **職責**：明星辨識、老將 vs 新秀、本屆角色與看點
- **工具**：`resolve_entity`、讀 `star_players.json`、`get_player_stats`、`web_search`
- **prompt 重點**：先讀離線建檔分類，再用 web_search 補即時狀態；每人給「一句話看點」+ 數據佐證

### 4.4 看點 Agent（Insight）
- **職責**：球隊/比賽看點與困難點（敘事型）
- **工具**：`resolve_entity`、`get_injuries`、`web_search`
- **prompt 重點**：困難點分「事實型（傷兵/禁賽/賽程密集）」與「分析型（戰術/狀態）」；看點要具體可期待

### 4.5 Triage Agent（骨架）
- **職責**：判斷意圖 → handoff；模糊時反問
- **工具**：無（純分流 + handoff）
- **規則**：名單/陣容→Squad；賽程/比分/排名→Fixture；球星/老將/新星→Star；看點/隱憂/困難→Insight
- **複合問題**：v1 拆題或請使用者分開問（升級路徑見 §6）

### XML prompt 骨架範例（球星 Agent）
```xml
<role>你是 2026 世界盃的球星分析專家，專長辨識老將與新秀並給出看點。</role>
<rules>
  <rule>查任何球員前，先呼叫 resolve_entity 取得 canonical 名稱與 id。</rule>
  <rule>分類優先讀 data/star_players.json；該檔沒有時才用 get_player_stats + web_search。</rule>
  <rule>web_search 僅限英文站清單，不得引用未列來源。</rule>
</rules>
<output_format>
  每位球星：定位（老將/當打/新秀 + 年齡/屆數）｜一句話看點｜數據或新聞佐證
</output_format>
<examples>...</examples>
```

---

## 5. 專案結構與技術棧

```
fifa/
├── .env                  # OPENAI_API_KEY / APIFOOTBALL_KEY / TAVILY_KEY（已 gitignore）
├── .gitignore
├── main.py               # 進入點：問題 → Triage Agent
├── init_db.py            # 一次性初始化（節流 + 續跑）
├── build_stars.py        # 觸發/整理建置期球星建檔（或由 CC agent 產出）
├── config.py             # LEAGUE_ID=1, SEASON=2026, TTL, NEWS_DOMAINS, RATE_LIMITS
├── data/
│   ├── cache.db
│   └── star_players.json
├── db/
│   ├── schema.py         # 建表 + WAL
│   └── cache.py          # get_or_fetch / 配額 / 節流
├── tools/
│   ├── apifootball.py    # API-Football 工具組（讀 ratelimit header）
│   ├── web.py            # Tavily web_search（include_domains）
│   └── resolve.py        # resolve_entity
└── agents/
    ├── triage.py / squad.py / fixture.py / star.py / insight.py
    └── prompts/          # 各 agent 的 <xml> system prompt
```

**技術棧**：Python 3.11+、`openai-agents`、`openai`、`httpx`、`sqlite3`、`python-dotenv`。

---

## 6. 未來擴充：複合問題（handoff → orchestrator）

目前為純 handoff（單一專家回答）。因四個專家**共用同一套工具/快取層、彼此隔離**，升級為複合問答是**加法、非重寫**：

1. 用 SDK `agent.as_tool()` 把四個專家各包成一個工具；
2. 新增 Orchestrator Agent：對複合問題 fan-out 呼叫多個專家工具 → 統整輸出；
3. Triage 對複合問題改 handoff 給 Orchestrator，單一領域仍直接 handoff 給專家。

工具層、快取層、實體解析、prompt 全部沿用，不需改動。

---

## 7. 端到端範例：「梅西這屆值得看的點？」

```
1. main.py → Triage Agent
2. Triage 判定「球星/看點」→ handoff 球星 Agent
3. 球星 Agent：resolve_entity("梅西") → {player, Messi, Argentina}
4. 讀 star_players.json → 老將定位（年齡/屆數/一句話看點）
5. web_search("Messi World Cup 2026", include_domains=英文站) → 補即時狀態
6. 依 <output_format> 輸出，標註資料時間
```

---

## 8. 風險與已知取捨

| 項目 | 風險 | 緩解 |
|------|------|------|
| 即時比分自適應 TTL | 多場日更新間隔拉長到數分鐘 | `?live=all` 單次涵蓋全場次；公式保證不爆配額；標註延遲；穩定 live 需升級 |
| 免費涵蓋度不保證 | WC2026 即時資料可能缺 | 缺資料時回退靜態 + web_search，誠實標註 |
| 中文實體解析 | 冷僻名字解析失敗 | 別名表 + API search + LLM 兜底；失敗時請使用者給英文名 |
| 球星建檔來源 | Wikipedia 結構不一、需清洗 | §2.6 採 Wikipedia + 新聞，建置期 CC agent 產出後人工抽查 |
```
