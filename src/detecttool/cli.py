from __future__ import annotations
import json
import typer
from rich.console import Console
from rich.table import Table
from .engine import detect_lines, Detector, MultiLineAggregator
from .sources.file_follow import follow_file

from .config import load_config
from .engine import detect_lines

app = typer.Typer(help="SuSG2025 DetectTool - Linux abnormal log detection")
console = Console()


def _iter_file_lines(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, start=1):
            yield i, line


@app.command()
def scan(
    file: str = typer.Option(..., "--file", "-f", help="Path to a log file to scan"),
    config: str = typer.Option("configs/rules.yaml", "--config", "-c", help="Path to rules YAML"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON instead of table"),
):
    cfg = load_config(config)
    incidents = detect_lines(_iter_file_lines(file), cfg.rules)

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
    cfg = load_config(config)
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


@app.command()
def stats():
    """Statistics (placeholder)."""
    console.print("[yellow]stats: TODO (will be implemented later)[/yellow]")

