"""Apple Calendar 데이터 모델"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field


def _convert_datetime(v: object) -> datetime:
    """NSDate / ISO 문자열 / datetime → datetime 변환"""
    # PyObjC NSDate → datetime
    if hasattr(v, "timeIntervalSince1970"):
        return datetime.fromtimestamp(v.timeIntervalSince1970())
    if isinstance(v, str):
        return datetime.fromisoformat(v)
    if isinstance(v, datetime):
        return v
    raise ValueError(f"Cannot convert {type(v)} to datetime")


FlexibleDateTime = Annotated[datetime, BeforeValidator(_convert_datetime)]


class RecurrenceRule(BaseModel):
    """반복 규칙"""

    frequency: Literal["daily", "weekly", "monthly", "yearly"]
    interval: int = 1
    end_date: datetime | None = None


class Event(BaseModel):
    """캘린더 이벤트"""

    identifier: str
    title: str
    start_time: FlexibleDateTime
    end_time: FlexibleDateTime
    calendar_name: str = ""
    location: str | None = None
    notes: str | None = None
    url: str | None = None
    all_day: bool = False
    is_recurring: bool = False

    def __str__(self) -> str:
        time_fmt = "%Y-%m-%d" if self.all_day else "%Y-%m-%d %H:%M"
        start = self.start_time.strftime(time_fmt)
        end = self.end_time.strftime(time_fmt)
        parts = [f"{self.title} ({start} ~ {end})"]
        if self.calendar_name:
            parts.append(f"[{self.calendar_name}]")
        if self.location:
            parts.append(f"@ {self.location}")
        parts.append(f"ID: {self.identifier}")
        return " | ".join(parts)

    @classmethod
    def from_ekevent(cls, ekevent: object) -> Event:
        """EKEvent → Event 변환"""
        return cls(
            identifier=str(ekevent.eventIdentifier()),
            title=str(ekevent.title() or ""),
            start_time=ekevent.startDate(),
            end_time=ekevent.endDate(),
            calendar_name=str(ekevent.calendar().title()) if ekevent.calendar() else "",
            location=str(ekevent.location()) if ekevent.location() else None,
            notes=str(ekevent.notes()) if ekevent.notes() else None,
            url=str(ekevent.URL()) if ekevent.URL() else None,
            all_day=bool(ekevent.isAllDay()),
            is_recurring=ekevent.hasRecurrenceRules(),
        )


class CreateEventRequest(BaseModel):
    """이벤트 생성 요청"""

    title: str
    start_time: datetime
    end_time: datetime
    calendar_name: str | None = Field(default=None, description="캘린더 이름 (미지정 시 기본 캘린더)")
    location: str | None = None
    notes: str | None = None
    alarms_minutes_offsets: list[int] | None = Field(
        default=None, description="알림 (분 단위). 예: [15, 60] = 15분 전, 1시간 전"
    )
    url: str | None = None
    all_day: bool = False
    recurrence_rule: RecurrenceRule | None = None


class UpdateEventRequest(BaseModel):
    """이벤트 수정 요청 (지정된 필드만 업데이트)"""

    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    calendar_name: str | None = None
    location: str | None = None
    notes: str | None = None
    alarms_minutes_offsets: list[int] | None = None
    url: str | None = None
    all_day: bool | None = None
    recurrence_rule: RecurrenceRule | None = None
