#!/bin/bash
# =============================================================================
# 一鍵開啟私有 Cloud Run 服務（fifa-wc-agent）
# =============================================================================
# 服務為私有（--no-allow-unauthenticated），只有被授權的 Google 帳號能存取。
# 本腳本在本機開一個代理，自動帶上你的身分，讓你用瀏覽器逛 chat 頁面。
#
# 用法：
#   ./open_app.sh           # 預設 localhost:8080
#   ./open_app.sh 9000      # 改用 localhost:9000
#
# 啟動後：開瀏覽器到 http://localhost:<PORT>，用完按 Ctrl+C 關閉。
# =============================================================================

set -euo pipefail

SERVICE="fifa-wc-agent"
REGION="asia-east1"
PORT="${1:-8080}"

# 被授權可存取的帳號（與 Cloud Run run.invoker IAM 一致），用空白分隔。
# 從環境變數讀取，避免把個人帳號寫死在版控裡：
#   export WC_ALLOWED_ACCOUNTS="you@example.com teammate@example.com"
# 留空則跳過名單檢查，直接用目前 gcloud 登入帳號嘗試連線。
ALLOWED_ACCOUNTS="${WC_ALLOWED_ACCOUNTS:-}"

# --- 檢查目前登入帳號是否在授權名單內 ---
ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
if [ -z "$ACCOUNT" ]; then
  echo "❌ 尚未登入 gcloud。請先執行： gcloud auth login" >&2
  exit 1
fi

if [ -n "$ALLOWED_ACCOUNTS" ]; then
  authorized="no"
  for a in $ALLOWED_ACCOUNTS; do
    [ "$a" = "$ACCOUNT" ] && authorized="yes"
  done
  if [ "$authorized" != "yes" ]; then
    echo "⚠️  目前登入帳號為 '$ACCOUNT'，不在 WC_ALLOWED_ACCOUNTS 名單內，連線會被 403 擋下。" >&2
    echo "    請切換到有 run.invoker 權限的帳號： gcloud config set account <你的帳號>" >&2
    echo "    （或先 gcloud auth login）" >&2
    exit 1
  fi
fi

echo "👤 帳號：$ACCOUNT"
echo "🚀 啟動代理 → http://localhost:${PORT}"
echo "   開瀏覽器到上面網址即可使用；用完在本視窗按 Ctrl+C 關閉。"
echo "-------------------------------------------------------------"

exec gcloud run services proxy "$SERVICE" --region "$REGION" --port "$PORT"
