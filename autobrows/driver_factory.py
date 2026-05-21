"""Browser driver construction utilities."""

from .config import FrameworkConfig


def create_driver(config: FrameworkConfig, webdriver_module=None):
    if webdriver_module is None:
        from selenium import webdriver as webdriver_module  # pragma: no cover

    browser = config.browser.strip().lower()

    if browser == "chrome":
        options = webdriver_module.ChromeOptions()
        if config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        driver = webdriver_module.Chrome(options=options)
    elif browser == "firefox":
        options = webdriver_module.FirefoxOptions()
        if config.headless:
            options.add_argument("-headless")
        driver = webdriver_module.Firefox(options=options)
    else:
        raise ValueError(f"Unsupported browser: {config.browser}")

    driver.implicitly_wait(config.implicit_wait)
    driver.set_page_load_timeout(config.page_load_timeout)
    return driver
