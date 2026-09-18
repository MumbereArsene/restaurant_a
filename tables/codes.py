"""Short public codes for tables and invoices (human-typed, not UUID)."""

from __future__ import annotations

import secrets

# Avoid 0/O, 1/I/L
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def normalize_code(raw: str) -> str:
    """Uppercase, strip separators, drop ambiguous/invalid characters."""
    text = (raw or "").upper().replace(" ", "").replace("-", "")
    return "".join(c for c in text if c in CODE_ALPHABET)


def generate_unique_code(*, is_taken, length: int = CODE_LENGTH, attempts: int = 64) -> str:
    for _ in range(attempts):
        code = generate_code(length)
        if not is_taken(code):
            return code
    raise RuntimeError("Impossible de générer un code unique.")


def extract_raw_code(raw: str) -> str:
    text = (raw or "").strip()
    if "/order/" in text:
        text = text.rstrip("/").split("/order/")[-1].split("/")[0].split("?")[0]
    if "/facture/" in text:
        text = text.split("/facture/")[-1].split("/")[0].split("?")[0]
    return text.strip()


def resolve_table(raw: str):
    from .models import Table

    text = extract_raw_code(raw)
    code = normalize_code(text)
    if len(code) >= CODE_LENGTH:
        table = Table.objects.filter(public_code=code).first()
        if table:
            return table
    if text:
        return Table.objects.filter(qr_token=text).first()
    return None


def resolve_order_by_code(raw: str):
    from orders.models import Order

    text = extract_raw_code(raw)
    code = normalize_code(text)
    if len(code) >= CODE_LENGTH:
        order = (
            Order.objects.select_related("table", "customer")
            .prefetch_related("items__dish")
            .filter(invoice_code=code)
            .first()
        )
        if order:
            return order
    if text:
        return (
            Order.objects.select_related("table", "customer")
            .prefetch_related("items__dish")
            .filter(invoice_token=text)
            .first()
        )
    return None
