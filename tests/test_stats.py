"""
Test cases for statistics functionality.

Tests cover:
- Statistics generation
- Count accuracy
- Top N rankings
- Edge cases (empty results, etc.)
"""
from __future__ import annotations
import pytest
from pathlib import Path
from detecttool.engine import detect_lines, Incident
from detecttool.config import load_config
from detecttool.cli import _generate_statistics


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_LOG = FIXTURES_DIR / "test.log"


def _iter_file_lines(path: Path):
    """Helper to iterate file lines with line numbers."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, start=1):
            yield i, line


@pytest.fixture
def config():
    """Load the default rules configuration."""
    config_path = Path(__file__).parent.parent / "configs" / "rules.yaml"
    return load_config(str(config_path))


@pytest.fixture
def incidents(config):
    """Detect incidents from test log file."""
    return detect_lines(_iter_file_lines(TEST_LOG), config.rules)


@pytest.fixture
def stats_data(incidents):
    """Generate statistics from detected incidents."""
    return _generate_statistics(incidents, total_lines=16, top_n=10)


class TestStatisticsGeneration:
    """Test statistics data generation."""

    def test_total_incidents(self, stats_data):
        """Test total incidents count in statistics."""
        assert stats_data["total_incidents"] == 6

    def test_total_lines_scanned(self, stats_data):
        """Test total lines scanned is recorded."""
        assert stats_data["total_lines_scanned"] == 16

    def test_unique_types_count(self, stats_data):
        """Test unique types count."""
        assert stats_data["unique_types"] == 6

    def test_by_type_structure(self, stats_data):
        """Test by_type statistics structure."""
        assert "by_type" in stats_data
        assert isinstance(stats_data["by_type"], dict)
        assert len(stats_data["by_type"]) == 6

    def test_by_severity_structure(self, stats_data):
        """Test by_severity statistics structure."""
        assert "by_severity" in stats_data
        assert isinstance(stats_data["by_severity"], dict)

    def test_by_rule_structure(self, stats_data):
        """Test by_rule statistics structure."""
        assert "by_rule" in stats_data
        assert isinstance(stats_data["by_rule"], dict)
        assert len(stats_data["by_rule"]) == 6

    def test_top_processes_structure(self, stats_data):
        """Test top_processes statistics structure."""
        assert "top_processes" in stats_data
        assert isinstance(stats_data["top_processes"], list)
        # Each item should be a tuple of (process_name, count)
        for item in stats_data["top_processes"]:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_top_pids_structure(self, stats_data):
        """Test top_pids statistics structure."""
        assert "top_pids" in stats_data
        assert isinstance(stats_data["top_pids"], list)
        for item in stats_data["top_pids"]:
            assert isinstance(item, tuple)
            assert len(item) == 2


class TestStatisticsCounts:
    """Test accuracy of statistical counts."""

    def test_type_counts(self, stats_data):
        """Test that each type appears exactly once."""
        by_type = stats_data["by_type"]
        expected_types = ["OOM", "OOPS", "PANIC", "DEADLOCK", "REBOOT", "FS_EXCEPTION"]

        for t in expected_types:
            assert t in by_type, f"Type {t} should be in statistics"
            assert by_type[t] == 1, f"Type {t} should appear exactly once"

    def test_severity_counts(self, stats_data):
        """Test severity level distribution."""
        by_severity = stats_data["by_severity"]

        # From rules.yaml: OOM/OOPS/FS_EXCEPTION/DEADLOCK=high, PANIC=critical, REBOOT=medium
        assert by_severity.get("high") == 4, "Should have 4 high severity incidents"
        assert by_severity.get("critical") == 1, "Should have 1 critical severity incident"
        assert by_severity.get("medium") == 1, "Should have 1 medium severity incident"

    def test_total_equals_sum(self, stats_data):
        """Test that total incidents equals sum of all type counts."""
        by_type = stats_data["by_type"]
        total = stats_data["total_incidents"]

        assert sum(by_type.values()) == total, \
            "Sum of type counts should equal total incidents"

    def test_rule_counts(self, stats_data):
        """Test rule trigger counts."""
        by_rule = stats_data["by_rule"]
        expected_rules = [
            "oom_basic",
            "oops_basic",
            "panic_basic",
            "deadlock_hung_task",
            "reboot_basic",
            "fs_exception_basic",
        ]

        for rule_id in expected_rules:
            assert rule_id in by_rule, f"Rule {rule_id} should be in statistics"
            assert by_rule[rule_id] == 1, f"Rule {rule_id} should trigger exactly once"


class TestTopNRankings:
    """Test Top N ranking functionality."""

    def test_top_processes_content(self, stats_data):
        """Test top processes list contains expected processes."""
        top_procs = stats_data["top_processes"]

        # Should have extracted python3 and kworker/0:1
        assert len(top_procs) == 2, "Should have 2 processes extracted"

        proc_names = [p[0] for p in top_procs]
        assert "python3" in proc_names, "Should include python3"
        assert "kworker/0:1" in proc_names, "Should include kworker/0:1"

    def test_top_pids_content(self, stats_data):
        """Test top PIDs list contains expected PIDs."""
        top_pids = stats_data["top_pids"]

        # Should have extracted 1234 and 4321
        assert len(top_pids) == 2, "Should have 2 PIDs extracted"

        pids = [p[0] for p in top_pids]
        assert "1234" in pids, "Should include PID 1234"
        assert "4321" in pids, "Should include PID 4321"

    def test_top_n_limit(self):
        """Test that top_n parameter limits results."""
        # Create incidents with many different processes
        incidents = [
            Incident(
                rule_id=f"test_rule_{i}",
                type="OOM",
                severity="high",
                message=f"Process {i}",
                line_no=i,
                extracted={"comm": f"proc{i}", "pid": str(i)},
            )
            for i in range(20)
        ]

        stats = _generate_statistics(incidents, total_lines=20, top_n=5)

        # Should only return top 5
        assert len(stats["top_processes"]) == 5, "Should limit to top 5 processes"
        assert len(stats["top_pids"]) == 5, "Should limit to top 5 PIDs"


class TestEdgeCases:
    """Test edge cases for statistics."""

    def test_empty_incidents(self):
        """Test statistics generation with no incidents."""
        stats = _generate_statistics([], total_lines=10, top_n=10)

        assert stats["total_incidents"] == 0
        assert stats["unique_types"] == 0
        assert len(stats["by_type"]) == 0
        assert len(stats["by_severity"]) == 0
        assert len(stats["top_processes"]) == 0
        assert len(stats["top_pids"]) == 0

    def test_incidents_without_extracted_fields(self):
        """Test statistics with incidents that have no extracted fields."""
        incidents = [
            Incident(
                rule_id="test_rule",
                type="OOPS",
                severity="high",
                message="Test message",
                line_no=1,
                extracted={},  # No extracted fields
            )
        ]

        stats = _generate_statistics(incidents, total_lines=1, top_n=10)

        assert stats["total_incidents"] == 1
        assert len(stats["top_processes"]) == 0, "Should have no processes without comm field"
        assert len(stats["top_pids"]) == 0, "Should have no PIDs without pid field"

    def test_duplicate_process_aggregation(self):
        """Test that same process appearing multiple times is aggregated correctly."""
        incidents = [
            Incident(
                rule_id="test1",
                type="OOM",
                severity="high",
                message="Kill 1",
                line_no=1,
                extracted={"comm": "python3", "pid": "100"},
            ),
            Incident(
                rule_id="test2",
                type="OOM",
                severity="high",
                message="Kill 2",
                line_no=2,
                extracted={"comm": "python3", "pid": "101"},
            ),
            Incident(
                rule_id="test3",
                type="OOM",
                severity="high",
                message="Kill 3",
                line_no=3,
                extracted={"comm": "java", "pid": "200"},
            ),
        ]

        stats = _generate_statistics(incidents, total_lines=3, top_n=10)

        top_procs = dict(stats["top_processes"])
        assert top_procs["python3"] == 2, "python3 should appear 2 times"
        assert top_procs["java"] == 1, "java should appear 1 time"
