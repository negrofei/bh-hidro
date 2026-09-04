from pathlib import Path

from bh_hidro.config import Settings


def test_database_url_default():
    settings = Settings(
        database_host="db",
        database_port=3306,
        database_name="bh_hidro",
        database_user="operativo",
        database_password="secret",
    )
    assert settings.database_url() == (
        "mysql+aiomysql://operativo:secret@db:3306/bh_hidro?charset=utf8mb4"
    )


def test_default_paths():
    settings = Settings()
    assert settings.log_dir == Path("logs")
    assert settings.delta_days_back == 7
    assert settings.delta_days_forward == 1
