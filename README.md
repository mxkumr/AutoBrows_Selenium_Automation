# AutoBrows Selenium Automation

A lightweight Selenium-based automation framework scaffold using Python.

## What is included
- Environment-driven framework configuration
- Browser driver factory (Chrome/Firefox)
- Reusable base page object for Page Object Model style tests
- Focused unit tests for configuration and driver creation logic

## Setup
1. Create a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration
Use environment variables:
- `AUTOBROWS_BASE_URL`
- `AUTOBROWS_BROWSER` (`chrome` or `firefox`)
- `AUTOBROWS_HEADLESS` (`true`/`false`)
- `AUTOBROWS_IMPLICIT_WAIT` (seconds)
- `AUTOBROWS_PAGE_LOAD_TIMEOUT` (seconds)

## Running tests
```bash
python -m unittest discover -s tests -q
```
