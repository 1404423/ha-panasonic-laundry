import unittest

from _loader import load

decode = load("decode")


def status(**kw):
    base = {"0080": "30", "0088": "42", "00B0": "42", "00E2": "61", "0121": "00", "00D0": "61",
            "00ED": "FFFF", "00DB": "FFFF", "00DC": "FFFF"}
    base.update(kw)
    return base


class DecodeTests(unittest.TestCase):
    def test_hhmm(self):
        self.assertEqual(decode.hhmm_to_minutes("0235"), 2 * 60 + 0x35)
        self.assertEqual(decode.hhmm_to_minutes("0000"), 0)
        for none in ("FFFF", "ffff", "", None, "123"):
            self.assertIsNone(decode.hhmm_to_minutes(none))

    def test_state(self):
        self.assertEqual(decode.decode_state(status()), "waiting")               # power on, before operation
        self.assertEqual(decode.decode_state(status(**{"0080": "31"})), "off")
        self.assertEqual(decode.decode_state(status(**{"0088": "41"})), "error")
        self.assertEqual(decode.decode_state(status(**{"00E2": "41"})), "running")  # washing
        self.assertEqual(decode.decode_state(status(**{"00E2": "52"})), "running")  # drying
        self.assertEqual(decode.decode_state(status(**{"00E2": "44"})), "paused")
        self.assertEqual(decode.decode_state(status(**{"00E2": "51"})), "done")
        self.assertEqual(decode.decode_state(status(**{"00E2": "ZZ"})), "waiting")  # unknown code: do not crash

    def test_state_off_wins_over_error(self):
        self.assertEqual(decode.decode_state(status(**{"0080": "31", "0088": "41"})), "off")

    def test_remaining_prefers_combined_value(self):
        self.assertIsNone(decode.decode_remaining(status()))
        self.assertEqual(decode.decode_remaining(status(**{"00ED": "0230", "00DB": "0010"})), 2 * 60 + 0x30)
        self.assertEqual(decode.decode_remaining(status(**{"00DB": "0010"})), 0x10)
        self.assertEqual(decode.decode_remaining(status(**{"00DC": "0105"})), 60 + 5)

    def test_texts(self):
        self.assertEqual(decode.decode_progress_text(status(**{"0121": "01"})), "洗い中")
        self.assertIsNone(decode.decode_progress_text(status(**{"0121": "99"})))
        self.assertIsNotNone(decode.decode_course_text(status()))
        self.assertIsNone(decode.decode_course_text({}))

    def test_door(self):
        self.assertEqual(decode.decode_door(status(**{"00B0": "41"})), "open")
        self.assertEqual(decode.decode_door(status(**{"00B0": "42"})), "closed")
        self.assertIsNone(decode.decode_door({}))


if __name__ == "__main__":
    unittest.main()
