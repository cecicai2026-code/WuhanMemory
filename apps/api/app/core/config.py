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

    # 默认用哪个模型：qwen 或 doubao。每次请求也可以另外指定
    llm_provider: str = "qwen"
    llm_fallback_provider: str | None = None
    llm_provider_mode: str = "fixed"

    qwen_api_key: str | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    doubao_api_key: str | None = None
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str | None = None
    # 豆包的深度思考开关：留空用模型自己的默认值，enabled 强制思考，disabled 不思考
    doubao_thinking: str = ""

    llm_request_timeout_seconds: int = 60
    llm_max_retries: int = 2

    # 高德 Web 服务 key，只在后端用（地点搜索、路线规划）
    amap_web_service_key: str | None = None
    amap_base_url: str = "https://restapi.amap.com"
    # JS key 配套的安全密钥。只在后端用：浏览器的地图请求经过 /_AMapService 代理时由后端加上（见 app/api/amap_proxy.py）
    amap_security_js_code: str | None = None
    # 自定义地图样式的上游地址（高德官方代理示例里 /_AMapService/v4/map/styles 转到这里）
    amap_webapi_url: str = "https://webapi.amap.com"

    # 公开模式（板块 7）：网站给别人用时打开，本机开发时关着。见 app/core/site_policy.py
    public_mode: bool = False
    # 公开模式下，我的行程、生成和撤回分享链接要这个口令；不设就关掉这些功能
    owner_passcode: str | None = None
    # 公开模式下规划和对比的次数上限（对比一次算 2 次）；带对口令的不限
    rate_per_client_per_hour: int = 5
    rate_per_day: int = 50
    # 网站前面有反向代理或隧道时打开，用 X-Forwarded-For 里的第一个地址认人；没有代理时不要打开，否则谁都能伪造
    trust_proxy_headers: bool = False

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
