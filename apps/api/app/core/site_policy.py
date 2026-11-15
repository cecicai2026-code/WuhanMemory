"""公开模式（板块 7，2026-11-15 Cecilia 定）。

网站给老师和朋友用时，在后端 .env 里打开 PUBLIC_MODE=true；本机开发时关着，一切照旧。打开后：

1. 占位照片（官网、第三方）不对外：景点接口不返回它们，后端也不提供 /media/photos-placeholder。
2. 我的行程、生成和撤回分享链接要口令：请求头 X-Owner-Passcode 要等于 .env 的 OWNER_PASSCODE。
   没设口令时这些功能关掉（403）。分享页本身谁都能打开。
3. 规划（发消息）和双模型对比限次数：同一个地址每小时 RATE_PER_CLIENT_PER_HOUR 次，全站每天 RATE_PER_DAY 次
   （按武汉时间零点算），对比一次算 2 次。带对口令的不限，也不计数。
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import settings
from app.data_quality.rules import CITY_TZ
from app.repositories.rate_event_repository import RateEventRepository, SqliteRateEventRepository
from app.core.lang import L

PASSCODE_HEADER = "X-Owner-Passcode"


@dataclass(frozen=True)
class SitePolicy:
    public_mode: bool = False
    owner_passcode: str | None = None
    per_client_per_hour: int = 5
    per_day: int = 50
    trust_proxy_headers: bool = False


def get_site_policy() -> SitePolicy:
    return SitePolicy(
        public_mode=settings.public_mode,
        owner_passcode=settings.owner_passcode or None,
        per_client_per_hour=settings.rate_per_client_per_hour,
        per_day=settings.rate_per_day,
        trust_proxy_headers=settings.trust_proxy_headers,
    )


def get_rate_store() -> RateEventRepository:
    return SqliteRateEventRepository(settings.database_path)


Policy = Annotated[SitePolicy, Depends(get_site_policy)]
RateStore = Annotated[RateEventRepository, Depends(get_rate_store)]


def is_owner(request: Request, policy: SitePolicy) -> bool:
    given = request.headers.get(PASSCODE_HEADER)
    if not policy.owner_passcode or not given:
        return False
    return secrets.compare_digest(given.encode(), policy.owner_passcode.encode())


def require_owner(request: Request, policy: Policy) -> None:
    """公开模式下，只有带对口令的请求能用。本机（没开公开模式）不查。"""
    if not policy.public_mode:
        return
    if not policy.owner_passcode:
        raise HTTPException(status_code=403, detail=L("公开模式下这个功能关着：后端 .env 里没有设 OWNER_PASSCODE", "This feature is off in public mode: OWNER_PASSCODE isn't set in the backend .env"))
    if not is_owner(request, policy):
        raise HTTPException(status_code=401, detail=L("这个功能需要网站主人的口令", "This feature needs the site owner's passcode"))


def _client_key(request: Request, policy: SitePolicy) -> str:
    address = request.client.host if request.client else "unknown"
    if policy.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        address = forwarded or address
    # 不存原始地址，只存摘要
    return hashlib.sha256(f"wuhanmemory-rate:{address}".encode()).hexdigest()[:32]


def rate_limited(weight: int) -> Callable[..., None]:
    """规划和对比的次数限制，用作接口的依赖。没超限时先记一次（这次请求后面出错也算）。"""

    def check(request: Request, policy: Policy, store: RateStore) -> None:
        if not policy.public_mode or is_owner(request, policy):
            return
        now = datetime.now(timezone.utc)
        client = _client_key(request, policy)
        hour_used = store.used_by(client, since=now - timedelta(hours=1))
        if hour_used + weight > policy.per_client_per_hour:
            raise HTTPException(
                status_code=429,
                detail=L(f"试用次数到了：每小时最多 {policy.per_client_per_hour} 次（对比一次算 2 次），过一会儿再试。", f"Trial limit reached: at most {policy.per_client_per_hour} per hour (a comparison counts as 2). Please try again later."),
            )
        midnight = datetime.now(CITY_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        if store.used_total(since=midnight) + weight > policy.per_day:
            raise HTTPException(status_code=429, detail=L(f"今天全站的试用次数（{policy.per_day} 次）用完了，明天再来。", f"Today's trial limit for the whole site ({policy.per_day}) has been used up. Please come back tomorrow."))
        store.add(client, weight, now)

    return check
