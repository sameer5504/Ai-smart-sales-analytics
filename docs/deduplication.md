# Duplicate Removal

Part of **Business Data Management**, the cleaning stage of the processing
pipeline. Operates on the standardized product line-item DataFrame (one row per
product per order).

## Definition of an exact duplicate row

A row is an **exact duplicate** when **every** value in it is identical to a row
that appeared earlier in the DataFrame, compared across the full standardized
schema:

| Column             | Notes                                     |
| ------------------ | ----------------------------------------- |
| `transaction_date` | after date standardization                |
| `order_id`         |                                           |
| `product_id`       |                                           |
| `product_name`     |                                           |
| `quantity`         |                                           |
| `unit_price`       |                                           |
| `category`         | included when present                     |

Rules:

- **All columns must match.** Two rows differing in any single field are *not*
  duplicates (e.g. same order + product but different quantity is a legitimate
  separate line item, not a duplicate).
- **Deduplication runs after standardization**, so formatting differences
  (e.g. `"01/02/2026"` vs `"2026-02-01"`) are already normalized and don't cause
  real duplicates to be missed or fake ones to be flagged.
- **First occurrence is kept**, later identical rows are removed.
- **Missing values (NaN) are treated as equal to each other**, so two otherwise
  identical rows that both have an empty `category` are still duplicates.

This "all columns identical" rule is the safe default: it only removes rows that
carry zero new information, so no real sales data is lost.

## Usage

```python
from app.processing.deduplication import remove_exact_duplicates

result = remove_exact_duplicates(df)
result.dataframe          # cleaned DataFrame
result.duplicates_removed # how many rows were removed
print(result.summary())   # "Removed 3 duplicate row(s): 100 -> 97"
```
