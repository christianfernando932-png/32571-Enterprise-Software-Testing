"""
Shared helpers for the product filtering / comparison / sorting tests.

Website under test: LambdaTest eCommerce Playground (OpenCart + Mazaar theme)
https://ecommerce-playground.lambdatest.io/
"""
import re
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import Page, Locator

BASE_URL = "https://ecommerce-playground.lambdatest.io/index.php"

# Category used for filtering and sorting (path=20 -> "Desktops").
# If your group uses a different category, change it here only.
CATEGORY_URL = f"{BASE_URL}?route=product/category&path=20"
COMPARE_URL = f"{BASE_URL}?route=product/compare"


def product_url(product_id: str) -> str:
    return f"{BASE_URL}?route=product/product&product_id={product_id}"


# Messages OpenCart shows for empty states
NO_PRODUCTS_MSG = "There are no products to list in this category."
NO_COMPARE_MSG = "You have not chosen any products to compare."

# Text that must never appear on a page (server / database errors leaking out)
ERROR_LEAKS = ("sql syntax", "fatal error", "warning:", "exception", "notice:")

# Each product tile in the main listing of a category / search results page.
# "product-grid" / "product-list" are only on the main listing, so side
# modules such as "Bestsellers" are not picked up by mistake.
PRODUCT_CARD = ".product-layout.product-grid, .product-layout.product-list"


# --------------------------------------------------------------------------
# Reading the product listing
# --------------------------------------------------------------------------
def visible_cards(page: Page) -> Locator:
    """Return a locator for all product tiles currently listed on the page."""
    return page.locator(PRODUCT_CARD).filter(has=page.locator("h4 a"))


def parse_price(text: str) -> float:
    """Turn '$1,234.50' (or '$98.00 $122.00' for a special) into 1234.5.
    The FIRST amount is the price the customer actually pays."""
    match = re.search(r"\$\s?([\d,]+\.\d{2})", text)
    if not match:
        raise ValueError(f"No price found in: {text!r}")
    return float(match.group(1).replace(",", ""))


def parse_last_price(text: str) -> float:
    """Last $ amount in a cell. The comparison table shows a special as
    '<strike>$122.00</strike> $98.00', so the price paid is the LAST amount."""
    amounts = re.findall(r"\$\s?([\d,]+\.\d{2})", text)
    if not amounts:
        raise ValueError(f"No price found in: {text!r}")
    return float(amounts[-1].replace(",", ""))


def card_price(card: Locator) -> float:
    # .price-new exists when a product is on special; otherwise use .price
    special = card.locator(".price-new")
    text = special.first.inner_text() if special.count() else card.locator(".price").first.inner_text()
    return parse_price(text)


def listed_prices(page: Page) -> list[float]:
    """Prices of every listed product, in on-screen order."""
    return [card_price(c) for c in visible_cards(page).all()]


def listed_names(page: Page) -> list[str]:
    """Product names of every listed product, in on-screen order."""
    return [c.locator("h4 a").first.inner_text().strip() for c in visible_cards(page).all()]


def id_from_href(href: str):
    return parse_qs(urlparse(href or "").query).get("product_id", [None])[0]


def listed_product_ids(page: Page) -> list[str]:
    """product_id values of every listed product (unique, on-screen order)."""
    ids = []
    for card in visible_cards(page).all():
        pid = id_from_href(card.locator("h4 a").first.get_attribute("href"))
        if pid and pid not in ids:
            ids.append(pid)
    return ids


def result_total(page: Page) -> int:
    """Total number of matching products, read from OpenCart's
    'Showing 1 to 15 of 26 (2 Pages)' line. Returns 0 for an empty list."""
    if page.get_by_text(NO_PRODUCTS_MSG).count():
        return 0
    line = page.get_by_text(re.compile(r"Showing \d+ to \d+ of \d+")).first
    match = re.search(r"of (\d+)", line.inner_text())
    assert match, f"Could not read the product total from: {line.inner_text()!r}"
    return int(match.group(1))


def next_page_link(page: Page) -> Locator:
    return page.locator(".pagination a", has_text=">").filter(visible=True).filter(has_not_text=">|")


def walk_result_pages(page: Page, max_pages: int = 20):
    """Yield once for the current results page, then follow the 'Next' link and
    yield again for every following page. The link's own URL is loaded (a full
    page load), so the list is never read while an AJAX refresh is half done,
    and the test still proves the site's pagination link keeps the filter/sort."""
    number = 1
    while True:
        yield number
        nxt = next_page_link(page)
        if nxt.count() == 0:
            return
        page.goto(nxt.first.get_attribute("href"))
        number += 1
        assert number <= max_pages, "Too many result pages visited"


def assert_no_error_leak(page: Page):
    body = page.inner_text("body").lower()
    for leak in ERROR_LEAKS:
        assert leak not in body, f"Error text leaked on page: {leak!r}"


# --------------------------------------------------------------------------
# Product page details (used to check that a filter really did its job)
# Verified on the live site: the product page's main block is #product-product
# (there is NO #content on product pages) and the details are list items like
#   <li><span class="ls-label">Brand:</span> Apple</li>
# --------------------------------------------------------------------------
PRODUCT_ROOT = "#product-product"


def product_field(page: Page, label: str) -> str:
    """Value of a 'Label: value' list item on the product page ('' if absent)."""
    item = page.locator(f"{PRODUCT_ROOT} li").filter(
        has=page.locator(".ls-label", has_text=re.compile(rf"^\s*{label}:"))).first
    if item.count() == 0:
        return ""
    text = item.text_content() or ""
    return re.sub(rf"^\s*{label}:\s*", "", " ".join(text.split())).strip()


def product_page_details(page: Page, product_id: str) -> dict:
    """Open a product page and read name, Brand, Availability, Product Code
    and the price the customer pays."""
    page.goto(product_url(product_id))
    root = page.locator(PRODUCT_ROOT)
    root.wait_for(timeout=15_000)
    price_box = root.locator(".price-new:visible, .price:visible").first
    return {
        "name": root.locator("h1").first.inner_text().strip(),
        "brand": product_field(page, "Brand"),
        "availability": product_field(page, "Availability"),
        "model": product_field(page, "Product Code"),
        "price": parse_price(price_box.inner_text()),
    }


# --------------------------------------------------------------------------
# Filter panel (Mazaar "mz_filter" module on the left of a category page)
#
# Verified on the live site: every filter change is applied with AJAX - the
# browser calls  index.php?route=extension/module/mz_filter/product&...&mz_fp=146p146
# and redraws the list. The URL changes BEFORE the list is redrawn, so waiting
# for the URL is not enough: we wait for that request to finish.
# Price is sent as mz_fp=<min>p<max>; manufacturer as mz_fm=<id>;
# availability as mz_fss=<id> (In stock = -1, Out Of Stock = 5).
# There are two copies of the panel (desktop + hidden mobile), hence :visible.
# --------------------------------------------------------------------------
FILTER_GROUPS = {
    "Manufacturer": ".mz-filter-group.manufacturer",
    "Availability": ".mz-filter-group.stock_status",
}
FILTER_REQUEST = "extension/module/mz_filter/product"


def filter_section(page: Page, title: str) -> Locator:
    return page.locator(f"{FILTER_GROUPS[title]}:visible").first


def option_label_text(label: Locator) -> str:
    """Name of a filter option (logo options fall back to the image alt)."""
    text = label.inner_text().strip()
    if not text:
        img = label.locator("img")
        if img.count():
            text = img.first.get_attribute("alt") or img.first.get_attribute("title") or ""
    return re.sub(r"\s*\(\d+\)\s*$", "", text).strip()


def run_filter_action(page: Page, action, url_pattern: str, timeout: int = 15_000):
    """Do `action()` and wait until the filter AJAX request whose URL matches
    `url_pattern` (a regex) has finished and the list has been redrawn."""
    pattern = re.compile(url_pattern)
    with page.expect_response(lambda r: FILTER_REQUEST in r.url and pattern.search(r.url),
                              timeout=timeout):
        action()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)          # let the theme swap the new HTML in


def tick_filter_option(page: Page, section_title: str, option_text: str = None) -> str:
    """Tick one option in a filter section (the first one if option_text is
    None), wait for the refreshed list and return the option's name."""
    section = filter_section(page, section_title)
    labels = section.locator("label[for]").filter(visible=True)
    label = labels.filter(has_text=re.compile(option_text, re.I)).first if option_text else labels.first
    name = option_label_text(label)
    box = page.locator(f"[id='{label.get_attribute('for')}']")
    param, value = box.get_attribute("name"), box.get_attribute("value")
    run_filter_action(page, lambda: label.evaluate("(el) => el.click()"), rf"[?&]{param}=[^&]*{re.escape(value)}")
    return name


def price_boxes(page: Page):
    """':visible' skips the hidden copy used by the mobile layout."""
    min_box = page.locator("input[name='mz_fp[min]']:visible").first
    max_box = page.locator("input[name='mz_fp[max]']:visible").first
    return min_box, max_box


def apply_price_filter(page: Page, minimum: str, maximum: str, timeout: int = 15_000):
    """Type min and max like a user, then wait for the request carrying BOTH
    values (mz_fp=<min>p<max>). Typing in the second box makes the first box
    send its own request (min + old max) - that intermediate result is ignored."""
    min_box, max_box = price_boxes(page)

    def type_both():
        min_box.fill(minimum)
        max_box.fill(maximum)
        max_box.press("Enter")
        max_box.blur()

    run_filter_action(page, type_both,
                      rf"mz_fp={re.escape(minimum)}p{re.escape(maximum)}(&|$)", timeout)


# --------------------------------------------------------------------------
# Sort / Show controls
# --------------------------------------------------------------------------
def choose_sort(page: Page, label: str):
    """Pick an option in the Sort By drop-down (id like 'input-sort-212403')."""
    sort_select = page.locator("select[id^='input-sort']:visible").first
    with page.expect_navigation():
        sort_select.select_option(label=label)
    page.wait_for_load_state("networkidle")


def choose_limit(page: Page, how_many: str):
    """Pick an option in the 'Show' drop-down (products per page)."""
    limit_select = page.locator("select[id^='input-limit']:visible").first
    with page.expect_navigation():
        limit_select.select_option(label=how_many)
    page.wait_for_load_state("networkidle")


# --------------------------------------------------------------------------
# Comparison list
# --------------------------------------------------------------------------
def compared_product_ids(page: Page) -> list[str]:
    """product_id values of the products shown in the comparison table."""
    ids = []
    for link in page.locator("#content table a[href*='product_id=']").all():
        pid = id_from_href(link.get_attribute("href"))
        if pid and pid not in ids:
            ids.append(pid)
    return ids


def remove_link(page: Page, product_id: str) -> Locator:
    """'Remove' button under a product's column (href ends in remove=<id>)."""
    return page.locator(f"#content a[href$='remove={product_id}']").first


def compare_row(page: Page, label: str) -> list[str]:
    """Cell texts of one row of the comparison table (e.g. 'Price', 'Brand'),
    one entry per compared product, left to right."""
    row = page.locator("#content table tr").filter(
        has=page.locator("td:first-child", has_text=re.compile(rf"^\s*{label}\s*$"))).first
    return [c.inner_text().strip() for c in row.locator("td").all()[1:]]


def add_to_compare_via_request(page: Page, product_id: str) -> dict:
    """Add a product to the comparison list using the same AJAX call the
    'Compare this Product' button makes. Shares the browser's session cookie,
    so it is used to set up test data quickly."""
    resp = page.request.post(f"{BASE_URL}?route=product/compare/add",
                             form={"product_id": product_id})
    assert resp.ok, f"compare/add returned HTTP {resp.status}"
    return resp.json()
