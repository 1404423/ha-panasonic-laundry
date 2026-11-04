import unittest

from _loader import load

util = load("util")
CODE = "AbCdEf0123456789-_AbCdEf0123456789-_AbCd0"


class ExtractTests(unittest.TestCase):
    def test_bare_code(self):
        self.assertEqual(util.extract_code(f"  {CODE}\n"), CODE)

    def test_redirect_url(self):
        url = f"auth0://auth.digital.panasonic.com/android/com.panasonic.SmartLaundry/callback?code={CODE}&state=abc123"
        self.assertEqual(util.extract_code(url), CODE)
        self.assertEqual(util.extract_state(url), "abc123")

    def test_whole_console_line(self):
        line = (f"consent?state=hKFo2SBFAKE:1 Failed to launch 'auth0://auth.digital.panasonic.com/android/"
                f"com.panasonic.SmartLaundry/callback?code={CODE}&state=0123abcd' because the scheme does not have a registered handler.")
        self.assertEqual(util.extract_code(line), CODE)
        self.assertEqual(util.extract_state(line), "0123abcd")

    def test_code_last_in_url(self):
        self.assertEqual(util.extract_code(f"auth0://x/callback?state=s1&code={CODE}"), CODE)

    def test_no_state(self):
        self.assertIsNone(util.extract_state(CODE))



class BackoffTests(unittest.TestCase):
    def test_no_failures_no_wait(self):
        self.assertEqual(util.refresh_backoff_seconds(0), 0)

    def test_doubles_then_caps(self):
        self.assertEqual([util.refresh_backoff_seconds(n) for n in (1, 2, 3, 4)], [60, 120, 240, 480])
        self.assertEqual(util.refresh_backoff_seconds(5), 900)
        self.assertEqual(util.refresh_backoff_seconds(50), 900)


if __name__ == "__main__":
    unittest.main()
