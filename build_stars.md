# 球星建檔任務（在 Claude Code 內以 agent 執行）

目標：產出 `data/star_players.json`，涵蓋 2026 世界盃主要球隊的代表性球星。

來源（僅此兩類）：
- Wikipedia：各隊世界盃名單頁、球員個人頁（取年齡、國家隊 caps、參賽屆數）
- 新聞 web search：BBC Sport / ESPN / The Athletic（取本屆看點敘事）
- 不爬 Transfermarkt。

每位球星輸出物件：
```json
{
  "name_en": "Lionel Messi",
  "name_zh_aliases": ["梅西", "美斯"],
  "team": "Argentina",
  "age": 38,
  "caps": 190,
  "tournaments_played": 5,
  "classification": "老將",
  "one_line_insight": "可能的最後一屆，傳奇收官看點",
  "sources": ["https://en.wikipedia.org/wiki/Lionel_Messi"]
}
```
- classification：老將 | 當打 | 新秀（年齡為硬依據，資歷佐證）

分類規則：age>=32 且多屆=老將；age<=21 或首屆=新秀；其餘=當打。
輸出為合法 JSON 陣列，寫入 data/star_players.json。完成後人工抽查 5 筆。
