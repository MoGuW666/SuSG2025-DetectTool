from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Pattern
import re
import yaml


@dataclass
class Rule:
    id: str
    type: str
    severity: str = "medium"
    keywords_any: List[str] = field(default_factory=list)
    keywords_all: List[str] = field(default_factory=list)

    regex_any: List[Pattern[str]] = field(default_factory=list)
    regex_all: List[Pattern[str]] = field(default_factory=list)

    cooldown_seconds: int = 0


@dataclass
class Config:
    version: int = 1
    rules: List[Rule] = field(default_factory=list)


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    rules: List[Rule] = []
    for r in (data.get("rules", []) or []):
        reg_any_str = r.get("regex_any", []) or []
        reg_all_str = r.get("regex_all", []) or []

        rules.append(
            Rule(
                id=r["id"],
                type=r["type"],
                severity=r.get("severity", "medium"),
                keywords_any=r.get("keywords_any", []) or [],
                keywords_all=r.get("keywords_all", []) or [],
                regex_any=[re.compile(p) for p in reg_any_str],
                regex_all=[re.compile(p) for p in reg_all_str],
                cooldown_seconds=int(r.get("cooldown_seconds", 0) or 0),
            )
        )

    return Config(version=int(data.get("version", 1)), rules=rules)

