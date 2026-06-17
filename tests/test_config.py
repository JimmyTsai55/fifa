import config


def test_core_constants():
    assert config.LEAGUE_ID == 1
    assert config.SEASON == 2026
    assert config.DAILY_QUOTA == 100
    assert config.PER_MIN == 10


def test_ttl_table_has_expected_keys():
    for k in ["teams", "squad", "fixtures", "standings", "injuries"]:
        assert k in config.TTL and config.TTL[k] > 0


def test_news_domains_english_only():
    assert "bbc.com/sport" in config.NEWS_DOMAINS
    assert len(config.NEWS_DOMAINS) >= 4
