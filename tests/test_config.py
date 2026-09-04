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


def test_database_url_quotes_password():
    settings = Settings(
        database_host="127.0.0.1",
        database_port=3308,
        database_name="bh_hidro",
        database_user="operativo",
        database_password="p@ss/word",
    )
    assert settings.database_url() == (
        "mysql+aiomysql://operativo:p%40ss%2Fword@127.0.0.1:3308/bh_hidro?charset=utf8mb4"
    )


def test_same_mysql_instance_defaults_source_port():
    host = Settings(database_host="127.0.0.1", database_port=3308)
    assert host.same_mysql_instance() is True
    assert host.source_port == 3308
    other = Settings(
        database_host="127.0.0.1",
        database_port=3308,
        source_database_port=3309,
    )
    assert other.same_mysql_instance() is False


def test_default_paths():
    settings = Settings()
    assert settings.log_dir == Path("logs") or settings.log_dir == Path("/logs")
    assert settings.delta_days_back == 7
    assert settings.delta_days_forward == 1
