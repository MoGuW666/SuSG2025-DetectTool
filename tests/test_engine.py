"""
Test cases for the core detection engine.

Tests cover:
- Detection of all 6 abnormal types (OOM, Oops, Panic, Deadlock, Reboot, FS_Exception)
- Field extraction (pid, comm, etc.)
- Multi-line aggregation
- Cooldown mechanism
"""
from __future__ import annotations
import pytest
from pathlib import Path
from detecttool.engine import detect_lines, Detector, Incident
from detecttool.config import load_config


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


class TestDetection:
    """Test detection of various abnormal types."""

    def test_total_incidents_count(self, incidents):
        """Test that correct number of incidents are detected."""
        # Test log should contain 6 incidents (one of each type)
        assert len(incidents) == 6, f"Expected 6 incidents, got {len(incidents)}"

    def test_oom_detection(self, incidents):
        """Test OOM (Out of Memory) detection."""
        oom_incidents = [inc for inc in incidents if inc.type == "OOM"]
        assert len(oom_incidents) == 1, "Should detect exactly 1 OOM incident"

        oom = oom_incidents[0]
        assert oom.severity == "high"
        assert oom.rule_id == "oom_basic"
        assert "Killed process" in oom.message

    def test_oops_detection(self, incidents):
        """Test Oops (kernel error) detection."""
        oops_incidents = [inc for inc in incidents if inc.type == "OOPS"]
        assert len(oops_incidents) == 1, "Should detect exactly 1 Oops incident"

        oops = oops_incidents[0]
        assert oops.severity == "high"
        assert oops.rule_id == "oops_basic"
        assert "Oops:" in oops.message

    def test_panic_detection(self, incidents):
        """Test Panic (system crash) detection."""
        panic_incidents = [inc for inc in incidents if inc.type == "PANIC"]
        assert len(panic_incidents) == 1, "Should detect exactly 1 Panic incident"

        panic = panic_incidents[0]
        assert panic.severity == "critical"
        assert panic.rule_id == "panic_basic"
        assert "Kernel panic" in panic.message

    def test_deadlock_detection(self, incidents):
        """Test Deadlock (hung task) detection."""
        deadlock_incidents = [inc for inc in incidents if inc.type == "DEADLOCK"]
        assert len(deadlock_incidents) == 1, "Should detect exactly 1 Deadlock incident"

        deadlock = deadlock_incidents[0]
        assert deadlock.severity == "high"
        assert deadlock.rule_id == "deadlock_hung_task"
        assert "blocked for more than" in deadlock.message

    def test_reboot_detection(self, incidents):
        """Test Reboot detection."""
        reboot_incidents = [inc for inc in incidents if inc.type == "REBOOT"]
        assert len(reboot_incidents) == 1, "Should detect exactly 1 Reboot incident"

        reboot = reboot_incidents[0]
        assert reboot.severity == "medium"
        assert reboot.rule_id == "reboot_basic"
        assert "reboot:" in reboot.message

    def test_fs_exception_detection(self, incidents):
        """Test File System Exception detection."""
        fs_incidents = [inc for inc in incidents if inc.type == "FS_EXCEPTION"]
        assert len(fs_incidents) == 1, "Should detect exactly 1 FS_EXCEPTION incident"

        fs = fs_incidents[0]
        assert fs.severity == "high"
        assert fs.rule_id == "fs_exception_basic"
        assert "EXT4-fs error" in fs.message


class TestFieldExtraction:
    """Test extraction of fields from log lines."""

    def test_oom_field_extraction(self, incidents):
        """Test that OOM incident extracts pid and comm fields."""
        oom = [inc for inc in incidents if inc.type == "OOM"][0]

        assert "pid" in oom.extracted, "OOM should extract 'pid' field"
        assert "comm" in oom.extracted, "OOM should extract 'comm' field"
        assert oom.extracted["pid"] == "1234"
        assert oom.extracted["comm"] == "python3"

    def test_deadlock_field_extraction(self, incidents):
        """Test that Deadlock incident extracts pid, comm, and secs fields."""
        deadlock = [inc for inc in incidents if inc.type == "DEADLOCK"][0]

        assert "pid" in deadlock.extracted, "Deadlock should extract 'pid' field"
        assert "comm" in deadlock.extracted, "Deadlock should extract 'comm' field"
        assert "secs" in deadlock.extracted, "Deadlock should extract 'secs' field"
        assert deadlock.extracted["pid"] == "4321"
        assert deadlock.extracted["comm"] == "kworker/0:1"
        assert deadlock.extracted["secs"] == "120"


class TestMultiLineAggregation:
    """Test multi-line context aggregation for complex incidents."""

    def test_panic_has_context(self, incidents):
        """Test that Panic incident aggregates multi-line context."""
        panic = [inc for inc in incidents if inc.type == "PANIC"][0]

        # Panic should have context lines (stack trace)
        assert len(panic.context) > 0, "Panic should have multi-line context"
        # Context should include following lines until time gap or end marker
        assert any("panic stack trace" in line for line in panic.context), \
            "Panic context should include stack trace lines"

    def test_deadlock_has_context(self, incidents):
        """Test that Deadlock incident aggregates multi-line context."""
        deadlock = [inc for inc in incidents if inc.type == "DEADLOCK"][0]

        # Deadlock should have context lines
        assert len(deadlock.context) > 0, "Deadlock should have multi-line context"
        # Context should include task state and call trace
        assert any("Tainted:" in line or "Call Trace" in line or "schedule" in line
                   for line in deadlock.context), \
            "Deadlock context should include task state or call trace"

    def test_oops_has_context(self, incidents):
        """Test that Oops incident aggregates multi-line context."""
        oops = [inc for inc in incidents if inc.type == "OOPS"][0]

        # Oops should have context (Call Trace)
        assert len(oops.context) > 0, "Oops should have multi-line context"


class TestCooldown:
    """Test cooldown mechanism to prevent duplicate alerts."""

    def test_cooldown_prevents_duplicates(self, config):
        """Test that cooldown prevents rapid duplicate incidents."""
        # Create a log with duplicate OOM events
        duplicate_log = [
            (1, "Dec 24 17:40:10 kernel: Out of memory: Killed process 1234 (python3)\n"),
            (2, "Dec 24 17:40:11 kernel: Out of memory: Killed process 1234 (python3)\n"),  # Duplicate
            (3, "Dec 24 17:40:12 kernel: Out of memory: Killed process 1234 (python3)\n"),  # Duplicate
        ]

        incidents = detect_lines(iter(duplicate_log), config.rules)

        # Cooldown should prevent the duplicates (same pid, comm, and message prefix)
        # Only the first one should be detected
        oom_incidents = [inc for inc in incidents if inc.type == "OOM"]
        assert len(oom_incidents) == 1, "Cooldown should prevent duplicate OOM incidents"

    def test_different_process_not_cooldown(self, config):
        """Test that cooldown doesn't suppress incidents from different processes."""
        # Create a log with OOM events for different processes
        different_procs = [
            (1, "Dec 24 17:40:10 kernel: Out of memory: Killed process 1234 (python3)\n"),
            (2, "Dec 24 17:40:11 kernel: Out of memory: Killed process 5678 (java)\n"),  # Different process
        ]

        incidents = detect_lines(iter(different_procs), config.rules)

        # Both should be detected (different processes)
        oom_incidents = [inc for inc in incidents if inc.type == "OOM"]
        assert len(oom_incidents) == 2, "Different processes should not be affected by cooldown"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_log(self, config):
        """Test detection on empty log."""
        empty_log = iter([])
        incidents = detect_lines(empty_log, config.rules)
        assert len(incidents) == 0, "Empty log should produce no incidents"

    def test_no_matches(self, config):
        """Test log with no matching patterns."""
        normal_log = [
            (1, "Dec 24 17:40:01 kernel: Normal log message\n"),
            (2, "Dec 24 17:40:02 kernel: Another normal message\n"),
        ]
        incidents = detect_lines(iter(normal_log), config.rules)
        assert len(incidents) == 0, "Normal log should produce no incidents"

    def test_incident_types_are_unique(self, incidents):
        """Test that each incident has a unique type in our test log."""
        types = [inc.type for inc in incidents]
        # All 6 types should be present and each appears once
        assert len(set(types)) == 6, "Should have 6 unique incident types"
        assert sorted(types) == sorted(["OOM", "OOPS", "PANIC", "DEADLOCK", "REBOOT", "FS_EXCEPTION"])
