from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Dict, Iterator, List, Optional, Tuple
import re
import time
from datetime import datetime

from .config import Rule


# -------------------------
# Model
# -------------------------
@dataclass
class Incident:
    rule_id: str
    type: str
    severity: str
    message: str
    line_no: int
    extracted: Dict[str, str]
    context: List[str] = field(default_factory=list)  # 多行聚合附带的上下文（不含 message 那一行）

    def to_dict(self) -> Dict:
        return asdict(self)


# -------------------------
# Matching
# -------------------------
def _keywords_match(rule: Rule, text: str) -> bool:
    if rule.keywords_all and not all(k in text for k in rule.keywords_all):
        return False
    if rule.keywords_any and not any(k in text for k in rule.keywords_any):
        return False
    return True


def _regex_match(rule: Rule, text: str) -> Tuple[bool, Dict[str, str]]:
    extracted: Dict[str, str] = {}

    def match_any(patterns) -> Optional[object]:
        for p in patterns:
            m = p.search(text)
            if m:
                return m
        return None

    if rule.regex_all:
        for p in rule.regex_all:
            if not p.search(text):
                return False, {}
        m0 = rule.regex_all[0].search(text)
        if m0:
            extracted.update({k: str(v) for k, v in m0.groupdict().items() if v is not None})

    if rule.regex_any:
        m = match_any(rule.regex_any)
        if not m:
            return False, {}
        extracted.update({k: str(v) for k, v in m.groupdict().items() if v is not None})

    return True, extracted


class Cooldown:
    def __init__(self) -> None:
        self._last: Dict[str, float] = {}

    def allow(self, fingerprint: str, cooldown_seconds: int) -> bool:
        if cooldown_seconds <= 0:
            return True
        now = time.time()
        last = self._last.get(fingerprint)
        if last is not None and (now - last) < cooldown_seconds:
            return False
        self._last[fingerprint] = now
        return True


class Detector:
    """
    Stateful detector for streaming logs.
    Keeps cooldown state across lines.
    """
    def __init__(self, rules: List[Rule]) -> None:
        self.rules = rules
        self.cooldown = Cooldown()

    def process_line(self, line_no: int, line: str) -> List[Incident]:
        text = line.rstrip("\n")
        hits: List[Incident] = []

        for rule in self.rules:
            if not _keywords_match(rule, text):
                continue
            ok, extracted = _regex_match(rule, text)
            if not ok:
                continue

            fp = f"{rule.id}|{extracted.get('pid','')}|{extracted.get('comm','')}|{text[:80]}"
            if not self.cooldown.allow(fp, rule.cooldown_seconds):
                continue

            hits.append(
                Incident(
                    rule_id=rule.id,
                    type=rule.type,
                    severity=rule.severity,
                    message=text,
                    line_no=line_no,
                    extracted=extracted,
                )
            )
        return hits


# -------------------------
# Multi-line aggregation
# -------------------------
_SYSLOG_TS = re.compile(r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\b")
_MONTH = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

_END_MARKERS = (
    "end trace",
    "End trace",
    "end Kernel panic",
    "End Kernel panic",
    "---[ end",
)

def _parse_syslog_ts(line: str) -> Optional[float]:
    """
    Parse syslog timestamp like: 'Dec 24 17:40:11 ...'
    Return epoch seconds (local time). If parse fails, return None.
    """
    m = _SYSLOG_TS.search(line)
    if not m:
        return None
    mon = _MONTH.get(m.group("mon"))
    if not mon:
        return None
    day = int(m.group("day"))
    h = int(m.group("h"))
    mi = int(m.group("m"))
    s = int(m.group("s"))
    year = datetime.now().year
    try:
        dt = datetime(year, mon, day, h, mi, s)
        return dt.timestamp()
    except Exception:
        return None


def _trigger_type(text: str) -> Optional[str]:
    if "Kernel panic - not syncing" in text:
        return "PANIC"
    if ("Oops:" in text) or ("BUG:" in text) or ("Unable to handle kernel" in text):
        return "OOPS"
    # ✅ DEADLOCK 只用真正的“起始行”触发，避免 echo hung_task_timeout_secs 误触发
    if ("blocked for more than" in text) and ("task" in text):
        return "DEADLOCK"
    return None




class MultiLineAggregator:
    """
    Aggregates multi-line kernel events for OOPS/PANIC:
    - Start on trigger line
    - Collect subsequent lines as context
    - Flush on:
        * new trigger line
        * log timestamp gap > window_seconds
        * end marker
        * idle timeout (monitor heartbeat)
        * max_lines reached
    """
    def __init__(
        self,
        detector: Detector,
        *,
        window_seconds: float = 5.0,
        max_lines: int = 200,
        idle_flush_seconds: float = 0.8,
    ) -> None:
        self.detector = detector
        self.window_seconds = window_seconds
        self.max_lines = max_lines
        self.idle_flush_seconds = idle_flush_seconds

        self.active_type: Optional[str] = None
        self.start_line_no: int = 0
        self.start_line: str = ""
        self.start_ts: Optional[float] = None
        self.context: List[str] = []
        self._last_activity_wall: float = 0.0

    def _start(self, t: str, line_no: int, line: str) -> None:
        self.active_type = t
        self.start_line_no = line_no
        self.start_line = line.rstrip("\n")
        self.start_ts = _parse_syslog_ts(self.start_line)
        self.context = []
        self._last_activity_wall = time.time()

    def _emit(self) -> List[Incident]:
        if not self.active_type:
            return []
        hits = self.detector.process_line(self.start_line_no, self.start_line)

        # 如果规则没命中（理论上不该），做一个兜底事件
        if not hits:
            severity = "high" if self.active_type == "OOPS" else "critical"
            hits = [
                Incident(
                    rule_id=f"multiline_{self.active_type.lower()}",
                    type=self.active_type,
                    severity=severity,
                    message=self.start_line,
                    line_no=self.start_line_no,
                    extracted={},
                )
            ]

        for inc in hits:
            if inc.type == self.active_type:
                inc.context = list(self.context)
        self.active_type = None
        self.start_line_no = 0
        self.start_line = ""
        self.start_ts = None
        self.context = []
        self._last_activity_wall = 0.0
        return hits

    def flush(self) -> List[Incident]:
        return self._emit()

    def process(self, line_no: int, line: str) -> List[Incident]:
        # heartbeat: (0, "") 用于 idle flush
        if line_no == 0 and line == "":
            if self.active_type and (time.time() - self._last_activity_wall) >= self.idle_flush_seconds:
                return self._emit()
            return []

        text = line.rstrip("\n")
        t = _trigger_type(text)

        # 若当前在聚合中，先处理“切断条件”
        if self.active_type:
            # 新触发：先 flush 老的，再 start 新的（本行作为新块的起始行）
            if t is not None:
                out = self._emit()
                self._start(t, line_no, text)
                return out

            # 时间窗口切断：避免把很久后的其它日志吸进 context
            if self.start_ts is not None:
                cur_ts = _parse_syslog_ts(text)
                if cur_ts is not None and (cur_ts - self.start_ts) > self.window_seconds:
                    out = self._emit()
                    # 这行不属于之前的块，作为普通行继续处理
                    return out + self.process(line_no, line)

            # 追加到 context
            if len(self.context) < self.max_lines:
                self.context.append(text)
            self._last_activity_wall = time.time()

            # 结束标记：立刻 flush（包括该行）
            if any(m in text for m in _END_MARKERS) or len(self.context) >= self.max_lines:
                return self._emit()

            return []

        # 不在聚合中：如果触发多行类型 -> start block（先不立刻输出，等待聚合结束/flush）
        if t is not None:
            self._start(t, line_no, text)
            return []

        # 普通行：直接走规则检测
        return self.detector.process_line(line_no, line)


def detect_lines(lines: Iterator[Tuple[int, str]], rules: List[Rule]) -> List[Incident]:
    detector = Detector(rules)
    agg = MultiLineAggregator(detector)

    incidents: List[Incident] = []
    for line_no, line in lines:
        incidents.extend(agg.process(line_no, line))

    # 文件结束时把未 flush 的块吐出来
    incidents.extend(agg.flush())
    return incidents

