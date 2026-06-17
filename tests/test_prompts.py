from wc_agents import prompts


def test_all_prompts_xml_structured():
    for p in [prompts.TRIAGE, prompts.SQUAD, prompts.FIXTURE,
              prompts.STAR, prompts.INSIGHT]:
        assert "<role>" in p and "<rules>" in p and "<output_format>" in p
