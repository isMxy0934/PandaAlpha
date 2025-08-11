from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application runtime settings loaded from environment/.env.

    Defaults follow the spec: TZ=Asia/Shanghai and SQLite meta DB under data/.
    """

    tz: str = "Asia/Shanghai"
    database_url: str = "sqlite:///data/meta.sqlite"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = AppSettings()


