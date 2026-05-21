"""Base page object for Selenium interactions."""

from urllib.parse import urljoin


class BasePage:
    def __init__(self, driver, base_url: str = ""):
        self.driver = driver
        self.base_url = base_url

    def open(self, path: str = ""):
        target = path
        if self.base_url:
            target = urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/"))
        self.driver.get(target)

    def find(self, by, value):
        return self.driver.find_element(by, value)

    def click(self, by, value):
        self.find(by, value).click()

    def type_text(self, by, value, text: str, clear: bool = True):
        element = self.find(by, value)
        if clear:
            element.clear()
        element.send_keys(text)
