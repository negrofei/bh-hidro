"""Runtime settings from environment (and optional .env)."""

from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_host: str = "localhost"
    database_port: int = 3306
    database_name: str = "bh_hidro"
    database_user: str = "operativo"
    database_password: str = ""
    mysql_root_password: str = ""

    log_dir: Path = Path("logs")
    down_dir: Path = Path("descargas")
    out_dir: Path = Path("output")
    static_data: Path | None = None

    delta_days_back: int = 7
    delta_days_forward: int = 1
    delta_days_back_output: int = 1
    delta_days_forward_output: int = 7

    imerg_user: str = ""
    imerg_password: str = ""
    imerg_ftp_host: str = ""
    imerg_ftp_user: str = ""
    imerg_ftp_password: str = ""

    source_database_host: str = ""
    source_database_port: int | None = None
    source_database_name: str = "fdc_database"
    source_database_user: str = ""
    source_database_password: str = ""
    mysql_container: str = "bh-mysql-prod"

    download_config: Path = Path("configs/example/download.ini")
    reports_config: Path = Path("configs/example/reports.ini")
    reports_weekly_config: Path = Path("configs/example/reports.weekly.ini")
    balance_config: Path = Path("configs/example/balance.ini")
    output_config: Path = Path("configs/example/output.ini")

    @property
    def source_port(self) -> int:
        return int(self.source_database_port or self.database_port)

    def database_url(self, database: str | None = None) -> str:
        name = database if database is not None else self.database_name
        return self._url(self.database_user, self.database_password, self.database_host, self.database_port, name)

    def admin_url(self, user: str, password: str, database: str = "mysql") -> str:
        return self._url(user, password, self.database_host, self.database_port, database)

    def source_database_url(self) -> str:
        user = self.source_database_user or self.database_user
        password = self.source_database_password or self.database_password
        host = self.source_database_host or self.database_host
        return self._url(user, password, host, self.source_port, self.source_database_name)

    def same_mysql_instance(self) -> bool:
        host = self.source_database_host or self.database_host
        return host == self.database_host and self.source_port == int(self.database_port)

    @staticmethod
    def _url(user: str, password: str, host: str, port: int, database: str) -> str:
        return (
            f"mysql+aiomysql://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{database}"
            "?charset=utf8mb4"
        )


def get_settings() -> Settings:
    return Settings()
