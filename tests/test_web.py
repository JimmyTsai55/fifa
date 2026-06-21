import adapters.news_adapter as w


def test_web_search_passes_domains(monkeypatch):
    captured = {}

    def fake_post(url, json, headers):
        captured.update(json)

        class R:
            status_code = 200

            def json(self):
                return {"results": [{"title": "t", "url": "u", "content": "c"}]}
        return R()
    monkeypatch.setattr(w.httpx, "post", fake_post)
    out = w.search("Messi 2026", domains=["espn.com"])
    assert out[0]["title"] == "t"
    assert captured["include_domains"] == ["espn.com"]
