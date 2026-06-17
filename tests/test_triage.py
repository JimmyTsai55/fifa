from wc_agents.triage import triage_agent


def test_triage_has_four_handoffs():
    names = {h.name for h in triage_agent.handoffs}
    assert {"Squad", "Fixture", "Star", "Insight"} <= names
