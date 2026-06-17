import time
from db.schema import get_conn
from db.cache import cache_get
import tools.apifootball as af

THROTTLE_SEC = 6  # 守住 10 次/分


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
    af._fixtures(None)
    af._standings(None)
    print("init done")


if __name__ == "__main__":
    main()
