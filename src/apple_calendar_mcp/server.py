"""Apple Calendar MCP Server"""

from __future__ import annotations

from datetime import datetime

from mcp.server.fastmcp import FastMCP

from apple_calendar_mcp.calendar import (
    CalendarError,
    CalendarManager,
    NoSuchCalendarError,
    NoSuchEventError,
)
from apple_calendar_mcp.models import CreateEventRequest, UpdateEventRequest

mcp = FastMCP("apple-calendar")

_manager: CalendarManager | None = None


def _get_manager() -> CalendarManager:
    global _manager
    if _manager is None:
        _manager = CalendarManager()
    return _manager


# --- Resource ---


@mcp.resource("calendars://list")
def resource_calendars() -> str:
    """사용 가능한 캘린더 목록"""
    try:
        calendars = _get_manager().list_calendars()
        return "\n".join(f"- {name}" for name in calendars)
    except Exception as e:
        return f"Error: {e}"


# --- Tools ---


@mcp.tool()
async def list_events(
    start_date: datetime,
    end_date: datetime,
    calendar_name: str | None = None,
) -> str:
    """기간별 캘린더 이벤트 조회

    Args:
        start_date: 시작일시 (ISO 8601, 예: 2026-02-10T00:00:00)
        end_date: 종료일시 (ISO 8601, 예: 2026-02-17T23:59:59)
        calendar_name: 캘린더 이름 (미지정 시 모든 캘린더)
    """
    try:
        events = _get_manager().list_events(start_date, end_date, calendar_name)
        if not events:
            return "해당 기간에 이벤트가 없습니다."
        return "\n".join(str(e) for e in events)
    except NoSuchCalendarError as e:
        return f"Error: {e}"
    except CalendarError as e:
        return f"Error: {e}"


@mcp.tool()
async def search_events(
    keyword: str,
    calendar_name: str | None = None,
) -> str:
    """키워드로 이벤트 검색 (제목, 메모, 장소에서 검색)

    Args:
        keyword: 검색 키워드
        calendar_name: 캘린더 이름 (미지정 시 모든 캘린더)
    """
    try:
        events = _get_manager().search_events(keyword, calendar_name)
        if not events:
            return f"'{keyword}' 관련 이벤트를 찾을 수 없습니다."
        return f"검색 결과 ({len(events)}건):\n" + "\n".join(str(e) for e in events)
    except CalendarError as e:
        return f"Error: {e}"


@mcp.tool()
async def create_event(create_event_request: CreateEventRequest) -> str:
    """새 캘린더 이벤트 생성

    Args:
        create_event_request: 이벤트 정보 (title, start_time, end_time 필수)
    """
    try:
        event = _get_manager().create_event(create_event_request)
        if not event:
            return "이벤트 생성에 실패했습니다."
        return f"이벤트 생성 완료: {event.title} (ID: {event.identifier})"
    except CalendarError as e:
        return f"Error: {e}"


@mcp.tool()
async def update_event(
    event_id: str,
    update_event_request: UpdateEventRequest,
) -> str:
    """기존 이벤트 수정

    Args:
        event_id: 이벤트 ID (list_events/search_events 결과에서 확인)
        update_event_request: 수정할 필드들
    """
    try:
        event = _get_manager().update_event(event_id, update_event_request)
        return f"이벤트 수정 완료: {event.title} (ID: {event.identifier})"
    except NoSuchEventError as e:
        return f"Error: {e}"
    except CalendarError as e:
        return f"Error: {e}"


@mcp.tool()
async def delete_event(event_id: str) -> str:
    """이벤트 삭제

    Args:
        event_id: 이벤트 ID (list_events/search_events 결과에서 확인)
    """
    try:
        title = _get_manager().delete_event(event_id)
        return f"이벤트 삭제 완료: {title}"
    except NoSuchEventError as e:
        return f"Error: {e}"
    except CalendarError as e:
        return f"Error: {e}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
