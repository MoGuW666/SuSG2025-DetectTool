from __future__ import annotations
import json
from collections import Counter
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

