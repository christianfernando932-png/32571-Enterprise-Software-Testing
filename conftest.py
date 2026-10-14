"""
pytest fixtures shared by all tests.

pytest-playwright already provides the `page` fixture (a fresh browser tab with a
fresh session for EVERY test), so each scenario starts with an empty comparison
list and no leftover filters.
"""
from pathlib import Path

import pytest

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"


@pytest.fixture(autouse=True)
def screenshot_after_each_test(page, request):
    """After every scenario, save a full-page screenshot as evidence for the
    'Test Results' row of the report (pass or fail)."""
    yield
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    name = request.node.name.replace("[", "_").replace("]", "").replace(" ", "_")
    page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"), full_page=True)


@pytest.fixture
def browser_context_args(browser_context_args):
    """Desktop-sized window so the left-hand filter panel is shown (on narrow
    screens Mazaar hides it behind a 'Filter' button)."""
    return {**browser_context_args, "viewport": {"width": 1440, "height": 900}}
