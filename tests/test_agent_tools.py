import pytest
import adapters.agent_tools as at


class FakePort:
    def find_team_id(self, name): return 7 if name == "Brazil" else None
    def squad(self, tid): return [{"tid": tid}]
    def player_stats(self, tid): return []
    def fixtures(self, tid=None): return [{"f": tid}]
    def standings(self, group=None): return [{"s": 1}]
    def injuries(self, tid): return []
    def live(self): return [{"live": 1}]


def test_current_football_raises_when_unbound():
    at._football = None
    with pytest.raises(RuntimeError):
        at.current_football()


def test_bind_and_lookup():
    at.bind_football(FakePort())
    assert at.current_football().find_team_id("Brazil") == 7
