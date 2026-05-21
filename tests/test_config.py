import os
import unittest
from unittest.mock import patch

from autobrows.config import FrameworkConfig


class FrameworkConfigTests(unittest.TestCase):
    def test_from_env_uses_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = FrameworkConfig.from_env()

        self.assertEqual(config.base_url, "")
        self.assertEqual(config.browser, "chrome")
        self.assertFalse(config.headless)
        self.assertEqual(config.implicit_wait, 5)
        self.assertEqual(config.page_load_timeout, 30)

    def test_from_env_reads_values(self):
        with patch.dict(
            os.environ,
            {
                "AUTOBROWS_BASE_URL": "https://example.com",
                "AUTOBROWS_BROWSER": "firefox",
                "AUTOBROWS_HEADLESS": "true",
                "AUTOBROWS_IMPLICIT_WAIT": "10",
                "AUTOBROWS_PAGE_LOAD_TIMEOUT": "45",
            },
            clear=True,
        ):
            config = FrameworkConfig.from_env()

        self.assertEqual(config.base_url, "https://example.com")
        self.assertEqual(config.browser, "firefox")
        self.assertTrue(config.headless)
        self.assertEqual(config.implicit_wait, 10)
        self.assertEqual(config.page_load_timeout, 45)


if __name__ == "__main__":
    unittest.main()
