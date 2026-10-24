# Recommendation Output Contract

The shape returned by `GET /api/recommendations` and consumed by the AI
assistant when it delivers findings in chat (US-5.8.2).

Backed by `Recommendation` and `RecommendationsResult` in
`backend/app/recommendations/contract.py`, which build on `Anomaly` in
`backend/app/anomaly/schemas.py`.

## Where the numbers come from

Recommendations are built in Python from the business's own rows. The
assistant receives a finished `RecommendationsResult` and phrases what it is
given, so every figure a user sees comes from this payload.

`expected_impact` is a structured object with a `confidence` label rather than
a sentence, so a projection is never presented as a measured fact.

## Endpoint

| Endpoint | Use |
| -------- | --- |
| `GET /api/recommendations?dataset_id=` | Findings and recommendations for a dataset that has already been uploaded and prepared. Requires an authenticated user. |

The dataset is addressed by its id, from `GET /api/datasets`, not by filename.
One display filename can have several uploads behind it, and the id is what
ties a request to a row the caller owns.

Returns `403` when the dataset belongs to someone else. The check happens
before anything is read, so a caller cannot reach another user's rows.

Returns `404` when the dataset has not been prepared, either because it was
never uploaded or because its required columns could not be identified.

Having nothing to recommend is not an error. It comes back `200` with
`"status": "unavailable"` and a `reason`, so there is always a response to
render.

## Response shape

```json
{
  "status": "available",
  "total_findings": 7,
  "suppressed_count": 3,
  "reason": null,
  "message": null,
  "generated_at": "2026-08-27T09:00:00+00:00",
  "recommendations": [
    {
      "id": "rec-p001-sharp-drop",
      "priority": 1,
      "action": "Check Coffee 250g for a stock gap or a price change, and restock to about 130 units for next month.",
      "rationale": "Coffee 250g is your largest product by revenue and it sold 65% below its usual weekly volume.",
      "restock_units": 130.0,
      "demand_source": "forecast",
      "finding": {
        "anomaly_type": "sharp_drop",
        "scope": "product",
        "severity": "critical",
        "product_id": "P001",
        "product_name": "Coffee 250g",
        "category": "beverages",
        "metric": "units_sold",
        "period_start": "2026-07-20",
        "period_end": "2026-07-26",
        "current_value": 42.0,
        "baseline_value": 120.0,
        "change_percent": -65.0,
        "message": "Coffee 250g sold 42 units this week, 65% below its four-week median of 120."
      },
      "evidence": {
        "metric": "units_sold",
        "current_value": 42.0,
        "baseline_value": 120.0,
        "change_percent": -65.0,
        "units_lost": 78.0,
        "revenue_at_risk": 3510.0,
        "revenue_share_percent": 22.4,
        "period_start": "2026-07-20",
        "period_end": "2026-07-26",
        "currency": "GBP"
      },
      "expected_impact": {
        "value": 3510.0,
        "currency": "GBP",
        "confidence": "projected",
        "basis": "if weekly sales return to the four-week median of 120 units",
        "unavailable_reason": null
      }
    }
  ]
}
```

## Result fields

| Field | Type | Notes |
| ----- | ---- | ----- |
| `status` | string | `"available"` or `"unavailable"` |
| `recommendations` | array | Ranked, most important first. Empty when unavailable. |
| `total_findings` | number | How many anomalies detection produced, before the cap |
| `suppressed_count` | number | How many the cap held back, so the assistant can offer the rest (US-4.3.6) |
| `reason` | string \| null | Machine code when unavailable, from the table below |
| `message` | string \| null | Human-readable explanation, safe to show the user |
| `generated_at` | string | ISO-8601 UTC timestamp |

## Recommendation fields

| Field | Type | Notes |
| ----- | ---- | ----- |
| `id` | string | Stable, so a follow-up question can name one recommendation (US-5.4.1) |
| `finding` | object | The `Anomaly` this answers, carried whole so the assistant can explain the trigger without a second lookup |
| `action` | string | What to do, one imperative sentence (US-4.3.1) |
| `rationale` | string | Why it follows from the finding. Quoted verbatim for US-5.4.1 |
| `evidence` | object | The figures behind it (US-4.3.2), rendered for US-5.4.2 |
| `expected_impact` | object | What acting is worth (US-4.3.3), rendered for US-5.4.3 |
| `priority` | number | 1 is most important. Set by ranking (US-4.3.6) |
| `restock_units` | number \| null | Suggested restock quantity, when the rule produced one |
| `demand_source` | string \| null | `forecast` or `trailing_sales`, which the estimate came from (US-4.3.5) |

## Impact

| Field | Type | Notes |
| ----- | ---- | ----- |
| `value` | number \| null | Monthly amount. `null` is legitimate; `unavailable_reason` then says why |
| `currency` | string \| null | Currency of `value` |
| `confidence` | string | `measured` (a fact from the data) or `projected` (an estimate) |
| `basis` | string | One plain sentence naming the assumption. The assistant quotes this rather than inventing a justification |
| `unavailable_reason` | string \| null | Why no value could be produced |

## Anomaly types

Three fields carry three separate facts and none repeats another: the type is
the shape of the change, the scope is who it happened to, the metric is what
was measured.

| `anomaly_type` | Scope | Metric | Story |
| -------------- | ----- | ------ | ----- |
| `sharp_drop` | product | `units_sold` | US-4.1.3 |
| `dead_stock` | product | `units_sold` | US-4.1.4 |
| `unusual_increase` | product | `units_sold` | US-4.1.5 |
| `sharp_drop` | store | `revenue` or `units_sold` | US-4.1.1, US-4.1.2 |
| `unusual_increase` | store | `revenue` or `units_sold` | US-4.1.1 |

Units and revenue move independently. Selling fewer items at a higher price
raises revenue while sales fall, so US-4.1.1 requires both to be watched and
they are reported as separate findings.

Because of that, one event can produce two findings for the same period, one
per metric. `Anomaly.dedupe_key` groups them, and ranking collapses them into
a single recommendation so the business owner is told once (US-4.3.6).

`dead_stock` is product-scoped only, enforced by a validator.

Severity is one of `critical`, `warning`, `info` (US-4.1.6). Sort on
`SEVERITY_RANK` rather than on the string value, which would order
alphabetically.

## Unavailable reasons

| `reason` | Meaning |
| -------- | ------- |
| `no_findings` | Detection ran and found nothing worth reporting. The normal quiet case. |
| `insufficient_history` | Not enough history to establish a baseline to compare against. |
| `detection_unavailable` | Detection could not run. A server-side problem, not a problem with the uploaded data. |

## Working against this before the engine exists

`backend/tests/fixtures/anomalies.py` and
`backend/tests/fixtures/recommendations.py` hold sample objects for every type
and severity, so the two halves of Epic 4 can be built in parallel:

- Engine work (US-4.3.x) imports `tests.fixtures.anomalies` and needs nothing
  from detection.
- Endpoint, chat grounding and dashboard work import
  `tests.fixtures.recommendations` and need nothing from the engine.

The fixture figures are arithmetically consistent, checked by a test in
`tests/anomaly/test_schemas.py`.

`expected_units` in `app/recommendations/demand.py` is a stub that raises
`NotImplementedError`. Rules take a `DemandEstimator` rather than importing it
directly, so they can be tested against a fake until US-4.3.5 lands.
