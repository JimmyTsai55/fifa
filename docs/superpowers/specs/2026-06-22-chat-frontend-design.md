# 前端問答頁面設計 (Chat Frontend)

日期:2026-06-22
狀態:已核准,待實作

## 目標

為既有的「2026 世界盃 Multi-Agent 問答系統」加上一個簡單的前端頁面,
風格類似現代 AI 對話介面 (ChatGPT 風格),並以浮動提示文字引導使用者
知道可以輸入什麼樣的問題。

## 既有後端 (不更動)

- `POST /ask`,Body `{ "question": str }`,回 `{ "answer": str, "model": str }`。
- 需要 `X-API-Key` header 驗證 (`api/v1/deps.py:require_api_key`)。
- 例外處理已在 `main.py`:`QuotaExhausted→429`、`ValueError→422`、`RuntimeError→502`。
- `use_case.execute(question)` 為核心問答邏輯,完全不動。

## 架構

```
瀏覽器 (單頁 chat.html)
   │  POST /chat   { "question": "..." }      ← 不帶任何金鑰
   ▼
FastAPI 新增路由
   ├─ GET  /          → 回傳靜態 chat 頁面
   └─ POST /chat      → server 端呼叫既有 use_case,回 { answer, model }
   ▼
既有 use_case.execute()  (完全不動)
```

### 關鍵決策

1. **API Key 處理 — 後端代理。**
   `/chat` 在 server 端執行,直接呼叫既有 `get_use_case().execute()`,
   不暴露任何金鑰給瀏覽器。`/chat` 本身**不要求** `X-API-Key`
   (它就是公開的前端入口);受金鑰保護的 `/ask` 維持原狀供外部程式使用。
   - `/chat` 沿用既有的例外型別,因此 `QuotaExhausted/ValueError/RuntimeError`
     的 429/422/502 處理自動適用。

2. **前端形式 — 單一靜態檔。**
   一個 `static/chat.html`,內嵌 CSS + 原生 JS,無打包、無 React。
   由 FastAPI 直接 serve (`GET /`)。部署零額外步驟。

3. **對話呈現 — 滾動對話串流。**
   ChatGPT 風格,前端累積顯示多輪問答氣泡。
   **後端維持無狀態**:每次 `/chat` 為獨立問答,不帶上下文。

## 畫面規格

### 空狀態歡迎頁
- 中央標題 + 副標。
- 4 張**浮動提示卡** (輕微上下浮動 CSS 動畫),點擊即帶入該問題並送出:
  - 🧑‍🤝‍🧑 陣容:「巴西隊最新的世界盃陣容有誰?」
  - 📅 賽程:「阿根廷下一場比賽是什麼時候?」
  - ⭐ 球星:「梅西這屆世界盃的看點是什麼?」
  - 🔍 看點:「法國和西班牙哪一隊奪冠機會大?」

### 對話區
- 使用者氣泡靠右、AI 氣泡靠左,滾動累積。
- 送出後在 AI 側顯示「思考中…」載入動畫,回應後取代之。
- AI 答案下方以小字顯示使用的 `model`。
- 錯誤 (429/422/502/網路) 以系統氣泡顯示友善訊息。

### 輸入區
- 底部固定輸入框 + 送出鈕,Enter 送出 (Shift+Enter 換行)。
- placeholder **輪播**提示文字,例:
  「試試問:德國隊的傷兵名單…」/「日本隊的分組對手有誰?…」等。
- 送出中停用輸入,避免重複送出 (亦配合後端單實例配額)。

### 視覺
- 乾淨淺色底、圓角氣泡、單一強調色 (世界盃綠)。
- RWD 手機可用。

## 範圍外 (YAGNI)

- 不做登入 / 帳號。
- 不做多輪上下文記憶 (後端本就無狀態)。
- 不做歷史持久化。
- 不做逐字串流輸出 (一次回完即可)。

## 測試

- 後端:`tests/test_web.py` 或新增測試,覆蓋 `GET /` 回 200 HTML、
  `POST /chat` 成功回 `{answer, model}`、配額耗盡回 429。
- 前端:手動驗證空狀態、送出、載入、錯誤訊息、提示卡點擊、placeholder 輪播。
