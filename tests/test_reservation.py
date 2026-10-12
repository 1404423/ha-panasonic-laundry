import unittest
from datetime import datetime, time, timedelta, timezone

from _loader import load

decode = load("decode")
res = load("reservation")
JST = timezone(timedelta(hours=9))

# values seen on the real washer (NA-LX127CL-W, 2026-10-12)
HIST = "BF00000083000000A10000002D0000007F000000840000004400000021000000610000006A000000"


def st(**kw):
    base = {"0080": "30", "0088": "42", "00B0": "42", "00E2": "61", "0100": "01", "0090": "42",
            "0092": "0000", "00F2": "0000", "00D0": "21", "0132": "00", "0133": "00", "012B": HIST}
    base.update(kw)
    return base


class HistoryTests(unittest.TestCase):
    def test_history_newest_first(self):
        codes = decode.decode_history(st())
        self.assertEqual(codes[:3], ["BF", "83", "A1"])
        self.assertEqual(len(codes), 10)

    def test_history_skips_empty_and_unknown(self):
        self.assertEqual(decode.decode_history(st(**{"012B": "BF00000000000000ZZ000000"})), ["BF"])
        self.assertEqual(decode.decode_history({}), [])

    def test_reservation_values(self):
        self.assertEqual(decode.decode_reservation(st()), "off")
        on = st(**{"0090": "41", "0092": "0A00", "00F2": "0334"})
        self.assertEqual(decode.decode_reservation(on), "reserved")
        self.assertEqual(decode.decode_reserve_finish_minutes(on), 600)
        self.assertEqual(decode.decode_reserve_start_minutes(on), 3 * 60 + 52)
        self.assertIsNone(decode.decode_reserve_finish_minutes(st()))


class ReservationTests(unittest.TestCase):
    def test_hex(self):
        self.assertEqual(res.hex_hhmm(600), "0A00")
        self.assertEqual(res.hex_hhmm(150), "021E")

    def test_next_occurrence(self):
        now = datetime(2026, 10, 12, 21, 30, 15, tzinfo=JST)
        self.assertEqual(res.next_occurrence(time(7, 0), now), datetime(2026, 10, 13, 7, 0, tzinfo=JST))
        self.assertEqual(res.next_occurrence(time(23, 0), now), datetime(2026, 10, 12, 23, 0, tzinfo=JST))
        self.assertEqual(res.next_occurrence(time(21, 30), now), datetime(2026, 10, 13, 21, 30, tzinfo=JST))

    def test_minutes_until_rounds_up_to_10(self):
        now = datetime(2026, 10, 12, 21, 30, 15, tzinfo=JST)
        self.assertEqual(res.minutes_until(datetime(2026, 10, 13, 7, 30, tzinfo=JST), now), 600)
        self.assertEqual(res.minutes_until(datetime(2026, 10, 13, 7, 0, tzinfo=JST), now), 570)

    def test_blockers(self):
        self.assertEqual(res.blockers(st()), [])
        self.assertIn("remote_not_permitted", res.blockers(st(**{"0100": "02"})))
        self.assertIn("door_open", res.blockers(st(**{"00B0": "41"})))
        self.assertIn("not_waiting", res.blockers(st(**{"00E2": "41"})))
        self.assertIn("fault", res.blockers(st(**{"0088": "41"})))
        self.assertIn("power_off", res.blockers(st(**{"0080": "31"})))
        self.assertEqual(len(res.blockers(st(**{"0100": "02", "00B0": "41"}))), 2)

    def test_reserve_cmds_match_the_verified_request(self):
        # the request that worked on the real washer: 0092=0A00, 0090=41, 00D0=21 (course 21 is a washing course)
        cmds = res.build_reserve_cmds(st(), "21", 600)
        self.assertEqual(cmds[:3], [("0092", "0A00"), ("0090", "41"), ("00D0", "21")])
        self.assertEqual(cmds[3:], [("0132", "00"), ("0133", "00")])

    def test_reserve_cmds_drying_course_has_no_detergent_modes(self):
        self.assertEqual(res.build_reserve_cmds(st(), "BF", 600), [("0092", "0A00"), ("0090", "41"), ("00D0", "BF")])

    def test_reserve_range(self):
        for bad in (0, 5, 24 * 60 + 10):
            with self.assertRaises(ValueError):
                res.build_reserve_cmds(st(), "BF", bad)
        res.build_reserve_cmds(st(), "BF", 24 * 60)

    def test_start_cmds(self):
        self.assertEqual(res.build_start_cmds(), [("00B2", "41")])  # 41 = start (42 pause, 43 stop)

    def test_start_blockers(self):
        self.assertEqual(res.start_blockers(st()), [])
        self.assertIn("already_reserved", res.start_blockers(st(**{"0090": "41"})))
        self.assertIn("remote_not_permitted", res.start_blockers(st(**{"0100": "02"})))
        self.assertIn("door_open", res.start_blockers(st(**{"00B0": "41"})))
        self.assertIn("not_waiting", res.start_blockers(st(**{"00E2": "52"})))  # already running: do not start again

    def test_cancel(self):
        self.assertEqual(res.build_cancel_cmds(), [("0090", "42")])


if __name__ == "__main__":
    unittest.main()
