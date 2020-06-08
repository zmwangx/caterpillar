import enum
import pathlib

from typing import Callable, Sequence


class EventType(enum.Enum):
    SEGMENTS_DOWNLOAD_INITIATED = 0x11
    SEGMENTS_DOWNLOAD_FINISHED = 0x12
    SEGMENT_DOWNLOAD_SUCCEEDED = 0x21
    SEGMENT_DOWNLOAD_FAILED = 0x22
    MERGE_FINISHED = 0x42


class Event:
    def __init__(self, event_type: EventType):
        self.event_type = event_type

    def _serialize(self, *, repr_form: bool = True):
        classname = self.__class__.__name__
        attr_list = [
            f"{attr}={val!r}" if repr_form else f"{attr}={val}"
            for attr, val in self.__dict__.items()
            if attr != "event_type" and not attr.startswith("_")
        ]
        return f"{classname}({', '.join(attr_list)})"

    def __str__(self):
        return self._serialize(repr_form=False)

    def __repr__(self):
        return self._serialize(repr_form=True)


class SegmentsDownloadInitiatedEvent(Event):
    def __init__(self, *, segment_count: int):
        super().__init__(EventType.SEGMENTS_DOWNLOAD_INITIATED)
        self.segment_count = segment_count


class SegmentsDownloadFinishedEvent(Event):
    def __init__(self, *, success_count: int, failure_count: int):
        super().__init__(EventType.SEGMENTS_DOWNLOAD_FINISHED)
        self.success_count = success_count
        self.failure_count = failure_count


class SegmentDownloadSucceededEvent(Event):
    def __init__(self, *, path: pathlib.Path):
        super().__init__(EventType.SEGMENT_DOWNLOAD_SUCCEEDED)
        self.path = path


class SegmentDownloadFailedEvent(Event):
    def __init__(self, *, segment_url: str):
        super().__init__(EventType.SEGMENT_DOWNLOAD_FAILED)
        self.segment_url = segment_url


class MergeFinishedEvent(Event):
    def __init__(self, *, path: pathlib.Path):
        super().__init__(EventType.MERGE_FINISHED)
        self.path = path


EventHook = Callable[[Event], None]


def emit_event(event: Event, event_hooks: Sequence[EventHook]):
    for hook in event_hooks:
        hook(event)
