from wc_agents import specialists


def test_specialists_have_expected_tools():
    def names(a):
        return {t.name for t in a.tools}
    assert "resolve_entity" in names(specialists.squad_agent)
    assert "tool_get_live" in names(specialists.fixture_agent)
    assert "get_star_profile" in names(specialists.star_agent)
    assert "tool_get_injuries" in names(specialists.insight_agent)


def test_specialists_named():
    assert specialists.squad_agent.name == "Squad"
    assert specialists.star_agent.name == "Star"
