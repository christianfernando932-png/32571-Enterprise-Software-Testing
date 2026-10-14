# Test cases T005–T007 (Christian Fernando)

## T005 — Filter Products (F5)

| # | Scenario | Steps | Expected result |
|---|---|---|---|
| 1 | Price range filter | 1. Open Desktops, note total. 2. Filter $100–$500. 3. Check every product on every results page. 4. Filter on exactly one real product's price (min = max). 5. Clear both boxes. | Total shrinks but is > 0; every price is within $100–$500 on all pages; paging shows each product once; the min = max range finds that product (boundaries inclusive); clearing restores the original total. |
| 2 | Manufacturer + availability, combined | 1. Tick the first manufacturer. 2. Open sample products. 3. Add Availability = In stock. 4. Open sample products. 5. Add $100–$500 on top. | Each filter can only narrow the list (AND logic); sampled products show the chosen brand; after step 3 they are also "In Stock"; after step 5 all three rules hold together. |
| 3 | Invalid / no-match input (5 runs) | Enter: 90000–99999; 1000–100; −500 to −1; 0–99999999999999999999; "abc"–"xyz". | 90000–99999, 1000–100 and −500 to −1 each show "There are no products to list in this category." (dearest product is $2,000; min > max and prices below $0 are impossible). 0–99999999999999999999 lists every product (same total as unfiltered: a valid, very wide range). Letters are refused by the browser's number field, so no filter is applied. No SQL/PHP error text in any run. |

## T006 — Manage Product Comparison List (F6)

| # | Scenario | Steps | Expected result |
|---|---|---|---|
| 1 | Add from two entry points, verify data | 1. Add product A from its product page. 2. Add product B from its tile on the category page. 3. Open Product Comparison. | Both adds return a success message naming the product; both columns appear; name, price, brand and availability in each column match the product page. |
| 2 | Remove products and empty state | 1. Open comparison as a new visitor. 2. Add 3 products. 3. Remove the middle one. 4. Reload. 5. Remove the other two. | Empty message at start; after step 3 exactly the other two remain; the removal survives a reload; empty message returns at the end. |
| 3 | Duplicates, 4-product limit, persistence, invalid id | 1. Add the same product twice. 2. Add 4 more (5 in total). 3. Visit home and category, return and reload. 4. Add product_id 999999. | One column for the duplicate; only 4 products kept, oldest dropped; list unchanged after navigating and reloading; invalid id is rejected and the list is unchanged. |

## T007 — Sort Products (F7)

| # | Scenario | Steps | Expected result |
|---|---|---|---|
| 1 | Price sort, both directions, whole category | 1. Show 100 per page. 2. Price (Low > High). 3. Price (High > Low). 4. Compare the two lists. 5. Back to 15 per page, Low > High, walk every page. | All products on one page; ascending then descending order; both lists hold the same products with no duplicates and one is the mirror of the other; order holds across page breaks and the sort stays in the URL. |
| 2 | Name and model sort, both directions | 1. Name (A – Z). 2. Name (Z – A). 3. Model (A – Z) and (Z – A), reading product codes from product pages. | Names in case-insensitive A–Z then Z–A order; product codes in the matching order for each model option. |
| 3 | Sort with other controls + tampering | 1. Filter $100–$500, sort Low > High. 2. Switch to list view. 3. Sort High > Low, go to page 2. 4. Load 4 tampered sort/order URLs. | Filter and sort both kept; view change keeps the same order; page 2 keeps the sort and continues it; tampered URLs return HTTP 200 with products and no error text. |

## How the 13 pytest rows map to the 9 scenarios

| Test case | Scenario | pytest rows |
|---|---|---|
| T005 | S1 Price range | 1 |
| T005 | S2 Manufacturer + availability | 1 |
| T005 | S3 Invalid / no-match input | 5 (one per input) |
| T006 | S1, S2, S3 | 3 |
| T007 | S1, S2, S3 | 3 |
| | 9 scenarios | 13 |
