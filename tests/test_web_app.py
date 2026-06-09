from __future__ import annotations

import unittest

from auto_order_splitting.web_app import parse_skip_keywords


class WebAppTests(unittest.TestCase):
    def test_empty_skip_keywords_stay_empty(self):
        self.assertEqual(parse_skip_keywords(""), [])
        self.assertEqual(parse_skip_keywords(None), [])

    def test_skip_keywords_parse_multiple_values(self):
        self.assertEqual(parse_skip_keywords("营养餐，早晚餐, 食材配送"), ["营养餐", "早晚餐", "食材配送"])


if __name__ == "__main__":
    unittest.main()
