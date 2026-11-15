from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 仓库根目录：apps/api/app/core/config.py 往上四层
REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    public_app_url: str = "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    llm_provider: str = "mock"
    llm_fallback_provider: str | None = None
    llm_provider_mode: str = "fixed"

    qwen_api_key: str | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    doubao_api_key: str | None = None
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str | None = None

    llm_request_timeout_seconds: int = 60
    llm_max_retries: int = 2

    # 高德 Web 服务 key，只在后端用（地点搜索、路线规划）
    amap_web_service_key: str | None = None
    amap_base_url: str = "https://restapi.amap.com"
    # JS key 配套的安全密钥。只在后端用：浏览器的地图请求经过 /_AMapService 代理时由后端加上（见 app/api/amap_proxy.py）
    amap_security_js_code: str | None = None
    # 自定义地图样式的上游地址（高德官方代理示例里 /_AMapService/v4/map/styles 转到这里）
    amap_webapi_url: str = "https://webapi.amap.com"

    # 景点资料（data/pois/*.json）和照片所在的目录，见 ADR 0003
    data_dir: Path = REPO_ROOT / "data"
    # SQLite 数据库文件。相对路径按 apps/api 算
    database_url: str = "sqlite:///./wuhanmemory.db"

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError(f"DATABASE_URL 只支持 sqlite:///，现在是 {self.database_url}")
        path = Path(self.database_url[len(prefix):])
        return path if path.is_absolute() else API_ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
