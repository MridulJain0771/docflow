from app.core.config import Settings


def test_default_upload_limit_is_positive() -> None:
    settings = Settings(_env_file=None)
    assert settings.max_upload_mb > 0
