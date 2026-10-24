# Missing-Value Handling

Part of **Business Data Management**, the cleaning stage of the processing
pipeline. Runs on the standardized product line-item DataFrame, before or
alongside duplicate removal.

Goal: keep the analysis running by handling incomplete rows with predefined
rules, instead of stopping because of individual rows.

## What counts as "missing"

A value is treated as missing when it is any of:

- a true null (`NaN` / `None`)
- an empty string `""`
- whitespace only, e.g. `"   "`
- a common placeholder: `"N/A"`, `"NA"`, `"-"`, `"null"`, `"none"` (case-insensitive)

These are all normalized to a true missing value first, so the rules below
apply consistently.

## Per-field rules

Fields fall into three groups.

**Critical fields** — required to produce a valid KPI. If any is missing, the
row is **excluded** (removed and counted). A row without these can't contribute
to revenue or be placed in a time period, so it carries no usable information.

| Field              |
| ------------------ |
| `transaction_date` |
| `product_id`       |
| `quantity`         |
| `unit_price`       |

**Optional fields** — not required for KPIs. Missing values are **filled with a
default** so the row is kept.

| Field          | Default value     |
| -------------- | ----------------- |
| `product_name` | `"Unknown"`       |
| `category`     | `"Uncategorized"` |

**Flagged fields** — kept as-is when missing (never filled, never excludes the
row), but counted so downstream KPIs and the data-quality summary can see the
gap.

| Field      | Behaviour                                             |
| ---------- | ---------------------------------------------------- |
| `order_id` | left blank, row kept, count of blanks reported       |

### Why `order_id` is flagged, not critical or optional

- **Not critical:** a line item with a blank `order_id` still has a valid date,
  product, quantity, and price, so it still contributes to revenue, product, and
  time-based KPIs. Excluding it would understate those numbers.
- **Not filled:** giving blank rows a placeholder `order_id` would merge them all
  into one fake order and corrupt order-level KPIs (order count, average order
  value).
- **So it is kept and counted.** Order-level KPIs compute on the rows that do
  have an `order_id` and treat the field as unavailable/partial when too many are
  missing — handled at the KPI layer, not here.

If the `order_id` column is missing from the upload entirely, that is handled
upstream (column mapping + required-field validation), and the order-level KPIs
are marked "Unavailable." This step only deals with a present column that has
some blank values.

## Scope

This step handles **missing/empty values only**. Invalid values (e.g. negative
quantity, zero price, unparseable dates) are a separate concern and are not
handled here.

## Output

Returns the cleaned DataFrame plus counts, for the data-quality summary:

- rows checked
- values filled (in optional fields)
- rows excluded (missing a critical field)
- rows kept
- flagged missing (per flagged field, e.g. `order_id`)
