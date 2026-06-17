import sys
from agents import Runner              # OpenAI Agents SDK
from wc_agents.triage import triage_agent


def ask(question: str) -> str:
    result = Runner.run_sync(triage_agent, question)
    return result.final_output


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or input("問世界盃什麼？ ")
    print(ask(q))
