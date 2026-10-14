if __name__ == "__main__":  # lets the ▶ Run Python File button run this file's tests
    import os, subprocess, sys
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", os.path.abspath(__file__)], cwd=project))

"""
T007 - Sort Products (F7)
Tester: Christian Fernando

  Scenario 1  Price sorting, both directions, over the WHOLE category
      - 'Show 100' so every product is on one page, then Low > High and High > Low
      - order is correct, no product is lost or duplicated by sorting, and
        High > Low is the mirror of Low > High
      - with the default 15 per page, the order also holds ACROSS page breaks
  Scenario 2  Name and Model sorting, both directions
      - Name (A - Z) / (Z - A) and Model (A - Z) / (Z - A)
      - checked case-insensitively, the way the database sorts
  Scenario 3  Sorting works together with other controls, and resists tampering
      - sort is kept after applying a price filter, switching grid/list view,
        and moving to page 2
      - tampered sort/order values in the URL give no server or SQL error
"""
import pytest
from playwright.sync_api import Page, expect

from helpers import (CATEGORY_URL, apply_price_filter, assert_no_error_leak,
                     choose_limit, choose_sort, listed_names, listed_prices,
                     listed_product_ids, next_page_link, product_page_details,
                     result_total, visible_cards, walk_result_pages)

PRICE_ASC, PRICE_DESC = "Price (Low > High)", "Price (High > Low)"
NAME_ASC, NAME_DESC = "Name (A - Z)", "Name (Z - A)"
MODEL_ASC, MODEL_DESC = "Model (A - Z)", "Model (Z - A)"


def is_ascending(values, key=lambda v: v):
    return all(key(a) <= key(b) for a, b in zip(values, values[1:]))


def is_descending(values, key=lambda v: v):
    return all(key(a) >= key(b) for a, b in zip(values, values[1:]))


# --------------------------------------------------------------------------
@pytest.mark.sorting
def test_scenario1_price_sort_both_directions_whole_category(page: Page):
    page.goto(CATEGORY_URL)
    total = result_total(page)

    # Step 1: show every product on one page
    choose_limit(page, "100")
    assert "limit=100" in page.url
    assert len(visible_cards(page).all()) == min(total, 100)

    # Step 2: Low > High
    choose_sort(page, PRICE_ASC)
    assert "sort=p.price" in page.url and "order=ASC" in page.url
    asc_prices, asc_ids = listed_prices(page), listed_product_ids(page)
    assert len(asc_prices) > 1
    assert is_ascending(asc_prices), f"Prices not ascending: {asc_prices}"

    # Step 3: High > Low
    choose_sort(page, PRICE_DESC)
    assert "order=DESC" in page.url
    desc_prices, desc_ids = listed_prices(page), listed_product_ids(page)
    assert is_descending(desc_prices), f"Prices not descending: {desc_prices}"

    # Step 4: sorting must not add, drop or duplicate products
    assert sorted(asc_ids) == sorted(desc_ids), "The two sort orders list different products"
    assert len(asc_ids) == len(set(asc_ids)), "A product appears twice"
    assert desc_prices == list(reversed(asc_prices)), "High > Low is not the mirror of Low > High"

    # Step 5: back to 15 per page - order must hold across the page break
    page.goto(CATEGORY_URL)
    choose_sort(page, PRICE_ASC)
    last_price = None
    for page_no in walk_result_pages(page):
        prices = listed_prices(page)
        assert "sort=p.price" in page.url, f"Sort lost on results page {page_no}"
        assert is_ascending(prices), f"Page {page_no} not ascending: {prices}"
        if last_price is not None:
            assert last_price <= prices[0], \
                f"Page {page_no} starts at ${prices[0]}, previous page ended at ${last_price}"
        last_price = prices[-1]


# --------------------------------------------------------------------------
@pytest.mark.sorting
def test_scenario2_name_and_model_sort_both_directions(page: Page):
    page.goto(CATEGORY_URL)

    # Step 1: Name A - Z
    choose_sort(page, NAME_ASC)
    assert "sort=pd.name" in page.url and "order=ASC" in page.url
    names_asc = listed_names(page)
    assert len(names_asc) > 1
    assert is_ascending(names_asc, str.casefold), f"Names not A-Z: {names_asc}"

    # Step 2: Name Z - A
    choose_sort(page, NAME_DESC)
    assert "sort=pd.name" in page.url and "order=DESC" in page.url
    names_desc = listed_names(page)
    assert is_descending(names_desc, str.casefold), f"Names not Z-A: {names_desc}"
    assert names_desc[0].casefold() >= names_asc[0].casefold()

    # Step 3: Model A - Z / Z - A. The model code is not on the tile, so read
    # it from the first few products' pages.
    for label, check in ((MODEL_ASC, is_ascending), (MODEL_DESC, is_descending)):
        page.goto(CATEGORY_URL)
        choose_sort(page, label)
        assert "sort=p.model" in page.url, f"{label} did not set sort=p.model"
        models = []
        for pid in listed_product_ids(page)[:5]:
            model = product_page_details(page, pid)["model"]
            assert model, f"Product {pid} page shows no Product Code"
            models.append(model)
        assert check(models, str.casefold), f"{label}: models out of order {models}"


# --------------------------------------------------------------------------
@pytest.mark.sorting
def test_scenario3_sort_with_filter_view_paging_and_tampering(page: Page):
    # Step 1: filter $100-$500, then sort Low > High -> both rules hold
    page.goto(CATEGORY_URL)
    apply_price_filter(page, "100", "500")
    choose_sort(page, PRICE_ASC)
    assert "mz_fp" in page.url, "Choosing a sort dropped the price filter"
    prices = listed_prices(page)
    assert prices and all(100 <= p <= 500 for p in prices), f"Filter lost after sorting: {prices}"
    assert is_ascending(prices), f"Filtered list not ascending: {prices}"

    # Step 2: switch to list view -> same products in the same order
    order_before = listed_product_ids(page)
    page.locator("#list-view:visible, button[title='List']:visible").first.click()
    page.wait_for_load_state("networkidle")
    assert listed_product_ids(page) == order_before, "Changing view changed the order"

    # Step 3: unfiltered category, sort High > Low, go to page 2 -> sort kept
    page.goto(CATEGORY_URL)
    choose_sort(page, PRICE_DESC)
    page1_last = listed_prices(page)[-1]
    if next_page_link(page).count():
        page.goto(next_page_link(page).first.get_attribute("href"))
        assert "sort=p.price" in page.url and "order=DESC" in page.url, "Page 2 lost the sort"
        page2 = listed_prices(page)
        assert is_descending(page2) and page2[0] <= page1_last

    # Step 4: tampered values typed into the URL (the drop-down can't make these)
    for bad in ("&sort=p.price;DROP TABLE x&order=ASC",
                "&sort=p.price&order=SIDEWAYS",
                "&sort=nonexistent_column&order=DESC",
                "&sort=%27%22&order=%3Cscript%3E"):
        response = page.goto(CATEGORY_URL + bad)
        assert response.status == 200, f"{bad!r}: server returned HTTP {response.status}"
        assert_no_error_leak(page)
        expect(visible_cards(page).first).to_be_visible()
