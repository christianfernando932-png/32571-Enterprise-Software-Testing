if __name__ == "__main__":  # lets the ▶ Run Python File button run this file's tests
    import os, subprocess, sys
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", os.path.abspath(__file__)], cwd=project))

"""
T006 - Manage Product Comparison List (F6)
Tester: Christian Fernando

  Scenario 1  Add products from different places and check the table is correct
      - one product from its product page, one from the category listing
      - both appear, and each column's name / price / brand / availability
        matches what the product page says (data integrity, not just presence)
  Scenario 2  Remove products and the empty state
      - a new visitor sees the empty message
      - with three products, removing the middle one keeps the other two
      - removing the rest returns to the empty message
  Scenario 3  List rules: duplicates, the 4-product limit, persistence, bad input
      - adding the same product twice gives one column
      - adding five products keeps four and drops the oldest
      - the list survives navigating away and reloading
      - a non-existent product_id is rejected and the list is unchanged
"""
import re

import pytest
from playwright.sync_api import Page, expect

from helpers import (BASE_URL, CATEGORY_URL, COMPARE_URL, NO_COMPARE_MSG,
                     add_to_compare_via_request, compare_row, compared_product_ids,
                     listed_product_ids, parse_last_price, remove_link, product_page_details,
                     product_url, visible_cards)


def first_product_ids(page: Page, how_many: int) -> list[str]:
    """Pick real product IDs from the category page instead of hard-coding them."""
    page.goto(CATEGORY_URL)
    ids = listed_product_ids(page)
    assert len(ids) >= how_many, f"Need {how_many} products, category lists {len(ids)}"
    return ids[:how_many]


def click_compare_on_product_page(page: Page, product_id: str) -> dict:
    """Product page -> 'Compare this Product' button; returns the site's JSON."""
    page.goto(product_url(product_id))
    btn = page.locator("button[title='Compare this Product']:visible, "
                       "button.btn-compare:visible").first
    with page.expect_response(lambda r: "product/compare/add" in r.url) as info:
        btn.click()
    return info.value.json()


def click_compare_on_listing_tile(page: Page, product_id: str) -> dict:
    """Category page -> hover the product's tile -> its compare button."""
    page.goto(CATEGORY_URL)
    tile = visible_cards(page).filter(
        has=page.locator(f"h4 a[href*='product_id={product_id}']")).first
    tile.hover()                                  # Mazaar shows tile buttons on hover
    btn = tile.locator("button[title*='Compare'], button.btn-compare, "
                       "[onclick*='compare.add']").first
    with page.expect_response(lambda r: "product/compare/add" in r.url) as info:
            btn.click()
    return info.value.json()


def remove_from_comparison(page: Page, product_id: str):
    """Click the Remove button in the column of the given product."""
    remove_link(page, product_id).click()
    page.wait_for_load_state("networkidle")


# --------------------------------------------------------------------------
@pytest.mark.comparison
def test_scenario1_add_from_two_entry_points_and_verify_table(page: Page):
    product_a, product_b = first_product_ids(page, 2)

    # Step 1: product A from its product page; success message names the product
    res_a = click_compare_on_product_page(page, product_a)
    assert "success" in res_a, f"Product {product_a} was not added: {res_a}"

    # Step 2: product B straight from the category listing tile
    res_b = click_compare_on_listing_tile(page, product_b)
    assert "success" in res_b, f"Product {product_b} was not added: {res_b}"

    # Step 3: collect the truth from each product page
    expected = {pid: product_page_details(page, pid) for pid in (product_a, product_b)}
    for pid, res in ((product_a, res_a), (product_b, res_b)):
        plain = re.sub(r"<[^>]+>", "", res["success"])
        assert expected[pid]["name"] in plain, f"Success message does not name the product: {plain!r}"

    # Step 4: comparison page shows both products ...
    page.goto(COMPARE_URL)
    expect(page.get_by_role("heading", name="Product Comparison")).to_be_visible()
    shown = compared_product_ids(page)
    assert set(shown) == {product_a, product_b}

    # ... and every column matches its product page
    names, prices = compare_row(page, "Product"), compare_row(page, "Price")
    brands, stock = compare_row(page, "Brand"), compare_row(page, "Availability")
    for col, pid in enumerate(shown):
        want = expected[pid]
        assert names[col] == want["name"], f"Name column {col}: {names[col]!r} != {want['name']!r}"
        assert parse_last_price(prices[col]) == want["price"], f"Price mismatch for {want['name']}"
        assert brands[col].casefold() == want["brand"].casefold(), f"Brand mismatch for {want['name']}"
        assert stock[col].casefold() == want["availability"].casefold(), f"Availability mismatch for {want['name']}"


# --------------------------------------------------------------------------
@pytest.mark.comparison
def test_scenario2_remove_products_and_empty_state(page: Page):
    # Step 1: a brand-new visitor has nothing to compare
    page.goto(COMPARE_URL)
    expect(page.get_by_text(NO_COMPARE_MSG)).to_be_visible()
    assert compared_product_ids(page) == []

    # Step 2: add three products
    ids = first_product_ids(page, 3)
    for pid in ids:
        assert "success" in add_to_compare_via_request(page, pid)
    page.goto(COMPARE_URL)
    assert set(compared_product_ids(page)) == set(ids)

    # Step 3: remove the middle one -> exactly the other two remain
    remove_from_comparison(page, ids[1])
    remaining = compared_product_ids(page)
    assert ids[1] not in remaining, "Removed product is still shown"
    assert set(remaining) == {ids[0], ids[2]}, f"Wrong products left: {remaining}"

    # Step 4: removal is saved, not just hidden (still gone after reload)
    page.reload()
    assert set(compared_product_ids(page)) == {ids[0], ids[2]}

    # Step 5: remove the rest -> empty message again
    for pid in (ids[0], ids[2]):
        remove_from_comparison(page, pid)
    expect(page.get_by_text(NO_COMPARE_MSG)).to_be_visible()
    assert compared_product_ids(page) == []


# --------------------------------------------------------------------------
@pytest.mark.comparison
def test_scenario3_duplicates_limit_persistence_and_invalid_id(page: Page):
    ids = first_product_ids(page, 5)

    # Step 1: duplicate - same product added twice gives one column
    assert "success" in add_to_compare_via_request(page, ids[0])
    add_to_compare_via_request(page, ids[0])
    page.goto(COMPARE_URL)
    assert compared_product_ids(page) == [ids[0]], "Duplicate product created a second column"

    # Step 2: limit - add the other four (five in total), oldest first
    for pid in ids[1:]:
        assert "success" in add_to_compare_via_request(page, pid)
    page.goto(COMPARE_URL)
    shown = compared_product_ids(page)
    assert len(shown) == 4, f"Expected 4 products, comparison shows {len(shown)}: {shown}"
    assert ids[0] not in shown, "Oldest product should have been dropped"
    assert set(shown) == set(ids[1:])

    # Step 3: persistence - browse elsewhere, come back, reload
    page.goto(f"{BASE_URL}?route=common/home")
    page.goto(CATEGORY_URL)
    page.goto(COMPARE_URL)
    page.reload()
    assert set(compared_product_ids(page)) == set(ids[1:]), "List was not kept for the session"

    # Step 4: invalid product id - rejected, list unchanged
    result = add_to_compare_via_request(page, "999999")
    assert "success" not in result, f"Non-existent product was accepted: {result}"
    page.goto(COMPARE_URL)
    assert set(compared_product_ids(page)) == set(ids[1:]), "Invalid add changed the list"
