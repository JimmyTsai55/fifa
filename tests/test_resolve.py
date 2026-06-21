import adapters.resolve_adapter as r


def test_resolve_known_team():
    out = r.resolve("阿根廷")
    assert out["type"] == "team" and out["canonical_name"] == "Argentina"


def test_resolve_known_player():
    out = r.resolve("梅西")
    assert out["type"] == "player"
    assert out["canonical_name"] == "Messi" and out["team"] == "Argentina"


def test_unknown_passes_through_as_query():
    out = r.resolve("某冷門球員")
    assert out["type"] == "unknown" and out["canonical_name"] == "某冷門球員"
