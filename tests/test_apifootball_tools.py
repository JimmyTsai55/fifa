import tools.apifootball as af


def test_get_squad_uses_cache(monkeypatch):
    captured = {}

    def fake_cached(key, ttl, path, params):
        captured.update(key=key, path=path, params=params)
        return [{"player": "x"}]
    monkeypatch.setattr(af, "_cached", fake_cached)
    out = af.get_squad(26)   # get_squad = _squad（純函式別名）
    assert out == [{"player": "x"}]
    assert captured["path"] == "/players/squads"
    assert captured["params"]["team"] == 26
    assert "squad:26" in captured["key"]


def test_find_team_id_matches_name(monkeypatch):
    monkeypatch.setattr(af, "_teams",
                        lambda: [{"team": {"id": 26, "name": "Argentina"}}])
    assert af._find_team_id("Argentina") == 26
    assert af._find_team_id("argentina") == 26   # 大小寫不敏感
    assert af._find_team_id("Narnia") is None
