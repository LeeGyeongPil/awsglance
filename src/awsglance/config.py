"""설정 — 데이터 폴더의 config.toml(없으면 기본값).

예)
    [collect]
    regions = ["us-east-1", "ap-northeast-2"]   # 비우면 활성 리전 자동 탐지
    inventory_minutes = 30
    cloudtrail_minutes = 5
    retention_days = 180
    max_trail_pages = 20

    [classify]
    human_roles = ["Admin*"]          # 이 역할로 들어온 호출은 '사람'
    automated_roles = ["platform-*"]  # 이 역할로 들어온 호출은 '자동'
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .classify import ClassifyRules


def default_data_dir() -> Path:
    env = os.environ.get("AWSGLANCE_DATA_DIR")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "awsglance"


@dataclass
class Settings:
    regions: list[str] = field(default_factory=list)
    inventory_minutes: int = 30
    cloudtrail_minutes: int = 5
    retention_days: int = 180
    max_trail_pages: int = 20
    max_runs: int = 500
    classify: ClassifyRules = field(default_factory=ClassifyRules)


def load(data_dir: Path) -> Settings:
    path = Path(data_dir) / "config.toml"
    s = Settings()
    if not path.exists():
        return s
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    col = raw.get("collect", {})
    s.regions = [str(r) for r in col.get("regions", [])]
    # 너무 잦은 수집은 AWS 호출 한도를 먹으므로 하한을 둔다
    s.inventory_minutes = max(5, int(col.get("inventory_minutes", s.inventory_minutes)))
    s.cloudtrail_minutes = max(1, int(col.get("cloudtrail_minutes", s.cloudtrail_minutes)))
    s.retention_days = max(1, int(col.get("retention_days", s.retention_days)))
    s.max_trail_pages = max(1, int(col.get("max_trail_pages", s.max_trail_pages)))
    cls = raw.get("classify", {})
    s.classify = ClassifyRules(human_roles=[str(x) for x in cls.get("human_roles", [])],
                               automated_roles=[str(x) for x in cls.get("automated_roles", [])])
    return s
