from app.llm.provider import LLMProvider, OpenAIProvider


def test_openai_provider_implements_interface():
    # Instantiation must not require a live key or make a network call.
    p = OpenAIProvider(api_key="test-key", model="gpt-5.4-mini")
    assert isinstance(p, LLMProvider)
    assert callable(p.complete)
