import config


def test_core_constants():
    assert config.LEAGUE_ID == 1
    assert isinstance(config.SEASON, int) and config.SEASON >= 2022
    assert config.DAILY_QUOTA == 100
    assert config.PER_MIN == 10


def test_ttl_table_has_expected_keys():
    for k in ["teams", "squad", "fixtures", "standings", "injuries"]:
        assert k in config.TTL and config.TTL[k] > 0


def test_news_domains_english_only():
    assert "bbc.com/sport" in config.NEWS_DOMAINS
    assert len(config.NEWS_DOMAINS) >= 4


def test_api_keys_parses_comma_list(monkeypatch):
    monkeypatch.setenv("WC_API_KEYS", " k1 , k2 ,")
    import importlib, config
    importlib.reload(config)
    assert config.api_keys() == {"k1", "k2"}


def test_port_defaults_to_8887(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    import importlib, config
    importlib.reload(config)
    assert config.PORT == 8887
