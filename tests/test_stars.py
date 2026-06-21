import adapters.stars_adapter as s


def test_load_and_find_by_alias(tmp_path, monkeypatch):
    import config
    import shutil
    shutil.copy("data/star_players.sample.json", tmp_path / "star_players.json")
    monkeypatch.setattr(config, "STAR_JSON_PATH", tmp_path / "star_players.json")
    s._cache = None
    prof = s.find("梅西")
    assert prof and prof["classification"] == "老將"


def test_find_unknown_returns_none(tmp_path, monkeypatch):
    import config
    import shutil
    shutil.copy("data/star_players.sample.json", tmp_path / "star_players.json")
    monkeypatch.setattr(config, "STAR_JSON_PATH", tmp_path / "star_players.json")
    s._cache = None
    assert s.find("無此人") is None
