import unittest

from autobrows.config import FrameworkConfig
from autobrows.driver_factory import create_driver


class FakeOptions:
    def __init__(self):
        self.args = []

    def add_argument(self, arg):
        self.args.append(arg)


class FakeDriver:
    def __init__(self, options):
        self.options = options
        self.wait = None
        self.timeout = None

    def implicitly_wait(self, wait):
        self.wait = wait

    def set_page_load_timeout(self, timeout):
        self.timeout = timeout


class FakeWebDriver:
    ChromeOptions = FakeOptions
    FirefoxOptions = FakeOptions

    @staticmethod
    def Chrome(options):
        return FakeDriver(options)

    @staticmethod
    def Firefox(options):
        return FakeDriver(options)


class DriverFactoryTests(unittest.TestCase):
    def test_create_chrome_driver_with_headless(self):
        cfg = FrameworkConfig(browser="chrome", headless=True, implicit_wait=2, page_load_timeout=9)

        driver = create_driver(cfg, webdriver_module=FakeWebDriver)

        self.assertEqual(driver.wait, 2)
        self.assertEqual(driver.timeout, 9)
        self.assertIn("--headless=new", driver.options.args)

    def test_create_firefox_driver_without_headless(self):
        cfg = FrameworkConfig(browser="firefox", headless=False)

        driver = create_driver(cfg, webdriver_module=FakeWebDriver)

        self.assertNotIn("-headless", driver.options.args)

    def test_unsupported_browser_raises(self):
        cfg = FrameworkConfig(browser="edge")

        with self.assertRaises(ValueError):
            create_driver(cfg, webdriver_module=FakeWebDriver)


if __name__ == "__main__":
    unittest.main()
