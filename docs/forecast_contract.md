# Forecast Output Contract

The shape returned by the revenue forecast endpoints and consumed by the
dashboard and the forecast chart (US-3.3.1).

Backed by `ForecastResult` in `backend/app/forecast/contract.py`.

## Endpoints

| Endpoint | Use |
| -------- | --- |
| `GET /api/forecast/revenue?dataset_id=` | Forecast from one of the caller's own datasets, already uploaded and prepared. This is the one the dashboard calls. |
| `POST /api/forecast` | Forecast from sales records sent in the request body, for a caller that already holds the rows. |

Both take optional `region` and `country` (a query parameter on the GET, a body
field on the POST) to pick the holiday calendar; `country` wins when both are
given. Both return the response below.

`GET /api/forecast/revenue` returns `403` when the dataset does not belong to the
authenticated user, `404` when its file has not been prepared — either never
uploaded, or its required columns could not be identified — and `400` when the
prepared rows are missing a field the forecast needs.

The dataset is resolved against the caller, and the file is read from that user's
own storage, so a dataset id belonging to someone else is refused rather than
answered.

A forecast that cannot be produced is not an error. It comes back `200` with
`"status": "unavailable"` and a `reason`, so there is always a response to draw.

## Response shape

```json
{
  "status": "available",
  "target_month": "2026-03",
  "predicted_revenue": 15230.50,
  "currency": null,
  "model": "trained_revenue",
  "history": [
    { "month": "2026-01", "revenue": 14000.0 },
    { "month": "2026-02", "revenue": 14800.0 }
  ],
  "interval": null,
  "reason": null,
  "message": null,
  "generated_at": "2026-03-01T12:00:00+00:00"
}
```

`currency` and `interval` are part of the shape but are `null` on every response
the served model produces today: uploads carry no currency, and the trained model
returns a point forecast without an uncertainty range. They are specified so a
consumer can read them once a model or an account setting supplies them, and a
client should treat both as optional rather than assume they are present.

## Fields

| Field               | Type            | Notes |
| ------------------- | --------------- | ----- |
| `status`            | string          | `"available"` or `"unavailable"` |
| `target_month`      | string          | month being forecast, `"YYYY-MM"` |
| `predicted_revenue` | number \| null  | forecast total; `null` when unavailable |
| `currency`          | string \| null  | e.g. `"GBP"`; always `null` today, see above |
| `model`             | string \| null  | which model produced it: `automl_endpoint` (the AutoML endpoint, preferred when reachable) or `trained_revenue` (the artifact in this repository, used otherwise); `null` when unavailable |
| `history`           | array           | monthly series used, oldest→newest, each `{ month, revenue }`; used to draw the history line |
| `interval`          | object \| null  | optional uncertainty range `{ lower, upper }`; `null` from the served model, see above |
| `reason`            | string \| null  | machine code when unavailable, from the table below |
| `message`           | string \| null  | human-readable explanation, safe to show the user |
| `generated_at`      | string          | ISO-8601 UTC timestamp |

## Reasons

| `reason` | Meaning |
| -------- | ------- |
| `insufficient_history` | The data covers fewer than 3 complete months, or the last 28 days net to zero or less so there is no baseline to scale against. |
| `model_unavailable` | The trained model is not present on the server. A deployment problem, not a problem with the uploaded data. |

`history` is filled in on an unavailable response wherever the data allows it,
so the history line can still be drawn when the forecast itself is missing.

## Unavailable example

Returned when there isn't enough history to forecast:

```json
{
  "status": "unavailable",
  "target_month": "2026-03",
  "predicted_revenue": null,
  "currency": null,
  "model": null,
  "history": [ { "month": "2026-01", "revenue": 14000.0 } ],
  "interval": null,
  "reason": "insufficient_history",
  "message": "Need at least 3 complete months of sales history to forecast; found 1.",
  "generated_at": "2026-03-01T12:00:00+00:00"
}
```
