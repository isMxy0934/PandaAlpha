from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application runtime settings loaded from environment/.env.

    Defaults follow the spec: TZ=Asia/Shanghai and SQLite meta DB under data/.
    """

    tz: str = "Asia/Shanghai"
    database_url: str = "sqlite:///data/meta.sqlite"
    tushare_token: str | None = None
    serverchan_sendkey: str | None = None
    data_provider: str = "akshare"  # akshare | tushare
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = AppSettings()


