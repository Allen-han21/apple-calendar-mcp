"""Apple Calendar CLI"""

from __future__ import annotations

from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

from apple_calendar_mcp.calendar import CalendarManager
from apple_calendar_mcp.models import CreateEventRequest

app = typer.Typer(name="cal", help="Apple Calendar CLI", no_args_is_help=True)
console = Console()


def _mgr() -> CalendarManager:
    return CalendarManager()


@app.command()
def week(
    offset: int = typer.Option(0, "-o", "--offset", help="주 오프셋 (0=이번 주, 1=다음 주, -1=지난 주)"),
):
    """이번 주 일정 조회"""
    mgr = _mgr()
    now = datetime.now()
    start = (now - timedelta(days=now.weekday()) + timedelta(weeks=offset)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(days=7)
    events = mgr.list_events(start, end)

    console.print(f"\n[bold]📅 {start:%m/%d} ~ {end:%m/%d} ({len(events)}건)[/bold]\n")

    current_date = None
    for e in events:
        d = e.start_time.strftime("%m/%d (%a)")
        if d != current_date:
            current_date = d
            console.print(f"[bold cyan]■ {d}[/bold cyan]")

        if e.all_day:
            time_str = "[dim]종일  [/dim]"
        else:
            time_str = f"{e.start_time:%H:%M}~{e.end_time:%H:%M}"

        loc = f" [dim]@ {e.location}[/dim]" if e.location else ""
        console.print(f"  {time_str}  {e.title} [dim][{e.calendar_name}][/dim]{loc}")


@app.command()
def today():
    """오늘 일정 조회"""
    mgr = _mgr()
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = mgr.list_events(start, end)

    console.print(f"\n[bold]📅 오늘 ({now:%m/%d %a}) - {len(events)}건[/bold]\n")
    for e in events:
        if e.all_day:
            time_str = "[dim]종일  [/dim]"
        else:
            time_str = f"{e.start_time:%H:%M}~{e.end_time:%H:%M}"
        loc = f" [dim]@ {e.location}[/dim]" if e.location else ""
        console.print(f"  {time_str}  {e.title} [dim][{e.calendar_name}][/dim]{loc}")


@app.command()
def search(keyword: str = typer.Argument(help="검색 키워드")):
    """이벤트 검색"""
    mgr = _mgr()
    events = mgr.search_events(keyword)

    console.print(f"\n[bold]🔍 '{keyword}' 검색 결과 - {len(events)}건[/bold]\n")
    for e in events:
        if e.all_day:
            time_str = f"{e.start_time:%m/%d} 종일"
        else:
            time_str = f"{e.start_time:%m/%d %H:%M}~{e.end_time:%H:%M}"
        console.print(f"  {time_str}  {e.title} [dim][{e.calendar_name}][/dim]")
        console.print(f"  [dim]ID: {e.identifier}[/dim]")


@app.command()
def add(
    title: str = typer.Argument(help="이벤트 제목"),
    start: str = typer.Argument(help="시작 (예: '2026-02-12T10:00')"),
    end: str = typer.Argument(help="종료 (예: '2026-02-12T11:00')"),
    calendar_name: str = typer.Option(None, "-c", "--calendar", help="캘린더 이름"),
    location: str = typer.Option(None, "-l", "--location", help="장소"),
    notes: str = typer.Option(None, "-n", "--notes", help="메모"),
):
    """이벤트 추가"""
    mgr = _mgr()
    req = CreateEventRequest(
        title=title,
        start_time=datetime.fromisoformat(start),
        end_time=datetime.fromisoformat(end),
        calendar_name=calendar_name,
        location=location,
        notes=notes,
    )
    event = mgr.create_event(req)
    console.print(f"\n[green]✅ 생성: {event.title} ({event.start_time:%m/%d %H:%M}~{event.end_time:%H:%M})[/green]")
    console.print(f"[dim]ID: {event.identifier}[/dim]")


@app.command()
def rm(event_id: str = typer.Argument(help="이벤트 ID")):
    """이벤트 삭제"""
    mgr = _mgr()
    title = mgr.delete_event(event_id)
    console.print(f"\n[red]🗑 삭제: {title}[/red]")


@app.command()
def calendars():
    """캘린더 목록"""
    mgr = _mgr()
    cals = mgr.list_calendars()
    console.print(f"\n[bold]📋 캘린더 ({len(cals)}개)[/bold]\n")
    for c in cals:
        console.print(f"  - {c}")


if __name__ == "__main__":
    app()
