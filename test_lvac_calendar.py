import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import lvac_calendar as lc

NOW = datetime.datetime(2026, 9, 25, 16, 0, tzinfo=datetime.timezone.utc)


def pacific_ts(*args):
    return int(datetime.datetime(*args, tzinfo=lc.TZ).timestamp())


def cls(cname, start, shift_id, minutes=60):
    return {'cname': cname, 'room': 'Room 1', 'instructor': 'Pat Q', 'start': start,
            'end': start + minutes * 60, 'shiftId': shift_id,
            'description': {'details': ['60 MINS', 'CARDIO']}}


class BuildFeedTest(unittest.TestCase):
    def test_keeps_only_selected_classes(self):
        schedules = {'nw': [cls('CYCLE', pacific_ts(2026, 9, 25, 6), 1),
                            cls('BODYPUMP™', pacific_ts(2026, 9, 25, 7), 2),
                            cls('BODYPUMP HEAVY™', pacific_ts(2026, 9, 25, 8), 3),
                            cls('YIN YOGA', pacific_ts(2026, 9, 25, 9), 4),
                            cls('CYCLE PWR BY LVAC', pacific_ts(2026, 9, 25, 10), 5),
                            cls('POWER YOGA', pacific_ts(2026, 9, 25, 11), 7)],
                     'sw': [cls('ZUMBA', pacific_ts(2026, 9, 25, 6), 6)]}
        feed = lc.build_feed(schedules, None, NOW)
        summaries = [l for l in feed.splitlines() if l.startswith('SUMMARY:')]
        self.assertEqual(summaries, ['SUMMARY:CYCLE – LVAC Northwest',
                                     'SUMMARY:BODYPUMP™ – LVAC Northwest',
                                     'SUMMARY:YIN YOGA – LVAC Northwest'])

    def test_times_are_pacific_wall_clock(self):
        feed = lc.build_feed({'nw': [cls('CYCLE', pacific_ts(2026, 11, 2, 6), 1)]}, None, NOW)
        # 6 AM stays 6 AM Pacific after the Nov 1 DST change
        self.assertIn('DTSTART;TZID=America/Los_Angeles:20261102T060000', feed)

    def test_carries_over_recent_past_classes_only(self):
        old = lc.build_feed({'nw': [cls('CYCLE', pacific_ts(2026, 9, 24, 6), 10),
                                    cls('CYCLE', pacific_ts(2026, 8, 1, 6), 11)]}, None, NOW)
        new = lc.build_feed({'nw': [cls('CYCLE', pacific_ts(2026, 9, 25, 6), 12)]}, old, NOW)
        uids = [l for l in new.splitlines() if l.startswith('UID:')]
        self.assertEqual(uids, ['UID:lvac-nw-10', 'UID:lvac-nw-12'])

    def test_unchanged_schedule_differs_only_by_dtstamp(self):
        schedules = {'nw': [cls('CYCLE', pacific_ts(2026, 9, 25, 6), 1)]}
        first = lc.build_feed(schedules, None, NOW)
        second = lc.build_feed(schedules, first, NOW + datetime.timedelta(hours=6))
        self.assertNotEqual(first, second)
        self.assertEqual(lc.without_dtstamps(first), lc.without_dtstamps(second))

    def test_main_leaves_file_alone_when_schedule_unchanged(self):
        schedule = [cls('CYCLE', pacific_ts(2026, 9, 25, 6), 1)]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(lc, 'fetch', return_value=schedule):
            path = Path(tmp, 'feed.ics')
            lc.main(path)
            first = path.read_bytes()
            lc.main(path)
            self.assertEqual(path.read_bytes(), first)

    def test_no_matching_classes_fails(self):
        with self.assertRaises(ValueError):
            lc.build_feed({'nw': [cls('ZUMBA', pacific_ts(2026, 9, 25, 6), 1)]}, None, NOW)


if __name__ == '__main__':
    unittest.main()
