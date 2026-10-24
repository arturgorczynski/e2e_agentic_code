"""Predefined CSV analysis only: no eval, generated code, imports or shell execution."""

import csv
import io
from decimal import Decimal, InvalidOperation, localcontext

MAX_INPUT = 5 * 1024 * 1024
MAX_OUTPUT = 1024 * 1024
MAX_ROWS = 50000


def analyze_csv(content, operation, value_column, group_column=None):
    # 50,000 values of magnitude <= 1e12 with 12 decimal places need up to 29
    # significant digits. The standard 28-digit context would silently round totals.
    with localcontext() as arithmetic:
        arithmetic.prec = 50
        return _analyze_csv(content, operation, value_column, group_column)


def _analyze_csv(content, operation, value_column, group_column):
    if len(content) > MAX_INPUT:
        raise ValueError("CSV exceeds the 5 MiB input limit")
    if operation not in {"numeric_summary", "group_sum"}:
        raise ValueError("Choose numeric_summary or group_sum")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Use a UTF-8 comma-separated CSV file") from exc
    csv.field_size_limit(10000)
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    headers = reader.fieldnames
    if not headers or len(headers) > 32 or len(set(headers)) != len(headers):
        raise ValueError("CSV needs 1–32 unique column names")
    if any(not name or len(name) > 100 for name in headers):
        raise ValueError("Column names must contain 1–100 characters")
    if value_column not in headers or (operation == "group_sum" and group_column not in headers):
        raise ValueError("Selected column is absent from the CSV header")
    groups = {}
    count = 0
    total = Decimal(0)
    smallest = largest = None
    try:
        for row in reader:
            count += 1
            if count > MAX_ROWS:
                raise ValueError("CSV exceeds 50,000 data rows")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Row {count + 1} does not match the header")
            raw = row[value_column].strip()
            if len(raw) > 40:
                raise ValueError(f"Numeric value too long on row {count + 1}")
            value = Decimal(raw)
            if (
                not value.is_finite()
                or abs(value) > Decimal("1e12")
                or value.as_tuple().exponent < -12
            ):
                raise ValueError(f"Invalid finite decimal on row {count + 1}")
            total += value
            smallest = value if smallest is None else min(smallest, value)
            largest = value if largest is None else max(largest, value)
            if operation == "group_sum":
                key = row[group_column]
                if len(key) > 200:
                    raise ValueError("Group labels are limited to 200 characters")
                groups[key] = groups.get(key, Decimal(0)) + value
                if len(groups) > 200:
                    raise ValueError("Use a grouping with at most 200 distinct values")
    except (csv.Error, InvalidOperation) as exc:
        raise ValueError(f"Malformed CSV or numeric value near row {count + 1}") from exc
    if not count:
        raise ValueError("CSV has no data rows")
    return {
        "operation": operation,
        "value_column": value_column,
        "group_column": group_column,
        "rows": count,
        "total": str(total),
        "minimum": str(smallest),
        "maximum": str(largest),
        "mean": str(total / count),
        "groups": [{"group": key, "sum": str(value)} for key, value in sorted(groups.items())],
        "units": "Same units as the input column; no implicit currency conversion",
        "precision": "Exact bounded sums; division rounded to 50 significant digits",
    }


def render_report(result):
    lines = [
        "# CSV analysis",
        "",
        f"Operation: {result['operation']}",
        f"Value column: {result['value_column']}",
        f"Rows analyzed: {result['rows']}",
        "",
        f"Total: {result['total']}",
        f"Minimum: {result['minimum']}",
        f"Maximum: {result['maximum']}",
        f"Mean: {result['mean']}",
        "",
        result["units"],
    ]
    if result["groups"]:
        lines.extend(["", "| Group | Sum |", "| --- | ---: |"])
        for row in result["groups"]:
            label = row["group"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {label} | {row['sum']} |")
    return "\n".join(lines) + "\n"
