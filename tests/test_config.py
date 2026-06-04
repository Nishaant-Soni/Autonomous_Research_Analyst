from app.config import Settings


def test_defaults_without_env_file():
    # _env_file=None ignores any local .env so we assert the in-code defaults.
    s = Settings(_env_file=None)
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"
    assert s.max_iterations == 2
