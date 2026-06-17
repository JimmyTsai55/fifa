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


def test_find_team_id_none_when_teams_empty(monkeypatch):
    # 未初始化 → teams 為空 → 回 None（而非誤配）
    monkeypatch.setattr(af, "_teams", lambda: [])
    assert af._find_team_id("Argentina") is None


def test_invalid_team_id_returns_error_not_api_call(monkeypatch):
    # team_id<=0 不應觸及 _cached / 真實 API，要回明確錯誤
    def boom(*a, **k):
        raise AssertionError("should not call API")
    monkeypatch.setattr(af, "_cached", boom)
    for fn in (af._squad, af._player_stats, af._injuries):
        out = fn(0)
        assert out and "error" in out[0]
