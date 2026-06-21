from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    OPENAI_API_KEY: str = ""
    APIFOOTBALL_KEY: str = ""
    TAVILY_KEY: str = ""
    WC_API_KEYS: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    WC_SEASON: int = 2022
    STORAGE_BACKEND: str = "sqlite"
    PORT: int = 8887


settings = _Settings()

# --- 向後相容的模組級常數（既有程式以 config.X 取用） ---
OPENAI_API_KEY = settings.OPENAI_API_KEY
APIFOOTBALL_KEY = settings.APIFOOTBALL_KEY
TAVILY_KEY = settings.TAVILY_KEY
OPENAI_DEFAULT_MODEL = settings.OPENAI_DEFAULT_MODEL
SEASON = settings.WC_SEASON
STORAGE_BACKEND = settings.STORAGE_BACKEND
PORT = settings.PORT

LEAGUE_ID = 1
DAILY_QUOTA = 100
PER_MIN = 10
TTL = {
    "teams": 30 * 86400, "squad": 86400, "fixtures": 6 * 3600,
    "standings": 3600, "injuries": 3 * 3600,
}
NEWS_DOMAINS = ["bbc.com/sport", "espn.com", "theathletic.com", "goal.com", "fifa.com"]

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "cache.db"
STAR_JSON_PATH = DATA_DIR / "star_players.json"
API_BASE = "https://v3.football.api-sports.io"


def api_keys() -> set[str]:
    return {k.strip() for k in settings.WC_API_KEYS.split(",") if k.strip()}


DATA_DIR.mkdir(exist_ok=True)
