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
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Configuration file not found: {path}\n"
            f"Please ensure the file exists or specify a different config with --config"
        )
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {path}: {e}")

    rules: List[Rule] = []
    for idx, r in enumerate(data.get("rules", []) or [], start=1):
        # Validate required fields
        if "id" not in r:
            raise ValueError(f"Rule #{idx} is missing required field 'id'")
        if "type" not in r:
            raise ValueError(f"Rule '{r.get('id', idx)}' is missing required field 'type'")

        reg_any_str = r.get("regex_any", []) or []
        reg_all_str = r.get("regex_all", []) or []

        # Compile regexes with error handling
        try:
            regex_any_compiled = [re.compile(p) for p in reg_any_str]
            regex_all_compiled = [re.compile(p) for p in reg_all_str]
        except re.error as e:
            raise ValueError(
                f"Invalid regex in rule '{r['id']}': {e}\n"
                f"Please check the regex patterns in your configuration"
            )

        rules.append(
            Rule(
                id=r["id"],
                type=r["type"],
                severity=r.get("severity", "medium"),
                keywords_any=r.get("keywords_any", []) or [],
                keywords_all=r.get("keywords_all", []) or [],
                regex_any=regex_any_compiled,
                regex_all=regex_all_compiled,
                cooldown_seconds=int(r.get("cooldown_seconds", 0) or 0),
            )
        )

    return Config(version=int(data.get("version", 1)), rules=rules)

