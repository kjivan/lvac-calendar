"""Build an iCalendar feed of selected LVAC classes.

Downloads the class schedules that power https://www.lvac.com/locations/search-class-schedules,
keeps only the classes in CLASS_NAMES (plus any yoga class), and writes an .ics file with
times pinned to Pacific time. Classes that already happened are carried over from the
previous feed for KEEP_PAST_DAYS so they don't vanish from the calendar.

Usage: python lvac_calendar.py docs/lvac-classes.ics
"""

import datetime
import http.client
import json
import re
import sys
import time
import urllib.request
import zoneinfo
from pathlib import Path

DATA_URL = 'https://www.lvac.com/wp-content/plugins/lvac-short-codes/uploads/{}.classes.json'
LOCATIONS = {'nw': 'Northwest', 'sw': 'Southwest'}
CLASS_NAMES = {'CYCLE', 'CYCLE XPRESS', 'BODYPUMP', 'BODYPUMP XPRESS', 'BODYBALANCE'}
KEEP_PAST_DAYS = 30
TZID = 'America/Los_Angeles'
TZ = zoneinfo.ZoneInfo(TZID)

VTIMEZONE = [
    'BEGIN:VTIMEZONE', f'TZID:{TZID}',
    'BEGIN:DAYLIGHT', 'TZOFFSETFROM:-0800', 'TZOFFSETTO:-0700', 'TZNAME:PDT',
    'DTSTART:19700308T020000', 'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU', 'END:DAYLIGHT',
    'BEGIN:STANDARD', 'TZOFFSETFROM:-0700', 'TZOFFSETTO:-0800', 'TZNAME:PST',
    'DTSTART:19701101T020000', 'RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU', 'END:STANDARD',
    'END:VTIMEZONE',
]


def wanted(cname):
    name = cname.upper().replace('™', '').strip()
    return name in CLASS_NAMES or 'YOGA' in name


def fetch(location, attempts=4):
    req = urllib.request.Request(DATA_URL.format(location), headers={'User-Agent': 'lvac-calendar'})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                classes = json.load(resp)
            break
        except (OSError, http.client.HTTPException, json.JSONDecodeError) as e:
            # LVAC's server occasionally cuts responses short; retry before giving up
            if attempt == attempts:
                raise
            print(f'Fetching {location} failed ({e!r}); retrying')
            time.sleep(5 * attempt)
    if not isinstance(classes, list) or not classes:
        raise ValueError(f'No classes returned for {location}')
    return classes


def local(ts):
    # Wall-clock Pacific time; paired with TZID so times stay right across DST changes
    return datetime.datetime.fromtimestamp(ts, TZ).strftime('%Y%m%dT%H%M%S')


def esc(s):
    return s.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


def fold(line):
    b = line.encode()
    out = []
    while len(b) > 75:
        i = 75
        while (b[i] & 0xC0) == 0x80:
            i -= 1
        out.append(b[:i].decode())
        b = b' ' + b[i:]
    out.append(b.decode())
    return '\r\n'.join(out)


def class_event(location, c):
    uid = f"lvac-{location}-{c['shiftId']}" if c.get('shiftId') else \
        f"lvac-{location}-{c['start']}-{re.sub(r'[^a-z0-9]+', '-', c['cname'].lower()).strip('-')}"
    desc = f"Instructor: {c['instructor']}\nRoom: {c['room']}"
    details = (c.get('description') or {}).get('details')
    if details:
        desc += '\n' + ' · '.join(details)
    return [
        'BEGIN:VEVENT', f'UID:{uid}', 'DTSTAMP:{dtstamp}',
        f"DTSTART;TZID={TZID}:{local(c['start'])}", f"DTEND;TZID={TZID}:{local(c['end'])}",
        'SUMMARY:' + esc(f"{c['cname'].strip()} – LVAC {LOCATIONS[location]}"),
        'LOCATION:' + esc(f"LVAC {LOCATIONS[location]}, {c['room']}"),
        'DESCRIPTION:' + esc(desc), 'END:VEVENT',
    ]


def parse_events(ics_text):
    """Return the VEVENT blocks of an .ics file as lists of unfolded lines."""
    lines = re.sub(r'\r?\n[ \t]', '', ics_text).splitlines()
    events, current = [], None
    for line in lines:
        if line == 'BEGIN:VEVENT':
            current = [line]
        elif current is not None:
            current.append(line)
            if line == 'END:VEVENT':
                events.append(current)
                current = None
    return events


def event_start(event):
    value = next(l for l in event if l.startswith('DTSTART')).split(':', 1)[1]
    return datetime.datetime.strptime(value, '%Y%m%dT%H%M%S')


def build_feed(schedules, previous_ics, now):
    """schedules: {location: [class, ...]} as returned by fetch()."""
    events = [(c['start'], class_event(loc, c))
              for loc, classes in schedules.items() for c in classes if wanted(c['cname'])]
    if not events:
        raise ValueError('No matching classes found; the LVAC data format may have changed')

    # Carry over classes from earlier days that LVAC no longer lists
    first_day = min(datetime.datetime.fromtimestamp(c['start'], TZ).date()
                    for classes in schedules.values() for c in classes)
    oldest = first_day - datetime.timedelta(days=KEEP_PAST_DAYS)
    uids = {e[1] for _, e in events}
    for old in parse_events(previous_ics or ''):
        start = event_start(old)
        if oldest <= start.date() < first_day and old[1] not in uids:
            old = [l if not l.startswith('DTSTAMP:') else 'DTSTAMP:{dtstamp}' for l in old]
            events.append((start.replace(tzinfo=TZ).timestamp(), old))
    events.sort(key=lambda e: (e[0], e[1][1]))

    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//lvac-calendar//EN', 'CALSCALE:GREGORIAN',
             'X-WR-CALNAME:LVAC Classes', f'X-WR-TIMEZONE:{TZID}',
             'REFRESH-INTERVAL;VALUE=DURATION:PT6H', 'X-PUBLISHED-TTL:PT6H', *VTIMEZONE]
    for _, event in events:
        lines += event
    lines.append('END:VCALENDAR')
    dtstamp = now.astimezone(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return '\r\n'.join(fold(l.replace('{dtstamp}', dtstamp)) for l in lines) + '\r\n'


def without_dtstamps(ics_text):
    return re.sub(r'^DTSTAMP:.*\r?\n', '', ics_text, flags=re.M)


def main(out_path):
    out = Path(out_path)
    previous = None
    if out.exists():
        with open(out, encoding='utf-8', newline='') as f:  # keep CRLFs so the comparison below works
            previous = f.read()
    schedules = {loc: fetch(loc) for loc in LOCATIONS}
    feed = build_feed(schedules, previous, datetime.datetime.now(datetime.timezone.utc))
    if previous is not None and without_dtstamps(previous) == without_dtstamps(feed):
        print('No schedule changes')
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(feed, encoding='utf-8', newline='')
    print(f"Wrote {feed.count('BEGIN:VEVENT')} classes to {out}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'docs/lvac-classes.ics')
