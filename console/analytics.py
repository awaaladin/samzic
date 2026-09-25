"""Order and revenue reporting for the console.

Everything is computed in the database with ``GROUP BY`` on a truncated date, then
padded in Python so a quiet day shows as ``0`` on the chart instead of being
missing. Nothing here writes; the views turn these dicts into pages, charts and
CSV.

Filters come straight from the query string (``period``, ``range``, ``start``,
``end``, ``chart`` plus page-specific ones) and are validated here, so a mangled
URL falls back to a sensible default rather than erroring.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import (
    Coalesce,
    ExtractHour,
    ExtractWeekDay,
    TruncDay,
    TruncMonth,
    TruncYear,
)
from django.utils import timezone

from orders.models import Order, OrderItem

PERIOD_CHOICES = [("day", "Daily"), ("month", "Monthly"), ("year", "Yearly")]
RANGE_CHOICES = [
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("90d", "Last 90 days"),
    ("12m", "Last 12 months"),
    ("ytd", "This year"),
    ("all", "All time"),
    ("custom", "Custom dates"),
]
CHART_CHOICES = [
    ("bar", "Bar chart"),
    ("line", "Line chart"),
    ("smooth", "Smooth curve"),
    ("doughnut", "Doughnut"),
    ("numbers", "Numbers only"),
]

# The period a range reads best in, used when the URL does not say.
DEFAULT_PERIOD_FOR_RANGE = {
    "7d": "day", "30d": "day", "90d": "day",
    "12m": "month", "ytd": "month", "all": "month", "custom": "day",
}
# Beyond this many days a daily chart is unreadable, so it is grouped by month.
MAX_DAILY_SPAN = 366

ZERO = Decimal("0")
MONEY = DecimalField(max_digits=14, decimal_places=2)
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]  # ExtractWeekDay: 1 = Sunday


# --- filters ---------------------------------------------------------------

def _valid(value, choices, default):
    return value if value in {c[0] for c in choices} else default


def _parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_filters(params):
    """Validated period / range / dates / chart from a QueryDict."""
    range_key = _valid(params.get("range"), RANGE_CHOICES, "30d")
    start, end = _parse_date(params.get("start")), _parse_date(params.get("end"))
    if range_key == "custom" and not (start and end):
        range_key = "30d"  # a custom range needs both ends
    period = params.get("period")
    if period not in {c[0] for c in PERIOD_CHOICES}:
        period = DEFAULT_PERIOD_FOR_RANGE[range_key]

    return {
        "range": range_key,
        "period": period,
        "chart": _valid(params.get("chart"), CHART_CHOICES, "bar"),
        "start": start,
        "end": end,
    }


def resolve_window(filters, earliest=None):
    """(start, end, effective_period, note) — inclusive local dates."""
    today = timezone.localdate()
    key = filters["range"]

    if key == "custom":
        start, end = sorted((filters["start"], filters["end"]))
    elif key == "7d":
        start, end = today - timedelta(days=6), today
    elif key == "30d":
        start, end = today - timedelta(days=29), today
    elif key == "90d":
        start, end = today - timedelta(days=89), today
    elif key == "12m":
        start, end = _month_start(_add_months(today, -11)), today
    elif key == "ytd":
        start, end = date(today.year, 1, 1), today
    else:  # all
        start, end = earliest or today, today

    end = min(end, today) if key != "custom" else end
    start = min(start, end)

    period, note = filters["period"], ""
    if period == "day" and (end - start).days + 1 > MAX_DAILY_SPAN:
        period, note = "month", "Grouped by month because a daily view of more than a year is unreadable."
    return start, end, period, note


def previous_window(start, end):
    """The window of equal length immediately before this one, for comparisons."""
    days = (end - start).days + 1
    return start - timedelta(days=days), start - timedelta(days=1)


# --- buckets ---------------------------------------------------------------

def _month_start(d):
    return d.replace(day=1)


def _add_months(d, months):
    index = d.year * 12 + (d.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


def bucket_starts(period, start, end):
    """Every bucket start date between start and end, so gaps show as zero."""
    out = []
    if period == "day":
        d = start
        while d <= end:
            out.append(d)
            d += timedelta(days=1)
    elif period == "month":
        d = _month_start(start)
        while d <= end:
            out.append(d)
            d = _add_months(d, 1)
    else:
        for year in range(start.year, end.year + 1):
            out.append(date(year, 1, 1))
    return out


def bucket_label(period, d):
    if period == "day":
        return f"{d.day} {d.strftime('%b')}" if d.year == timezone.localdate().year else d.strftime("%d %b %Y")
    if period == "month":
        return d.strftime("%b %Y")
    return str(d.year)


_TRUNC = {"day": TruncDay, "month": TruncMonth, "year": TruncYear}


def _as_date(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    return value


def grouped(queryset, field, period, **aggregates):
    """{bucket start date: {aggregate name: value}} for a queryset."""
    rows = (
        queryset.annotate(bucket=_TRUNC[period](field))
        .values("bucket")
        .annotate(**aggregates)
        .order_by("bucket")
    )
    return {_as_date(row["bucket"]): row for row in rows}


# --- orders ---------------------------------------------------------------

def filter_orders(params):
    """(queryset, applied filters) for the order insights page."""
    qs = Order.objects.all()
    applied = {}
    status = params.get("status", "")
    if status in {c[0] for c in Order.Status.choices}:
        qs, applied["status"] = qs.filter(status=status), status
    pay = params.get("payment_status", "")
    if pay in {c[0] for c in Order.PaymentStatus.choices}:
        qs, applied["payment_status"] = qs.filter(payment_status=pay), pay
    return qs, applied


def order_insights(params):
    filters = parse_filters(params)
    base, applied = filter_orders(params)

    earliest = base.order_by("created_at").values_list("created_at", flat=True).first()
    start, end, period, note = resolve_window(filters, _as_date(earliest) if earliest else None)
    window = base.filter(created_at__date__gte=start, created_at__date__lte=end)

    per_bucket = grouped(
        window, "created_at", period,
        n=Count("id"),
        value=Coalesce(Sum("total_price"), ZERO, output_field=MONEY),
        delivered=Count("id", filter=Q(status=Order.Status.DELIVERED)),
        cancelled=Count("id", filter=Q(status=Order.Status.CANCELLED)),
    )
    starts = bucket_starts(period, start, end)
    rows = []
    for d in starts:
        row = per_bucket.get(d, {})
        n = row.get("n", 0)
        value = row.get("value", ZERO)
        rows.append({
            "label": bucket_label(period, d),
            "orders": n,
            "delivered": row.get("delivered", 0),
            "cancelled": row.get("cancelled", 0),
            "value": value,
            "average": (value / n) if n else ZERO,
        })

    totals = window.aggregate(
        n=Count("id"),
        value=Coalesce(Sum("total_price"), ZERO, output_field=MONEY),
    )
    n, value = totals["n"], totals["value"]
    by_status = {
        row["status"]: row["n"]
        for row in window.values("status").annotate(n=Count("id"))
    }
    by_payment = {
        row["payment_status"]: row["n"]
        for row in window.values("payment_status").annotate(n=Count("id"))
    }

    prev_start, prev_end = previous_window(start, end)
    prev_n = base.filter(created_at__date__gte=prev_start, created_at__date__lte=prev_end).count()

    lines = OrderItem.objects.filter(order__in=window)
    items_sold = lines.aggregate(q=Coalesce(Sum("quantity"), 0))["q"]
    top_dishes = list(
        lines.values("name")
        .annotate(
            qty=Sum("quantity"),
            revenue=Sum(F("price") * F("quantity"), output_field=MONEY),
        )
        .order_by("-qty", "name")[:10]
    )

    hours = [0] * 24
    for row in window.annotate(h=ExtractHour("created_at")).values("h").annotate(c=Count("id")):
        hours[int(row["h"])] = row["c"]
    weekdays = [0] * 7
    for row in window.annotate(w=ExtractWeekDay("created_at")).values("w").annotate(c=Count("id")):
        weekdays[int(row["w"]) - 1] = row["c"]

    status_labels = dict(Order.Status.choices)
    status_rows = _with_pct(
        [
            {"key": key, "label": label, "count": by_status.get(key, 0)}
            for key, label in Order.Status.choices
        ],
        of_total=True,
    )

    # What the chart draws. A doughnut is a share-of-total, so it shows status mix.
    labels = [r["label"] for r in rows]
    if filters["chart"] == "doughnut":
        chart = {
            "labels": [s["label"] for s in status_rows],
            "datasets": [{"label": "Orders", "data": [s["count"] for s in status_rows]}],
            "money": False,
            "share": True,
        }
    else:
        chart = {
            "labels": labels,
            "datasets": [
                {"label": "Orders", "data": [r["orders"] for r in rows], "color": "#C21807"},
            ],
            "money": False,
            "share": False,
        }

    return {
        "kind": "orders",
        "filters": filters,
        "applied": applied,
        "period": period,
        "period_note": note,
        "start": start,
        "end": end,
        "prev_start": prev_start,
        "prev_end": prev_end,
        "kpis": {
            "orders": n,
            "value": value,
            "average": (value / n) if n else ZERO,
            "items_sold": items_sold,
            "delivered": by_status.get(Order.Status.DELIVERED, 0),
            "cancelled": by_status.get(Order.Status.CANCELLED, 0),
            "pending": by_status.get(Order.Status.PENDING, 0),
            "unpaid": by_payment.get(Order.PaymentStatus.UNPAID, 0),
            "change": _pct_change(n, prev_n),
            "previous": prev_n,
        },
        "rows": rows,
        "chart": chart,
        "status_rows": status_rows,
        "top_dishes": top_dishes,
        "busiest": {
            "hours": _with_pct([{"label": f"{h:02d}:00", "count": c} for h, c in enumerate(hours)]),
            "weekdays": _with_pct([{"label": WEEKDAYS[i], "count": c} for i, c in enumerate(weekdays)]),
        },
        "status_labels": status_labels,
    }


# --- revenue ---------------------------------------------------------------

REVENUE_VIEWS = [
    ("collected", "Collected (paid)"),
    ("outstanding", "Outstanding (unpaid)"),
    ("refunded", "Refunded"),
    ("all", "Everything"),
]


def revenue_queryset(params):
    """Orders annotated with the date their money counts on.

    Paid and refunded orders count on the day they were paid; unpaid ones on the day
    they were placed. Cancelled orders never count as outstanding — that money is
    not owed.
    """
    qs = Order.objects.annotate(money_date=Coalesce("paid_at", "created_at"))
    applied = {}
    method = params.get("payment_method", "")
    if method in {c[0] for c in Order.PaymentMethod.choices}:
        qs, applied["payment_method"] = qs.filter(payment_method=method), method
    view = params.get("view", "collected")
    if view not in {c[0] for c in REVENUE_VIEWS}:
        view = "collected"
    applied["view"] = view
    return qs, applied


def _money_sum(field="total_price", **cond):
    return Coalesce(Sum(field, filter=Q(**cond) if cond else None), ZERO, output_field=MONEY)


def revenue_insights(params):
    filters = parse_filters(params)
    base, applied = revenue_queryset(params)
    view = applied["view"]

    earliest = base.order_by("money_date").values_list("money_date", flat=True).first()
    start, end, period, note = resolve_window(filters, _as_date(earliest) if earliest else None)
    window = base.filter(money_date__date__gte=start, money_date__date__lte=end)

    paid = Q(payment_status=Order.PaymentStatus.PAID)
    unpaid = Q(payment_status=Order.PaymentStatus.UNPAID) & ~Q(status=Order.Status.CANCELLED)
    refunded = Q(payment_status=Order.PaymentStatus.REFUNDED)

    per_bucket = grouped(
        window, "money_date", period,
        collected=Coalesce(Sum("total_price", filter=paid), ZERO, output_field=MONEY),
        outstanding=Coalesce(Sum("total_price", filter=unpaid), ZERO, output_field=MONEY),
        refunded=Coalesce(Sum("total_price", filter=refunded), ZERO, output_field=MONEY),
        paid_orders=Count("id", filter=paid),
    )
    starts = bucket_starts(period, start, end)
    rows = []
    for d in starts:
        row = per_bucket.get(d, {})
        count = row.get("paid_orders", 0)
        collected = row.get("collected", ZERO)
        rows.append({
            "label": bucket_label(period, d),
            "collected": collected,
            "outstanding": row.get("outstanding", ZERO),
            "refunded": row.get("refunded", ZERO),
            "paid_orders": count,
            "average": (collected / count) if count else ZERO,
        })

    totals = window.aggregate(
        collected=Coalesce(Sum("total_price", filter=paid), ZERO, output_field=MONEY),
        food=Coalesce(Sum("subtotal", filter=paid), ZERO, output_field=MONEY),
        delivery=Coalesce(Sum("delivery_fee", filter=paid), ZERO, output_field=MONEY),
        outstanding=Coalesce(Sum("total_price", filter=unpaid), ZERO, output_field=MONEY),
        refunded=Coalesce(Sum("total_price", filter=refunded), ZERO, output_field=MONEY),
        paid_orders=Count("id", filter=paid),
        unpaid_orders=Count("id", filter=unpaid),
    )
    collected, paid_orders = totals["collected"], totals["paid_orders"]

    prev_start, prev_end = previous_window(start, end)
    prev_collected = base.filter(
        money_date__date__gte=prev_start, money_date__date__lte=prev_end
    ).aggregate(
        c=Coalesce(Sum("total_price", filter=paid), ZERO, output_field=MONEY)
    )["c"]

    by_method = []
    labels_by_method = dict(Order.PaymentMethod.choices)
    for row in (
        window.filter(paid).values("payment_method")
        .annotate(total=Sum("total_price"), n=Count("id")).order_by("-total")
    ):
        by_method.append({
            "label": labels_by_method.get(row["payment_method"], row["payment_method"]),
            "total": row["total"] or ZERO,
            "orders": row["n"],
            "share": (row["total"] / collected * 100) if collected else ZERO,
        })

    # Which lines the chart draws follows the "view" filter.
    series = {
        "collected": ("Collected", "collected", "#0F766E"),
        "outstanding": ("Outstanding", "outstanding", "#D97706"),
        "refunded": ("Refunded", "refunded", "#C21807"),
    }
    wanted = list(series) if view == "all" else [view]
    labels = [r["label"] for r in rows]
    if filters["chart"] == "doughnut":
        if view == "all":
            chart = {
                "labels": ["Collected", "Outstanding", "Refunded"],
                "datasets": [{"label": "Amount", "data": [
                    float(totals["collected"]), float(totals["outstanding"]), float(totals["refunded"]),
                ]}],
                "money": True, "share": True,
            }
        else:
            chart = {
                "labels": [m["label"] for m in by_method] or ["No data"],
                "datasets": [{"label": "Collected", "data": [float(m["total"]) for m in by_method] or [0]}],
                "money": True, "share": True,
            }
    else:
        chart = {
            "labels": labels,
            "datasets": [
                {"label": series[k][0], "data": [float(r[series[k][1]]) for r in rows], "color": series[k][2]}
                for k in wanted
            ],
            "money": True,
            "share": False,
        }

    # The money itself, newest first, for the transactions table / CSV.
    if view == "collected":
        ledger = window.filter(paid)
    elif view == "outstanding":
        ledger = window.filter(unpaid)
    elif view == "refunded":
        ledger = window.filter(refunded)
    else:
        ledger = window

    return {
        "kind": "revenue",
        "filters": filters,
        "applied": applied,
        "view": view,
        "period": period,
        "period_note": note,
        "start": start,
        "end": end,
        "prev_start": prev_start,
        "prev_end": prev_end,
        "kpis": {
            "collected": collected,
            "food": totals["food"],
            "delivery": totals["delivery"],
            "outstanding": totals["outstanding"],
            "refunded": totals["refunded"],
            "paid_orders": paid_orders,
            "unpaid_orders": totals["unpaid_orders"],
            "average": (collected / paid_orders) if paid_orders else ZERO,
            "change": _pct_change(collected, prev_collected),
            "previous": prev_collected,
        },
        "rows": rows,
        "chart": chart,
        "by_method": by_method,
        "ledger": ledger.select_related("user").order_by("-money_date", "-id"),
    }


def _with_pct(rows, of_total=False):
    """Add ``pct`` (0-100) to each row for CSS bars: relative to the biggest row, or
    to the sum of all rows when ``of_total``."""
    basis = sum(r["count"] for r in rows) if of_total else max((r["count"] for r in rows), default=0)
    for r in rows:
        r["pct"] = round(r["count"] / basis * 100) if basis else 0
    return rows


def _pct_change(current, previous):
    """Percentage change vs the previous window; None when there is nothing to compare to."""
    if not previous:
        return None
    return round(float((current - previous) / previous * 100), 1)
