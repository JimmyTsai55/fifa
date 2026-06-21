import time
import config
from adapters.apifootball_adapter import ApiFootballAdapter
from adapters.sqlite_store_adapter import SqliteStoreAdapter
from services.quota_service import QuotaService

THROTTLE_SEC = 7  # 守住 10 次/分（6s 剛好卡邊界、零緩衝，改 7s 留安全餘裕）


def main():
    store = SqliteStoreAdapter(config.DB_PATH)
    quota = QuotaService(store)
    af = ApiFootballAdapter(store, quota)

    teams = af.teams()
    print(f"teams: {len(teams)}")
    for t in teams:
        tid = t["team"]["id"]
        if store.peek(f"squad:{tid}"):
            continue                      # 續跑：已抓過跳過
        af.squad(tid)
        print(f"squad {tid} ok")
        time.sleep(THROTTLE_SEC)
    # 收尾的 fixtures / standings 也要各自節流，否則會和最後幾筆 squad
    # 擠在同一分鐘內觸發 10 次/分限流（先前在此處爆 QuotaExhausted）。
    time.sleep(THROTTLE_SEC)
    af.fixtures(None)
    time.sleep(THROTTLE_SEC)
    af.standings(None)
    print("init done")


if __name__ == "__main__":
    main()
