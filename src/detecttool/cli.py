from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Any
import typer
from rich.console import Console
from rich.table import Table
from .engine import detect_lines, Detector, MultiLineAggregator, Incident
from .sources.file_follow import follow_file
from .config import load_config

app = typer.Typer(help="SuSG2025 DetectTool - Linux abnormal log detection")
console = Console()


def _iter_file_lines(path: str):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                yield i, line
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Log file not found: {path}\n"
            f"Please check the file path and try again"
        )
    except PermissionError:
        raise PermissionError(
            f"Permission denied: {path}\n"
            f"Please ensure you have read permission for this file"
        )


@app.command()
def scan(
    file: str = typer.Option(..., "--file", "-f", help="Path to a log file to scan"),
    config: str = typer.Option("configs/rules.yaml", "--config", "-c", help="Path to rules YAML"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON instead of table"),
):
    try:
        cfg = load_config(config)
        incidents = detect_lines(_iter_file_lines(file), cfg.rules)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)
    except PermissionError as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)

    if json_out:
        print(json.dumps([x.to_dict() for x in incidents], ensure_ascii=False, indent=2))
        raise typer.Exit(0)

    table = Table(title=f"Incidents ({len(incidents)})")
    table.add_column("Line", justify="right")
    table.add_column("Type")
    table.add_column("Severity")
    table.add_column("Rule")
    table.add_column("Extracted")
    table.add_column("Ctx", justify="right")
    table.add_column("Message", overflow="fold")

    for inc in incidents:
        table.add_row(
            str(inc.line_no),
            inc.type,
            inc.severity,
            inc.rule_id,
            json.dumps(inc.extracted, ensure_ascii=False),
            str(len(inc.context)),
            inc.message,
        )

    console.print(table)

@app.command()
def monitor(
    file: str = typer.Option(..., "--file", "-f", help="Path to a log file to follow (tail -f)"),
    config: str = typer.Option("configs/rules.yaml", "--config", "-c", help="Path to rules YAML"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON lines (one incident per line)"),
    from_start: bool = typer.Option(False, "--from-start", help="Read file from beginning (default: follow new lines only)"),
    poll_interval: float = typer.Option(0.2, "--poll", help="Polling interval seconds for file follow"),
):
    try:
        cfg = load_config(config)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)

    detector = Detector(cfg.rules)
    agg = MultiLineAggregator(detector)
    console.print(f"[green]Monitoring[/green] {file}  (Ctrl+C to stop)")
    console.print(f"Config: {config} | from_start={from_start} | poll={poll_interval}s")

    try:
         for line_no, line in follow_file(
            file,
            start_at_end=(not from_start),
            poll_interval=poll_interval,
            yield_heartbeat=True,  # 关键：让 idle flush 生效
        ):
            hits = agg.process(line_no, line)
            for inc in hits:
                if json_out:
                    print(json.dumps(inc.to_dict(), ensure_ascii=False))
                else:
                    console.print(
                        f"[bold]{inc.type}[/bold] "
                        f"[dim](rule={inc.rule_id}, severity={inc.severity}, line={inc.line_no})[/dim]\n"
                        f"{inc.message}\n"
                        f"[dim]extracted={json.dumps(inc.extracted, ensure_ascii=False)}[/dim]"
                    )
                    if inc.context:
                        console.print(f"[dim]--- context ({len(inc.context)}) ---[/dim]")
                        for l in inc.context[:30]:
                            console.print(f"[dim]{l}[/dim]")
                        if len(inc.context) > 30:
                            console.print(f"[dim]... ({len(inc.context)-30} more)[/dim]")
                    console.print("")  # 空行分隔
    except KeyboardInterrupt:
        # 退出前 flush 一下，避免最后一个块丢失
        for inc in agg.flush():
            if json_out:
                print(json.dumps(inc.to_dict(), ensure_ascii=False))
            else:
                console.print(
                    f"[bold]{inc.type}[/bold] "
                    f"[dim](rule={inc.rule_id}, severity={inc.severity}, line={inc.line_no})[/dim]\n"
                    f"{inc.message}\n"
                    f"[dim]extracted={json.dumps(inc.extracted, ensure_ascii=False)}[/dim]"
                )
                if inc.context:
                    console.print(f"[dim]--- context ({len(inc.context)}) ---[/dim]")
                    for l in inc.context[:30]:
                        console.print(f"[dim]{l}[/dim]")
                    if len(inc.context) > 30:
                        console.print(f"[dim]... ({len(inc.context)-30} more)[/dim]")
                console.print("")
        console.print("[yellow]Stopped.[/yellow]")


def _generate_statistics(incidents: List[Incident], total_lines: int, top_n: int = 10) -> Dict[str, Any]:
    """
    Generate statistics from detected incidents.

    Args:
        incidents: List of detected incidents
        total_lines: Total number of lines scanned
        top_n: Number of top items to include in rankings

    Returns:
        Dictionary containing all statistics
    """
    total = len(incidents)

    # Count by type
    type_counts = Counter(inc.type for inc in incidents)

    # Count by severity
    severity_counts = Counter(inc.severity for inc in incidents)

    # Count by rule ID
    rule_counts = Counter(inc.rule_id for inc in incidents)

    # Extract and count process names (comm)
    comm_list = [inc.extracted.get('comm') for inc in incidents if inc.extracted.get('comm')]
    comm_counts = Counter(comm_list)

    # Extract and count PIDs
    pid_list = [inc.extracted.get('pid') for inc in incidents if inc.extracted.get('pid')]
    pid_counts = Counter(pid_list)

    return {
        'total_lines_scanned': total_lines,
        'total_incidents': total,
        'unique_types': len(type_counts),
        'by_type': dict(type_counts),
        'by_severity': dict(severity_counts),
        'by_rule': dict(rule_counts),
        'top_processes': comm_counts.most_common(top_n),
        'top_pids': pid_counts.most_common(top_n),
    }


@app.command()
def stats(
    file: str = typer.Option(..., "--file", "-f", help="Path to a log file to analyze"),
    config: str = typer.Option("configs/rules.yaml", "--config", "-c", help="Path to rules YAML"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON instead of tables"),
    top: int = typer.Option(10, "--top", "-n", help="Show top N items in rankings"),
):
    """
    Analyze log file and show statistics of detected incidents.

    Provides statistics by type, severity, and top affected processes/PIDs.
    """
    try:
        cfg = load_config(config)

        # Scan the log file (single pass)
        total_lines = 0
        lines_with_tracking = []
        for line_no, line in _iter_file_lines(file):
            lines_with_tracking.append((line_no, line))
            total_lines = line_no

        incidents = detect_lines(iter(lines_with_tracking), cfg.rules)
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)
    except PermissionError as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}", style="red")
        raise typer.Exit(1)

    # Generate statistics
    stats_data = _generate_statistics(incidents, total_lines, top_n=top)

    # JSON output
    if json_out:
        print(json.dumps(stats_data, ensure_ascii=False, indent=2))
        raise typer.Exit(0)

    # Rich table output
    total = stats_data['total_incidents']

    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]    Log Analysis Statistics Report    [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")

    # Overview
    console.print(f"[bold]Total lines scanned:[/bold] {stats_data['total_lines_scanned']:,}")
    console.print(f"[bold]Total incidents detected:[/bold] {total:,}")
    console.print(f"[bold]Unique incident types:[/bold] {stats_data['unique_types']}\n")

    if total == 0:
        console.print("[yellow]No incidents detected in the log file.[/yellow]")
        return

    # Table 1: Incidents by Type
    type_table = Table(title="Incidents by Type", show_header=True, header_style="bold magenta")
    type_table.add_column("Type", style="cyan", width=20)
    type_table.add_column("Count", justify="right", style="green")
    type_table.add_column("Percentage", justify="right", style="yellow")

    for type_name, count in sorted(stats_data['by_type'].items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total) * 100
        type_table.add_row(type_name, str(count), f"{percentage:.1f}%")

    console.print(type_table)
    console.print()

    # Table 2: Incidents by Severity
    severity_table = Table(title="Incidents by Severity", show_header=True, header_style="bold magenta")
    severity_table.add_column("Severity", style="cyan", width=20)
    severity_table.add_column("Count", justify="right", style="green")
    severity_table.add_column("Percentage", justify="right", style="yellow")

    # Sort by severity level (critical > high > medium > low)
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    for severity, count in sorted(stats_data['by_severity'].items(),
                                  key=lambda x: severity_order.get(x[0], 99)):
        percentage = (count / total) * 100
        severity_table.add_row(severity, str(count), f"{percentage:.1f}%")

    console.print(severity_table)
    console.print()

    # Table 3: Top N Processes (if any)
    if stats_data['top_processes']:
        proc_table = Table(title=f"Top {min(top, len(stats_data['top_processes']))} Affected Processes",
                          show_header=True, header_style="bold magenta")
        proc_table.add_column("Rank", style="dim", width=6, justify="right")
        proc_table.add_column("Process Name", style="cyan")
        proc_table.add_column("Incidents", justify="right", style="green")

        for rank, (proc_name, count) in enumerate(stats_data['top_processes'], start=1):
            proc_table.add_row(str(rank), proc_name, str(count))

        console.print(proc_table)
        console.print()

    # Table 4: Top N PIDs (if any)
    if stats_data['top_pids']:
        pid_table = Table(title=f"Top {min(top, len(stats_data['top_pids']))} Affected PIDs",
                         show_header=True, header_style="bold magenta")
        pid_table.add_column("Rank", style="dim", width=6, justify="right")
        pid_table.add_column("PID", style="cyan")
        pid_table.add_column("Incidents", justify="right", style="green")

        for rank, (pid, count) in enumerate(stats_data['top_pids'], start=1):
            pid_table.add_row(str(rank), pid, str(count))

        console.print(pid_table)
        console.print()

    # Table 5: Incidents by Rule (only if reasonable number of rules)
    if len(stats_data['by_rule']) <= top:
        rule_table = Table(title="Incidents by Detection Rule",
                          show_header=True, header_style="bold magenta")
        rule_table.add_column("Rule ID", style="cyan")
        rule_table.add_column("Count", justify="right", style="green")

        for rule_id, count in sorted(stats_data['by_rule'].items(), key=lambda x: x[1], reverse=True):
            rule_table.add_row(rule_id, str(count))

        console.print(rule_table)
    else:
        # Show only top N rules if there are too many
        rule_table = Table(title=f"Top {top} Detection Rules",
                          show_header=True, header_style="bold magenta")
        rule_table.add_column("Rank", style="dim", width=6, justify="right")
        rule_table.add_column("Rule ID", style="cyan")
        rule_table.add_column("Count", justify="right", style="green")

        top_rules = sorted(stats_data['by_rule'].items(), key=lambda x: x[1], reverse=True)[:top]
        for rank, (rule_id, count) in enumerate(top_rules, start=1):
            rule_table.add_row(str(rank), rule_id, str(count))

        console.print(rule_table)

    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]\n")


# -------------------------
# Daemon / Service Management
# -------------------------

SYSTEMD_SERVICE_TEMPLATE = """\
[Unit]
Description=SuSG DetectTool - Linux Abnormal Log Detection Daemon
Documentation=https://github.com/e-wanerer/SuSG2025-DetectTool
After=syslog.target network.target

[Service]
Type=simple
ExecStart={detecttool_path} monitor -f {log_file} -c {config_path} --json
Restart=on-failure
RestartSec=5
User=root

StandardOutput=append:{output_dir}/incidents.log
StandardError=append:{output_dir}/error.log

[Install]
WantedBy=multi-user.target
"""


def _find_detecttool_path() -> str:
    """Find the detecttool executable path."""
    # Try to find in PATH
    which_result = shutil.which("detecttool")
    if which_result:
        return which_result

    # Fallback: use python -m detecttool.cli
    return f"{sys.executable} -m detecttool.cli"


def _get_absolute_config_path(config: str) -> str:
    """Convert config path to absolute path."""
    config_path = Path(config)
    if config_path.is_absolute():
        return str(config_path)

    # If relative, make it absolute from current working directory
    return str(Path.cwd() / config_path)


def _run_systemctl(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run systemctl command."""
    cmd = ["systemctl"] + args
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] systemctl not found. This command requires systemd.")
        raise typer.Exit(1)


@app.command("install-service")
def install_service(
    log_file: str = typer.Option(
        "/var/log/kern.log",
        "--log-file", "-f",
        help="Log file to monitor"
    ),
    config: str = typer.Option(
        "/etc/detecttool/rules.yaml",
        "--config", "-c",
        help="Path to rules YAML (will be used by the service)"
    ),
    output_dir: str = typer.Option(
        "/var/log/detecttool",
        "--output-dir", "-o",
        help="Directory for output logs"
    ),
    service_name: str = typer.Option(
        "detecttool",
        "--name",
        help="Service name"
    ),
):
    """
    Install systemd service for daemon mode.

    Generates and installs a systemd unit file to run detecttool as a
    background service that monitors log files for system abnormalities.

    Example:
        sudo detecttool install-service -f /var/log/kern.log
    """
    # Check if running as root
    if os.geteuid() != 0:
        console.print("[bold red]Error:[/bold red] This command requires root privileges.")
        console.print("Please run with: [bold]sudo detecttool install-service ...[/bold]")
        raise typer.Exit(1)

    # Check if log file exists
    if not Path(log_file).exists():
        console.print(f"[bold yellow]Warning:[/bold yellow] Log file '{log_file}' does not exist.")
        console.print("The service will wait for the file to be created.")

    # Find detecttool path
    detecttool_path = _find_detecttool_path()
    console.print(f"[dim]DetectTool path: {detecttool_path}[/dim]")

    # Get absolute config path
    config_path = _get_absolute_config_path(config)

    # Create output directory
    output_path = Path(output_dir)
    if not output_path.exists():
        output_path.mkdir(parents=True, mode=0o755)
        console.print(f"[green]Created[/green] output directory: {output_dir}")

    # Generate service file content
    service_content = SYSTEMD_SERVICE_TEMPLATE.format(
        detecttool_path=detecttool_path,
        log_file=log_file,
        config_path=config_path,
        output_dir=output_dir,
    )

    # Write service file
    service_file = Path(f"/etc/systemd/system/{service_name}.service")
    service_file.write_text(service_content)
    console.print(f"[green]Created[/green] service file: {service_file}")

    # Reload systemd
    result = _run_systemctl(["daemon-reload"])
    if result.returncode == 0:
        console.print("[green]Reloaded[/green] systemd daemon")

    # Print usage instructions
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   Service Installation Complete!     [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")

    console.print("[bold]Service Configuration:[/bold]")
    console.print(f"  Service name:  {service_name}")
    console.print(f"  Log file:      {log_file}")
    console.print(f"  Config:        {config_path}")
    console.print(f"  Output dir:    {output_dir}")

    console.print("\n[bold]Management Commands:[/bold]")
    console.print(f"  Start:         [cyan]sudo systemctl start {service_name}[/cyan]")
    console.print(f"  Stop:          [cyan]sudo systemctl stop {service_name}[/cyan]")
    console.print(f"  Restart:       [cyan]sudo systemctl restart {service_name}[/cyan]")
    console.print(f"  Status:        [cyan]sudo systemctl status {service_name}[/cyan]")
    console.print(f"  Enable boot:   [cyan]sudo systemctl enable {service_name}[/cyan]")
    console.print(f"  Disable boot:  [cyan]sudo systemctl disable {service_name}[/cyan]")

    console.print("\n[bold]View Logs:[/bold]")
    console.print(f"  Incidents:     [cyan]tail -f {output_dir}/incidents.log[/cyan]")
    console.print(f"  Errors:        [cyan]tail -f {output_dir}/error.log[/cyan]")
    console.print(f"  Journal:       [cyan]journalctl -u {service_name} -f[/cyan]")

    console.print("\n[bold]Quick Start:[/bold]")
    console.print(f"  [cyan]sudo systemctl enable --now {service_name}[/cyan]")


@app.command("uninstall-service")
def uninstall_service(
    service_name: str = typer.Option(
        "detecttool",
        "--name",
        help="Service name to uninstall"
    ),
    remove_logs: bool = typer.Option(
        False,
        "--remove-logs",
        help="Also remove log files in /var/log/detecttool"
    ),
):
    """
    Stop and remove the systemd service.

    Example:
        sudo detecttool uninstall-service
        sudo detecttool uninstall-service --remove-logs
    """
    # Check if running as root
    if os.geteuid() != 0:
        console.print("[bold red]Error:[/bold red] This command requires root privileges.")
        console.print("Please run with: [bold]sudo detecttool uninstall-service[/bold]")
        raise typer.Exit(1)

    service_file = Path(f"/etc/systemd/system/{service_name}.service")

    if not service_file.exists():
        console.print(f"[bold yellow]Warning:[/bold yellow] Service file not found: {service_file}")
        console.print("Service may not be installed.")
        raise typer.Exit(0)

    # Stop service if running
    console.print(f"[dim]Stopping {service_name} service...[/dim]")
    _run_systemctl(["stop", service_name], check=False)

    # Disable service
    console.print(f"[dim]Disabling {service_name} service...[/dim]")
    _run_systemctl(["disable", service_name], check=False)

    # Remove service file
    service_file.unlink()
    console.print(f"[green]Removed[/green] service file: {service_file}")

    # Reload systemd
    _run_systemctl(["daemon-reload"])
    console.print("[green]Reloaded[/green] systemd daemon")

    # Remove logs if requested
    if remove_logs:
        log_dir = Path("/var/log/detecttool")
        if log_dir.exists():
            shutil.rmtree(log_dir)
            console.print(f"[green]Removed[/green] log directory: {log_dir}")

    console.print(f"\n[bold green]Service '{service_name}' has been uninstalled.[/bold green]")


@app.command("service-status")
def service_status(
    service_name: str = typer.Option(
        "detecttool",
        "--name",
        help="Service name to check"
    ),
):
    """
    Show daemon service status.

    Example:
        detecttool service-status
    """
    service_file = Path(f"/etc/systemd/system/{service_name}.service")

    if not service_file.exists():
        console.print(f"[bold yellow]Service not installed[/bold yellow]")
        console.print(f"Service file not found: {service_file}")
        console.print(f"\nTo install: [cyan]sudo detecttool install-service -f /var/log/kern.log[/cyan]")
        raise typer.Exit(0)

    # Get service status
    result = _run_systemctl(["is-active", service_name], check=False)
    is_active = result.stdout.strip() == "active"

    result = _run_systemctl(["is-enabled", service_name], check=False)
    is_enabled = result.stdout.strip() == "enabled"

    # Display status
    console.print(f"\n[bold]Service:[/bold] {service_name}")

    if is_active:
        console.print(f"[bold]Status:[/bold]  [bold green]running[/bold green]")
    else:
        console.print(f"[bold]Status:[/bold]  [bold red]stopped[/bold red]")

    if is_enabled:
        console.print(f"[bold]Boot:[/bold]    [green]enabled[/green]")
    else:
        console.print(f"[bold]Boot:[/bold]    [yellow]disabled[/yellow]")

    # Show log file stats if available
    incidents_log = Path("/var/log/detecttool/incidents.log")
    if incidents_log.exists():
        stat = incidents_log.stat()
        size_kb = stat.st_size / 1024
        console.print(f"\n[bold]Incidents Log:[/bold] {incidents_log}")
        console.print(f"  Size: {size_kb:.1f} KB")

        # Count incidents (lines in JSON log)
        try:
            with open(incidents_log, "r") as f:
                line_count = sum(1 for _ in f)
            console.print(f"  Incidents: {line_count}")
        except Exception:
            pass

    # Show detailed status from systemctl
    console.print(f"\n[dim]─── systemctl status {service_name} ───[/dim]")
    result = subprocess.run(
        ["systemctl", "status", service_name, "--no-pager", "-l"],
        capture_output=True,
        text=True,
    )
    # Print status output (trim to reasonable length)
    lines = result.stdout.split("\n")[:15]
    for line in lines:
        console.print(f"[dim]{line}[/dim]")

