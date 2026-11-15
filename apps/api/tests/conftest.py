"""全部测试共用的设置。

测试不跟着 .env 走公开模式：服务器的 .env 里 PUBLIC_MODE=true（ADR 0008），
在服务器上跑测试时，没专门测公开模式的测试也会被口令和次数限制拦住。
所以每个测试开始时先把网站规则设成本机模式；test_public_mode.py 自己会再换成公开模式。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.site_policy import SitePolicy, get_site_policy
from app.main import app


@pytest.fixture(autouse=True)
def local_site_policy() -> Iterator[None]:
    app.dependency_overrides[get_site_policy] = lambda: SitePolicy()
    yield
    app.dependency_overrides.pop(get_site_policy, None)
