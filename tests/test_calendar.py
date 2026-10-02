"""Offline calendar source contracts and independent Python date fixtures.

These tests do NOT execute Monkey C or emulate Garmin's timezone implementation.
Python datetime/calendar/zoneinfo generate independent fixtures for future device
checks. Source checks establish the selected Garmin API, conversion, guards and
refresh ordering. CIQ_SDK optionally checks the bundled official API docs.
"""
import calendar
from datetime import date, datetime, timedelta, timezone
import html
import os
from pathlib import Path
import re
import unittest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parents[1]
SDK_VALUE = (os.environ.get("CONNECTIQ_SDK") or os.environ.get("CIQ_SDK") or
             os.environ.get("CIQ_HOME"))
SDK = Path(SDK_VALUE).expanduser() if SDK_VALUE else None
ENGLISH_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def without_comments(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)


def expected_calendar(local_date):
    """Independent Python fixture, not a translation/execution of Monkey C."""
    # Python's ISO weekday is Monday=1..Sunday=7; the UI is Sunday=0.
    return (local_date.isoweekday() % 7,
            f"{ENGLISH_MONTHS[local_date.month - 1]} {local_date.day}")


class CalendarSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = without_comments((ROOT / "source/PrismelierData.mc").read_text())
        cls.labels = cls.code.split("private function updateClockLabels", 1)[1].split(
            "private function readActivity", 1)[0]
        cls.refresh = cls.code.split("function refresh(force", 1)[1].split(
            "private function updateClockLabels", 1)[0]

    def test_public_nullable_weekday_and_missing_date_defaults(self):
        self.assertRegex(self.code,
                         r"(?m)^    var weekdayIndex as Lang\.Number or Null = null;")
        self.assertRegex(self.code, r'(?m)^    var dateLabel as Lang\.String = "--";')

    def test_local_numeric_gregorian_info_is_the_only_calendar_source(self):
        self.assertIn("Gregorian.info(now, Time.FORMAT_SHORT)", self.labels)
        self.assertIn("var weekday = info.day_of_week;", self.labels)
        self.assertIn("var month = info.month;", self.labels)
        for forbidden in ("Gregorian.utcInfo", "Gregorian.localMoment", "Time.today",
                          "timeZoneOffset", "_location", "Weather.", "86400"):
            self.assertNotIn(forbidden, self.labels)
        self.assertEqual(self.labels.count("Gregorian.info("), 1)

    def test_every_refresh_recomputes_labels_before_expensive_minute_cache(self):
        now = self.refresh.index("var now = Time.now();")
        labels = self.refresh.index("updateClockLabels(now);")
        cache = self.refresh.index("if (force || minute != _lastRefreshMinute)")
        self.assertLess(now, labels)
        self.assertLess(labels, cache)
        self.assertNotRegex(self.refresh[:labels], r"\bif\s*\(")
        self.assertNotIn("return", self.refresh[:labels])
        self.assertEqual(self.refresh.count("updateClockLabels(now);"), 1)
        cached_reads = self.refresh[cache:].split("updateWeatherDisplay", 1)[0]
        for operation in ("readActivity();", "readHeartRate(seconds);",
                          "readWeather(seconds);",
                          "buildSolarEvents(now, seconds);"):
            self.assertEqual(self.refresh.count(operation), 1)
            self.assertIn(operation, cached_reads)

    def test_weekday_conversion_is_sunday_zero_and_guards_invalid_values(self):
        self.assertRegex(self.labels,
                         r"if\s*\(weekday instanceof Lang\.Number && weekday >= 1 && "
                         r"weekday <= 7\)\s*\{\s*weekdayIndex = weekday - 1;\s*\}")
        self.assertLess(self.labels.index("weekdayIndex = null;"),
                        self.labels.index("if (weekday instanceof"))
        self.assertEqual(self.labels.count("weekdayIndex ="), 2)
        self.assertNotIn("weekday %", self.labels)

    def test_english_months_and_unpadded_day_have_guarded_array_access(self):
        months = re.search(r"var months = \[(.*?)\];", self.labels, re.S)
        self.assertIsNotNone(months)
        self.assertEqual(tuple(re.findall(r'"([A-Za-z]+)"', months.group(1))),
                         ENGLISH_MONTHS)
        self.assertRegex(self.labels,
                         r"if\s*\(month instanceof Lang\.Number && month >= 1 && "
                         r"month <= 12 &&\s*info.day >= 1 && info.day <= 31\)\s*\{\s*"
                         r'_localDateKey = info.year \* 10000 \+ month \* 100 \+ info.day;\s*'
                         r'dateLabel = months\[month - 1\] \+ " " \+ '
                         r'info.day.format\("%d"\);\s*\}')
        self.assertLess(self.labels.index('dateLabel = "--";'),
                        self.labels.index("if (month instanceof"))
        self.assertEqual(self.labels.count("months["), 1)
        self.assertEqual(self.labels.count("dateLabel ="), 2)
        self.assertNotIn('format("%02d")', self.labels)
        self.assertNotIn("days[", self.labels)

    def test_am_pm_is_drawn_by_view_and_solar_suffix_matches(self):
        data = (ROOT / "source/PrismelierData.mc").read_text()
        view = (ROOT / "source/PrismelierView.mc").read_text()
        self.assertNotIn("timeSuffix", data)
        self.assertIn('clock.hour < 12 ? "AM" : "PM"', view)
        self.assertIn('solarTime += info.hour < 12 ? " AM" : " PM";', data)


class IndependentDateFixtureTests(unittest.TestCase):
    def test_known_dates_include_request_weekday_wrap_and_leap_day(self):
        fixtures = (
            ("2026-10-24", 6, "Oct 24"),
            ("2026-10-25", 0, "Oct 25"),
            ("2026-10-26", 1, "Oct 26"),
            ("2026-12-31", 4, "Dec 31"),
            ("2027-01-01", 5, "Jan 1"),
            ("2024-02-28", 3, "Feb 28"),
            ("2024-02-29", 4, "Feb 29"),
            ("2024-03-01", 5, "Mar 1"),
            ("2100-02-28", 0, "Feb 28"),
            ("2100-03-01", 1, "Mar 1"),
        )
        for iso_date, weekday, label in fixtures:
            with self.subTest(date=iso_date):
                self.assertEqual(expected_calendar(date.fromisoformat(iso_date)),
                                 (weekday, label))

    def test_two_weeks_include_each_letter_and_saturday_sunday_wrap(self):
        start = date(2026, 10, 18)  # Independently known Sunday.
        indices = [expected_calendar(start + timedelta(days=i))[0] for i in range(14)]
        self.assertEqual(indices, list(range(7)) * 2)
        self.assertEqual("".join("SMTWTFS"[i] for i in indices), "SMTWTFSSMTWTFS")

    def test_every_month_end_and_year_boundary(self):
        for year in (2023, 2024, 2026, 2100):
            for month in range(1, 13):
                end = date(year, month, calendar.monthrange(year, month)[1])
                next_day = end + timedelta(days=1)
                last_index, last_label = expected_calendar(end)
                next_index, next_label = expected_calendar(next_day)
                with self.subTest(year=year, month=month):
                    self.assertEqual(next_day.day, 1)
                    self.assertEqual(next_day.month, month % 12 + 1)
                    self.assertEqual(next_index, (last_index + 1) % 7)
                    self.assertEqual(last_label, f"{ENGLISH_MONTHS[month - 1]} {end.day}")
                    self.assertEqual(next_label, f"{ENGLISH_MONTHS[month % 12]} 1")

    def test_all_leap_year_date_lengths_and_glyph_inventory(self):
        start = date(2024, 1, 1)
        labels = [expected_calendar(start + timedelta(days=i))[1] for i in range(366)]
        self.assertEqual(len(set(labels)), 366)
        self.assertEqual({len(label) for label in labels}, {5, 6})
        self.assertIn("Feb 29", labels)
        self.assertIn("Sep 30", labels)
        self.assertIn("Dec 31", labels)
        for label in labels:
            self.assertRegex(label, r"^[A-Z][a-z]{2} [1-9][0-9]?$")
        expected_characters = set(" ".join(ENGLISH_MONTHS) + "0123456789")
        self.assertEqual(set("".join(labels)), expected_characters)


class IndependentTimezoneFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.zones = {name: ZoneInfo(name) for name in (
                "America/New_York", "Asia/Tokyo", "Pacific/Kiritimati",
                "Pacific/Honolulu", "Asia/Kathmandu")}
        except ZoneInfoNotFoundError as exc:
            raise unittest.SkipTest(f"Optional IANA timezone database unavailable: {exc}")

    def local(self, utc_iso, zone):
        return datetime.fromisoformat(utc_iso).astimezone(self.zones[zone])

    def test_dst_spring_forward_and_repeated_hour_do_not_change_calendar(self):
        fixtures = (
            ("2026-03-08T06:59:59+00:00", (1, 59), (0, "Mar 8")),
            ("2026-03-08T07:00:00+00:00", (3, 0), (0, "Mar 8")),
            ("2026-11-01T05:59:59+00:00", (1, 59), (0, "Nov 1")),
            ("2026-11-01T06:00:00+00:00", (1, 0), (0, "Nov 1")),
        )
        for instant, clock, calendar_value in fixtures:
            with self.subTest(instant=instant):
                local = self.local(instant, "America/New_York")
                self.assertEqual((local.hour, local.minute), clock)
                self.assertEqual(expected_calendar(local.date()), calendar_value)

    def test_dst_local_day_lengths_are_23_and_25_hours(self):
        ny = self.zones["America/New_York"]
        for year, month, day, duration, label in (
                (2026, 3, 8, 23, "Mar 9"), (2026, 11, 1, 25, "Nov 2")):
            with self.subTest(month=month):
                midnight = datetime(year, month, day, tzinfo=ny)
                next_midnight = midnight + timedelta(days=1)
                elapsed = (next_midnight.astimezone(timezone.utc) -
                           midnight.astimezone(timezone.utc)).total_seconds()
                self.assertEqual(elapsed, duration * 3600)
                self.assertEqual(expected_calendar(midnight.date())[0], 0)
                self.assertEqual(expected_calendar(next_midnight.date()), (1, label))

    def test_local_midnight_occurs_inside_one_utc_date(self):
        before = self.local("2026-10-25T03:59:59+00:00", "America/New_York")
        after = self.local("2026-10-25T04:00:00+00:00", "America/New_York")
        self.assertEqual(expected_calendar(before.date()), (6, "Oct 24"))
        self.assertEqual(expected_calendar(after.date()), (0, "Oct 25"))
        self.assertEqual((after - before).total_seconds(), 1)

    def test_same_instant_travel_can_change_date_without_cache_minute_change(self):
        instant = "2026-10-25T00:30:00+00:00"
        new_york = self.local(instant, "America/New_York")
        tokyo = self.local(instant, "Asia/Tokyo")
        self.assertEqual(new_york.timestamp() // 60, tokyo.timestamp() // 60)
        self.assertEqual(expected_calendar(new_york.date()), (6, "Oct 24"))
        self.assertEqual(expected_calendar(tokyo.date()), (0, "Oct 25"))

    def test_date_line_and_fractional_offset_fixtures(self):
        fixtures = (
            ("2026-12-31T10:30:00+00:00", "Pacific/Kiritimati", (5, "Jan 1")),
            ("2026-12-31T10:30:00+00:00", "Pacific/Honolulu", (4, "Dec 31")),
            ("2026-10-24T18:14:59+00:00", "Asia/Kathmandu", (6, "Oct 24")),
            ("2026-10-24T18:15:00+00:00", "Asia/Kathmandu", (0, "Oct 25")),
        )
        for instant, zone, expected in fixtures:
            with self.subTest(instant=instant, zone=zone):
                self.assertEqual(expected_calendar(self.local(instant, zone).date()), expected)


@unittest.skipUnless(SDK is not None, "Set CIQ_SDK for optional official calendar documentation checks")
class OfficialCalendarDocumentationTests(unittest.TestCase):
    def test_numeric_ranges_and_local_info_match_official_documentation(self):
        def plain(path):
            return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", path.read_text())))

        info = plain(SDK / "doc/Toybox/Time/Gregorian/Info.html")
        self.assertIn("A number in the range 1 to 7. 1 = Sunday, 2 = Monday, ..., 7 = Saturday", info)
        self.assertIn("A number in the range 1 to 12. 1 = January, 2= February, ..., 12 = December", info)
        module = plain(SDK / "doc/Toybox/Time/Gregorian.html")
        self.assertRegex(module, r"\binfo \(moment.*?Get Info for a Moment in local time\.")
        self.assertRegex(module, r"DAY_SUNDAY\s+1\s+API Level")
        self.assertRegex(module, r"DAY_SATURDAY\s+7\s+API Level")


if __name__ == "__main__":
    unittest.main(verbosity=2)
