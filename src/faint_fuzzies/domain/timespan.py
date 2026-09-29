"""Parses the hand-written date and time of a session."""
from datetime import datetime

DATE_TIME_FORMAT = "%d.%m.%Y%H:%M"


def parse_date_time(date: str, time: str) -> tuple[datetime, datetime]:
    """Parses "DD.MM.YYYY" and "HH:MM", each of which may be a range "from-to".

    A date range is paired with a time range, so "29.09.2011-30.09.2011" with "21:30-00:30"
    runs from the 29th at 21:30 to the 30th at 00:30. Times are local clock time.

    :param date: "DD.MM.YYYY", or "DD.MM.YYYY-DD.MM.YYYY" for a range
    :param time: "HH:MM", or "HH:MM-HH:MM" for a range
    :returns: the start and end as datetimes
    :raises ValueError: when a date or time (range) cannot be parsed, or the start is after the end
    """
    dates, times = date.split("-"), time.split("-")
    if len(dates) > 2:
        raise ValueError(f"invalid date '{date}'")
    if len(times) > 2:
        raise ValueError(f"invalid time '{time}'")
    try:
        # naive on purpose: there is no timezone anywhere in the source data, so there is no correct offset
        # to attach - astimezone() would only stamp the running machine's own zone, not the observer's
        start = datetime.strptime(dates[0] + times[0], DATE_TIME_FORMAT)  # noqa: DTZ007
        end = datetime.strptime(dates[-1] + times[-1], DATE_TIME_FORMAT)  # noqa: DTZ007
    except ValueError as exc:
        raise ValueError(f"invalid date or time '{date}' '{time}'") from exc
    if start > end:
        raise ValueError(f"start is after end in '{date}' '{time}'")
    return start, end
