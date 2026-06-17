import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LEAGUE_ID = 1
SEASON = 2026

DAILY_QUOTA = 100
PER_MIN = 10

# TTL（秒）
TTL = {
    "teams": 30 * 86400,
    "squad": 86400,
    "fixtures": 6 * 3600,
    "standings": 3600,
    "injuries": 3 * 3600,
}

NEWS_DOMAINS = [
    "bbc.com/sport",
    "espn.com",
    "theathletic.com",
    "goal.com",
    "fifa.com",
]

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cache.db"
STAR_JSON_PATH = DATA_DIR / "star_players.json"

API_BASE = "https://v3.football.api-sports.io"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
APIFOOTBALL_KEY = os.getenv("APIFOOTBALL_KEY", "")
TAVILY_KEY = os.getenv("TAVILY_KEY", "")

DATA_DIR.mkdir(exist_ok=True)
