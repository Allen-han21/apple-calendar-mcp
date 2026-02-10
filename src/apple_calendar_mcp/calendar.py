"""EventKit CalendarManager - macOS 캘린더 접근 래퍼"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

import EventKit
from Foundation import NSDate, NSRunLoop

from apple_calendar_mcp.models import (
    CreateEventRequest,
    Event,
    RecurrenceRule,
    UpdateEventRequest,
)

logger = logging.getLogger(__name__)

# EventKit 상수
EKEntityTypeEvent = 0
EKSpanThisEvent = 0
EKSpanFutureEvents = 1
EKAuthorizationStatusAuthorized = 3
EKAuthorizationStatusFullAccess = 4  # macOS 14+


class CalendarError(Exception):
    pass


class NoSuchCalendarError(CalendarError):
    def __init__(self, name: str):
        super().__init__(f"캘린더를 찾을 수 없습니다: {name}")


class NoSuchEventError(CalendarError):
    def __init__(self, event_id: str):
        super().__init__(f"이벤트를 찾을 수 없습니다: {event_id}")


class CalendarManager:
    """macOS EventKit 캘린더 관리자"""

    def __init__(self) -> None:
        self.store = EventKit.EKEventStore.alloc().init()
        self._request_access()

    def _request_access(self) -> None:
        """캘린더 접근 권한 요청 (동기화)"""
        status = EventKit.EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)

        if status in (EKAuthorizationStatusAuthorized, EKAuthorizationStatusFullAccess):
            return

        result = [None]
        done = threading.Event()

        def callback(success: bool, error: object) -> None:
            result[0] = success
            done.set()

        if hasattr(self.store, "requestFullAccessToEventsWithCompletion_"):
            self.store.requestFullAccessToEventsWithCompletion_(callback)
        else:
            self.store.requestAccessToEntityType_completion_(EKEntityTypeEvent, callback)

        # NSRunLoop을 돌려야 콜백이 디스패치됨
        while not done.is_set():
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.1)
            )

        if not result[0]:
            raise CalendarError(
                "캘린더 접근 권한이 거부되었습니다.\n"
                "System Settings > Privacy & Security > Calendar에서 터미널 앱을 허용하세요."
            )

    # --- 캘린더 ---

    def list_calendars(self) -> list[str]:
        """모든 캘린더 이름 목록"""
        calendars = self.store.calendarsForEntityType_(EKEntityTypeEvent)
        return sorted(str(cal.title()) for cal in calendars)

    def _find_calendar(self, name: str | None) -> EventKit.EKCalendar:
        """이름으로 캘린더 찾기. None이면 기본 캘린더."""
        if name is None:
            default = self.store.defaultCalendarForNewEvents()
            if default is None:
                raise CalendarError("기본 캘린더를 찾을 수 없습니다.")
            return default

        for cal in self.store.calendarsForEntityType_(EKEntityTypeEvent):
            if str(cal.title()) == name:
                return cal
        raise NoSuchCalendarError(name)

    # --- 이벤트 조회 ---

    def list_events(
        self,
        start: datetime,
        end: datetime,
        calendar_name: str | None = None,
    ) -> list[Event]:
        """기간별 이벤트 목록"""
        calendars = None
        if calendar_name:
            calendars = [self._find_calendar(calendar_name)]

        ns_start = self._to_nsdate(start)
        ns_end = self._to_nsdate(end)

        predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
            ns_start, ns_end, calendars,
        )
        ek_events = self.store.eventsMatchingPredicate_(predicate)
        if not ek_events:
            return []

        return sorted(
            [Event.from_ekevent(e) for e in ek_events],
            key=lambda e: e.start_time,
        )

    def search_events(
        self,
        keyword: str,
        calendar_name: str | None = None,
        days_back: int = 30,
        days_forward: int = 90,
    ) -> list[Event]:
        """키워드로 이벤트 검색"""
        now = datetime.now()
        start = now - timedelta(days=days_back)
        end = now + timedelta(days=days_forward)
        events = self.list_events(start, end, calendar_name)

        kw = keyword.lower()
        return [
            e for e in events
            if kw in (e.title or "").lower()
            or kw in (e.notes or "").lower()
            or kw in (e.location or "").lower()
        ]

    # --- 이벤트 생성 ---

    def create_event(self, req: CreateEventRequest) -> Event:
        """새 이벤트 생성"""
        ekevent = EventKit.EKEvent.eventWithEventStore_(self.store)
        ekevent.setTitle_(req.title)
        ekevent.setStartDate_(self._to_nsdate(req.start_time))
        ekevent.setEndDate_(self._to_nsdate(req.end_time))
        ekevent.setAllDay_(req.all_day)

        if req.location:
            ekevent.setLocation_(req.location)
        if req.notes:
            ekevent.setNotes_(req.notes)
        if req.url:
            from Foundation import NSURL
            ekevent.setURL_(NSURL.URLWithString_(req.url))

        # 알림
        if req.alarms_minutes_offsets:
            for minutes in req.alarms_minutes_offsets:
                alarm = EventKit.EKAlarm.alarmWithRelativeOffset_(-60 * minutes)
                ekevent.addAlarm_(alarm)

        # 반복
        if req.recurrence_rule:
            ekevent.addRecurrenceRule_(self._to_ek_recurrence(req.recurrence_rule))

        # 캘린더
        calendar = self._find_calendar(req.calendar_name)
        ekevent.setCalendar_(calendar)

        success, error = self.store.saveEvent_span_error_(ekevent, EKSpanThisEvent, None)
        if not success:
            raise CalendarError(f"이벤트 생성 실패: {error}")

        return Event.from_ekevent(ekevent)

    # --- 이벤트 수정 ---

    def update_event(self, event_id: str, req: UpdateEventRequest) -> Event:
        """이벤트 수정"""
        ekevent = self._find_event(event_id)

        if req.title is not None:
            ekevent.setTitle_(req.title)
        if req.start_time is not None:
            ekevent.setStartDate_(self._to_nsdate(req.start_time))
        if req.end_time is not None:
            ekevent.setEndDate_(self._to_nsdate(req.end_time))
        if req.all_day is not None:
            ekevent.setAllDay_(req.all_day)
        if req.location is not None:
            ekevent.setLocation_(req.location)
        if req.notes is not None:
            ekevent.setNotes_(req.notes)
        if req.url is not None:
            from Foundation import NSURL
            ekevent.setURL_(NSURL.URLWithString_(req.url))
        if req.calendar_name is not None:
            ekevent.setCalendar_(self._find_calendar(req.calendar_name))

        # 알림 교체
        if req.alarms_minutes_offsets is not None:
            for alarm in (ekevent.alarms() or []):
                ekevent.removeAlarm_(alarm)
            for minutes in req.alarms_minutes_offsets:
                alarm = EventKit.EKAlarm.alarmWithRelativeOffset_(-60 * minutes)
                ekevent.addAlarm_(alarm)

        # 반복 교체
        if req.recurrence_rule is not None:
            for rule in (ekevent.recurrenceRules() or []):
                ekevent.removeRecurrenceRule_(rule)
            ekevent.addRecurrenceRule_(self._to_ek_recurrence(req.recurrence_rule))

        span = EKSpanFutureEvents if ekevent.hasRecurrenceRules() else EKSpanThisEvent
        success, error = self.store.saveEvent_span_error_(ekevent, span, None)
        if not success:
            raise CalendarError(f"이벤트 수정 실패: {error}")

        return Event.from_ekevent(ekevent)

    # --- 이벤트 삭제 ---

    def delete_event(self, event_id: str) -> str:
        """이벤트 삭제"""
        ekevent = self._find_event(event_id)
        title = str(ekevent.title())

        span = EKSpanFutureEvents if ekevent.hasRecurrenceRules() else EKSpanThisEvent
        success, error = self.store.removeEvent_span_error_(ekevent, span, None)
        if not success:
            raise CalendarError(f"이벤트 삭제 실패: {error}")

        return title

    # --- 헬퍼 ---

    def _find_event(self, event_id: str) -> EventKit.EKEvent:
        """ID로 이벤트 찾기"""
        ekevent = self.store.eventWithIdentifier_(event_id)
        if ekevent is None:
            raise NoSuchEventError(event_id)
        return ekevent

    @staticmethod
    def _to_nsdate(dt: datetime) -> NSDate:
        """datetime → NSDate 변환"""
        return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

    @staticmethod
    def _to_ek_recurrence(rule: RecurrenceRule) -> EventKit.EKRecurrenceRule:
        """RecurrenceRule → EKRecurrenceRule 변환"""
        freq_map = {
            "daily": EventKit.EKRecurrenceFrequencyDaily,
            "weekly": EventKit.EKRecurrenceFrequencyWeekly,
            "monthly": EventKit.EKRecurrenceFrequencyMonthly,
            "yearly": EventKit.EKRecurrenceFrequencyYearly,
        }

        end = None
        if rule.end_date:
            end = EventKit.EKRecurrenceEnd.recurrenceEndWithEndDate_(
                NSDate.dateWithTimeIntervalSince1970_(rule.end_date.timestamp())
            )

        return EventKit.EKRecurrenceRule.alloc().initRecurrenceWithFrequency_interval_end_(
            freq_map[rule.frequency],
            rule.interval,
            end,
        )
