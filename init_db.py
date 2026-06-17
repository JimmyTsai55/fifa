import time
from db.schema import get_conn
from db.cache import cache_get
import tools.apifootball as af

THROTTLE_SEC = 7  # 守住 10 次/分（6s 剛好卡邊界、零緩衝，改 7s 留安全餘裕）


def main():
    conn = get_conn()
    teams = af._teams()
    print(f"teams: {len(teams)}")
    for t in teams:
        tid = t["team"]["id"]
        if cache_get(conn, f"squad:{tid}"):
            continue                      # 續跑：已抓過跳過
        af._squad(tid)
        print(f"squad {tid} ok")
        time.sleep(THROTTLE_SEC)
    # 收尾的 fixtures / standings 也要各自節流，否則會和最後幾筆 squad
    # 擠在同一分鐘內觸發 10 次/分限流（先前在此處爆 QuotaExhausted）。
    time.sleep(THROTTLE_SEC)
    af._fixtures(None)
    time.sleep(THROTTLE_SEC)
    af._standings(None)
    print("init done")


if __name__ == "__main__":
    main()
