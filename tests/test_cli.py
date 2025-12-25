"""
Test cases for CLI commands.

Tests cover:
- scan command functionality
- stats command functionality
- JSON output format
- Error handling
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path
from typer.testing import CliRunner
from detecttool.cli import app


# Test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_LOG = FIXTURES_DIR / "test.log"
CONFIG_PATH = Path(__file__).parent.parent / "configs" / "rules.yaml"

runner = CliRunner()


class TestScanCommand:
    """Test the scan command."""

    def test_scan_basic(self):
        """Test basic scan command execution."""
        result = runner.invoke(app, [
            "scan",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
        ])

        assert result.exit_code == 0, f"Scan command failed: {result.stdout}"
        assert "Incidents" in result.stdout, "Output should contain 'Incidents'"

    def test_scan_json_output(self):
        """Test scan command with JSON output."""
        result = runner.invoke(app, [
            "scan",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
            "--json",
        ])

        assert result.exit_code == 0, f"Scan JSON command failed: {result.stdout}"

        # Parse JSON output
        try:
            incidents = json.loads(result.stdout)
            assert isinstance(incidents, list), "JSON output should be a list"
            assert len(incidents) == 6, "Should detect 6 incidents"

            # Check structure of first incident
            if incidents:
                inc = incidents[0]
                assert "rule_id" in inc
                assert "type" in inc
                assert "severity" in inc
                assert "message" in inc
                assert "line_no" in inc
                assert "extracted" in inc
                assert "context" in inc

        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}\n{result.stdout}")

    def test_scan_detects_all_types(self):
        """Test that scan detects all 6 abnormal types."""
        result = runner.invoke(app, [
            "scan",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
            "--json",
        ])

        assert result.exit_code == 0

        incidents = json.loads(result.stdout)
        detected_types = {inc["type"] for inc in incidents}

        expected_types = {"OOM", "OOPS", "PANIC", "DEADLOCK", "REBOOT", "FS_EXCEPTION"}
        assert detected_types == expected_types, \
            f"Should detect all 6 types. Got: {detected_types}"

    def test_scan_file_not_found(self):
        """Test scan command with non-existent file."""
        result = runner.invoke(app, [
            "scan",
            "--file", "/tmp/nonexistent_file_12345.log",
            "--config", str(CONFIG_PATH),
        ])

        # Should fail with non-zero exit code
        assert result.exit_code != 0


class TestStatsCommand:
    """Test the stats command."""

    def test_stats_basic(self):
        """Test basic stats command execution."""
        result = runner.invoke(app, [
            "stats",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
        ])

        assert result.exit_code == 0, f"Stats command failed: {result.stdout}"
        assert "Log Analysis Statistics Report" in result.stdout
        assert "Total lines scanned" in result.stdout
        assert "Total incidents detected" in result.stdout

    def test_stats_json_output(self):
        """Test stats command with JSON output."""
        result = runner.invoke(app, [
            "stats",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
            "--json",
        ])

        assert result.exit_code == 0, f"Stats JSON command failed: {result.stdout}"

        # Parse JSON output
        try:
            stats = json.loads(result.stdout)
            assert isinstance(stats, dict), "JSON output should be a dict"

            # Check required fields
            assert "total_lines_scanned" in stats
            assert "total_incidents" in stats
            assert "unique_types" in stats
            assert "by_type" in stats
            assert "by_severity" in stats
            assert "by_rule" in stats
            assert "top_processes" in stats
            assert "top_pids" in stats

            # Check values
            assert stats["total_incidents"] == 6
            assert stats["unique_types"] == 6

        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}\n{result.stdout}")

    def test_stats_counts_accuracy(self):
        """Test that stats produces accurate counts."""
        result = runner.invoke(app, [
            "stats",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
            "--json",
        ])

        stats = json.loads(result.stdout)

        # Check type counts
        by_type = stats["by_type"]
        assert by_type["OOM"] == 1
        assert by_type["OOPS"] == 1
        assert by_type["PANIC"] == 1
        assert by_type["DEADLOCK"] == 1
        assert by_type["REBOOT"] == 1
        assert by_type["FS_EXCEPTION"] == 1

        # Check severity counts
        by_severity = stats["by_severity"]
        assert by_severity["high"] == 4
        assert by_severity["critical"] == 1
        assert by_severity["medium"] == 1

    def test_stats_top_n_parameter(self):
        """Test stats command with --top parameter."""
        result = runner.invoke(app, [
            "stats",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
            "--top", "3",
            "--json",
        ])

        assert result.exit_code == 0

        stats = json.loads(result.stdout)

        # top_processes and top_pids should respect the limit
        # In our test case, we have 2 processes and 2 PIDs, so both should be <= 3
        assert len(stats["top_processes"]) <= 3
        assert len(stats["top_pids"]) <= 3

    def test_stats_displays_tables(self):
        """Test that stats displays all required tables in non-JSON mode."""
        result = runner.invoke(app, [
            "stats",
            "--file", str(TEST_LOG),
            "--config", str(CONFIG_PATH),
        ])

        assert result.exit_code == 0

        output = result.stdout

        # Check for table titles
        assert "Incidents by Type" in output
        assert "Incidents by Severity" in output
        assert "Affected Processes" in output or "Top" in output
        assert "Affected PIDs" in output or "Top" in output
        assert "Detection Rule" in output

    def test_stats_file_not_found(self):
        """Test stats command with non-existent file."""
        result = runner.invoke(app, [
            "stats",
            "--file", "/tmp/nonexistent_file_12345.log",
            "--config", str(CONFIG_PATH),
        ])

        # Should fail with non-zero exit code
        assert result.exit_code != 0


class TestEdgeCases:
    """Test edge cases for CLI commands."""

    def test_stats_empty_log(self, tmp_path):
        """Test stats on a log with no incidents."""
        # Create an empty log file
        empty_log = tmp_path / "empty.log"
        empty_log.write_text("Dec 24 17:40:01 kernel: Normal log message\n")

        result = runner.invoke(app, [
            "stats",
            "--file", str(empty_log),
            "--config", str(CONFIG_PATH),
        ])

        assert result.exit_code == 0
        assert "No incidents detected" in result.stdout

    def test_stats_empty_log_json(self, tmp_path):
        """Test stats JSON output on a log with no incidents."""
        empty_log = tmp_path / "empty.log"
        empty_log.write_text("Dec 24 17:40:01 kernel: Normal log message\n")

        result = runner.invoke(app, [
            "stats",
            "--file", str(empty_log),
            "--config", str(CONFIG_PATH),
            "--json",
        ])

        assert result.exit_code == 0

        stats = json.loads(result.stdout)
        assert stats["total_incidents"] == 0
        assert stats["unique_types"] == 0
