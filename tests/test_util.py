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


if __name__ == "__main__":
    unittest.main()
