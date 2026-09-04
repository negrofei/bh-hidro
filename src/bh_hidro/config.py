"""Runtime settings from environment (and optional .env)."""

from pathlib import Path

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

    download_config: Path = Path("configs/example/download.ini")
    reports_config: Path = Path("configs/example/reports.ini")
    balance_config: Path = Path("configs/example/balance.ini")
    output_config: Path = Path("configs/example/output.ini")

    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
            "?charset=utf8mb4"
        )


def get_settings() -> Settings:
    return Settings()
