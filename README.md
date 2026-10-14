# Product Filtering, Comparison and Sorting — automated tests

32571 Enterprise Software Testing, Assessment Task 3. Tester: Christian Fernando.
Website under test: https://ecommerce-playground.lambdatest.io/

| Test case | Function | File | Scenarios |
|---|---|---|---|
| T005 | F5 Filter Products (price, manufacturer, availability) | `tests/test_t005_filtering.py` | 3 (scenario 3 runs 5 invalid inputs) |
| T006 | F6 Manage Product Comparison List | `tests/test_t006_comparison.py` | 3 |
| T007 | F7 Sort Products (price, name, model) | `tests/test_t007_sorting.py` | 3 |

Step-by-step scenarios with expected results are in `TEST_CASES.md`.

Tools: Python 3.9+, pytest, Playwright for Python (Chromium), pytest-html.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Running

```bash
python -m pytest                       # all 13 report rows, headless
python -m pytest --headed --slowmo 500 # watch the browser do it
python -m pytest -m comparison         # one test case (filtering / comparison / sorting)
python -m pytest -s                    # also show printed evidence
```

Results go to `report.html`; a full-page screenshot of every run goes to `screenshots/`.

## Notes

- Every test gets a fresh browser session, so the comparison list always starts empty.
- The category used is Desktops (`path=20`), set once in `helpers.py` (`CATEGORY_URL`).
- Selectors that depend on the Mazaar theme are all in `helpers.py`:
  `PRODUCT_CARD`, `filter_section()` (finds a filter block by its heading,
  e.g. "Manufacturer"), `price_boxes()`, `choose_sort()`, `choose_limit()`,
  `compare_row()`. The list-view button is in T007 scenario 3.
