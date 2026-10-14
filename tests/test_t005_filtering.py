if __name__ == "__main__":  # lets the ▶ Run Python File button run this file's tests
    import os, subprocess, sys
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", os.path.abspath(__file__)], cwd=project))

"""
T005 - Filter Products (F5): price, manufacturer and availability
Tester: Christian Fernando

Uses the left-hand "Filter" panel of the Desktops category page.

  Scenario 1  Price range filter
      - every product on every results page is inside the range
      - boundaries are inclusive (a range of exactly one product's price finds it)
      - clearing the range brings back the full, unfiltered list
  Scenario 2  Manufacturer + availability filters, alone and combined
      - a manufacturer filter only lists that brand (checked on product pages)
      - adding "In stock" narrows the list further and every product is in stock
      - adding a price range on top: filters combine with AND, never widen
  Scenario 3  Invalid and no-match filter input (one row per input in the report)
      - range with no products, min > max, negative, non-numeric, huge number
      - expected: no crash / error text, and never a product outside the rule
"""
import re
import pytest
from playwright.sync_api import Page, Error, expect

from helpers import (CATEGORY_URL, NO_PRODUCTS_MSG, apply_price_filter,
                     assert_no_error_leak, listed_prices, listed_product_ids,
                     price_boxes, product_page_details, result_total,
                     run_filter_action, tick_filter_option, visible_cards, walk_result_pages)

LOW, HIGH = 100, 500
SAMPLE_SIZE = 4          # product pages opened per filter to confirm brand / stock


# --------------------------------------------------------------------------
@pytest.mark.filtering
def test_scenario1_price_range_filter(page: Page):
    # Step 1: open the category and note the unfiltered total
    page.goto(CATEGORY_URL)
    expect(visible_cards(page).first).to_be_visible()
    total_before = result_total(page)
    a_real_price = listed_prices(page)[0]

    # Step 2: filter on $100 - $500
    apply_price_filter(page, str(LOW), str(HIGH))
    filtered_total = result_total(page)
    assert 0 < filtered_total <= total_before

    # Step 3: every product on every results page is inside the range
    seen = []
    for page_no in walk_result_pages(page):
        prices = listed_prices(page)
        assert prices, f"Results page {page_no} is empty"
        bad = [p for p in prices if not LOW <= p <= HIGH]
        assert not bad, f"Page {page_no} lists prices outside ${LOW}-${HIGH}: {bad}"
        seen.extend(prices)
    assert len(seen) == filtered_total, "Paging lost or repeated products"

    # Step 4: boundary - a range of exactly one real price must include it
    page.goto(CATEGORY_URL)
    exact = f"{a_real_price:.0f}" if a_real_price.is_integer() else f"{a_real_price}"
    apply_price_filter(page, exact, exact)

    page.wait_for_function(
        """expected => {
            const cards = [...document.querySelectorAll(
                '.product-layout.product-grid, .product-layout.product-list'
            )].filter(card => card.querySelector('h4 a'));

            return cards.length > 0 && cards.every(card => {
                const price = card.querySelector('.price-new') || card.querySelector('.price');
                const match = price?.textContent.match(/\\$\\s*([\\d,]+\\.\\d{2})/);
                return match && Number(match[1].replace(/,/g, '')) === expected;
            });
        }""",
        arg=a_real_price,
        timeout=15000
    )
    prices = listed_prices(page)
    assert prices, f"Inclusive boundary failed: nothing found for ${exact}-${exact}"
    assert all(p == a_real_price for p in prices), f"Expected only ${exact}, got {prices}"

    # Step 5: clearing both boxes restores the full list
    # (the site then sends mz_fp=p, i.e. no min and no max)
    min_box, max_box = price_boxes(page)

    def clear_both():
        min_box.fill("")
        max_box.fill("")
        max_box.press("Enter")
        max_box.blur()

    run_filter_action(page, clear_both, r"mz_fp=p(&|$)")

    expect(
        page.get_by_text(re.compile(r"Showing \d+ to \d+ of \d+")).first
    ).to_contain_text(f"of {total_before} ", timeout=15000)

    assert result_total(page) == total_before, "Clearing the price filter did not restore all products"


# --------------------------------------------------------------------------
@pytest.mark.filtering
def test_scenario2_manufacturer_and_availability_filters(page: Page):
    page.goto(CATEGORY_URL)
    total_all = result_total(page)

    # Step 1: tick the first manufacturer in the panel
    brand = tick_filter_option(page, "Manufacturer")
    assert brand, "Could not read the manufacturer option's name"
    total_brand = result_total(page)
    assert 0 < total_brand <= total_all, f"{brand}: {total_brand} of {total_all} products"
    brand_url = page.url
    brand_ids = listed_product_ids(page)

    # Step 2: each sampled product really is made by that manufacturer
    for pid in brand_ids[:SAMPLE_SIZE]:
        details = product_page_details(page, pid)
        assert details["brand"].casefold() == brand.casefold(), \
            f"'{details['name']}' is brand '{details['brand']}', filter was '{brand}'"

    # Step 3: add Availability = In stock -> list can only shrink
    page.goto(brand_url)
    tick_filter_option(page, "Availability", r"in\s*stock")
    total_brand_stock = result_total(page)
    assert total_brand_stock <= total_brand, "Adding a second filter widened the results"
    stock_url = page.url

    for pid in listed_product_ids(page)[:SAMPLE_SIZE]:
        details = product_page_details(page, pid)
        assert details["brand"].casefold() == brand.casefold()
        assert details["availability"].casefold() == "in stock", \
            f"'{details['name']}' shows availability '{details['availability']}'"

    # Step 4: add a price range on top -> all three rules hold together
    page.goto(stock_url)
    if total_brand_stock == 0:
        pytest.skip(f"No in-stock {brand} products to combine with a price range")
    apply_price_filter(page, str(LOW), str(HIGH))
    assert result_total(page) <= total_brand_stock
    page.wait_for_timeout(2000)
    print("Combined filter URL:", page.url)
    print("Prices after waiting:", listed_prices(page))
    bad = [p for p in listed_prices(page) if not LOW <= p <= HIGH]
    assert not bad, f"Combined filters listed prices outside ${LOW}-${HIGH}: {bad}"
    for pid in listed_product_ids(page)[:2]:
        details = product_page_details(page, pid)
        assert details["brand"].casefold() == brand.casefold()
        assert details["availability"].casefold() == "in stock"


# --------------------------------------------------------------------------
# Expected results, and why (behaviour confirmed on the live site 15-Oct-2026):
#   no_products_in_range  90000-99999  -> empty message: dearest product is $2,000
#   min_greater_than_max  1000-100     -> empty message: no price can be >=1000 AND <=100
#   negative_numbers      -500 to -1   -> empty message: no product costs less than $0
#   extremely_large_max   0-1e20       -> EVERY product listed (same total as
#                                         unfiltered): a valid, very wide range
#   non_numeric_text      abc / xyz    -> the browser's number field refuses the
#                                         text, so no filter request is ever sent
# In every case: HTTP-level health, no SQL / PHP error text on the page.
INVALID_RANGES = [
    pytest.param("90000", "99999", "empty", id="no_products_in_range"),
    pytest.param("1000", "100", "empty", id="min_greater_than_max"),
    pytest.param("-500", "-1", "empty", id="negative_numbers"),
    pytest.param("0", "99999999999999999999", "everything", id="extremely_large_max"),
    pytest.param("abc", "xyz", "refused", id="non_numeric_text"),
]


@pytest.mark.filtering
@pytest.mark.parametrize("minimum,maximum,expected", INVALID_RANGES)
def test_scenario3_invalid_and_no_match_price_input(page: Page, minimum, maximum, expected):
    page.goto(CATEGORY_URL)
    total_before = result_total(page)
    ids_before = listed_product_ids(page)
    min_box, _ = price_boxes(page)

    if expected == "refused":
        # Step 1: typing letters into the number field must fail ...
        with pytest.raises(Error, match=r"(?i)cannot type text|number"):
            min_box.fill(minimum)
        # ... and the list is untouched
        assert listed_product_ids(page) == ids_before
        assert_no_error_leak(page)
        return

    # Step 1: type the values and wait for the site's filter request
    apply_price_filter(page, minimum, maximum)

    # Step 2: the site stays healthy
    assert_no_error_leak(page)

    # Step 3: the justified expected result
    if expected == "empty":
        assert listed_prices(page) == [], f"{minimum}-{maximum} should match nothing"
        expect(page.get_by_text(NO_PRODUCTS_MSG)).to_be_visible()
    else:  # "everything"
        assert result_total(page) == total_before, \
            f"0-{maximum} should list all {total_before} products, got {result_total(page)}"
