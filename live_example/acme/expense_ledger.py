"""Explicit, additive fictional cash-expense ledger for the modern Acme cases.

The verified 2010-11 baseline and its schema hash remain immutable. This
extension is installed deliberately into a prepared exercise database; it is
never inferred from supplier order quantities or public retail transactions.
"""

from pathlib import Path

from acme.dataset import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS company_expenses (
 id TEXT PRIMARY KEY,
 paid_on TEXT NOT NULL CHECK(paid_on BETWEEN '2026-01-01' AND '2026-12-31'),
 category TEXT NOT NULL CHECK(category IN
  ('supplier_payment','logistics','packaging','marketing','software')),
 payee TEXT NOT NULL,
 amount_pence INTEGER NOT NULL CHECK(amount_pence > 0),
 currency TEXT NOT NULL CHECK(currency='GBP'),
 supplier_id TEXT REFERENCES suppliers(id),
 purchase_order_id TEXT REFERENCES purchase_orders(id),
 description TEXT NOT NULL,
 provenance TEXT NOT NULL CHECK(provenance='fictional_contemporary_expense'),
 CHECK(purchase_order_id IS NULL OR supplier_id IS NOT NULL)
) STRICT;
CREATE INDEX IF NOT EXISTS expense_paid_on ON company_expenses(paid_on);
CREATE INDEX IF NOT EXISTS expense_purchase_order ON company_expenses(purchase_order_id);
CREATE TRIGGER IF NOT EXISTS expense_supplier_matches_order_insert
BEFORE INSERT ON company_expenses
WHEN NEW.purchase_order_id IS NOT NULL AND EXISTS
 (SELECT 1 FROM purchase_orders WHERE id=NEW.purchase_order_id)
 AND NEW.supplier_id !=
 (SELECT supplier_id FROM purchase_orders WHERE id=NEW.purchase_order_id)
BEGIN SELECT RAISE(ABORT, 'expense supplier must match purchase order'); END;
CREATE TRIGGER IF NOT EXISTS expense_supplier_matches_order_update
BEFORE UPDATE OF supplier_id,purchase_order_id ON company_expenses
WHEN NEW.purchase_order_id IS NOT NULL AND EXISTS
 (SELECT 1 FROM purchase_orders WHERE id=NEW.purchase_order_id)
 AND NEW.supplier_id !=
 (SELECT supplier_id FROM purchase_orders WHERE id=NEW.purchase_order_id)
BEGIN SELECT RAISE(ABORT, 'expense supplier must match purchase order'); END;
CREATE TRIGGER IF NOT EXISTS purchase_supplier_matches_expenses
BEFORE UPDATE OF supplier_id ON purchase_orders
WHEN EXISTS (SELECT 1 FROM company_expenses
 WHERE purchase_order_id=OLD.id AND supplier_id!=NEW.supplier_id)
BEGIN SELECT RAISE(ABORT, 'purchase order supplier has linked expenses'); END;
"""

# Authored cash payments for the 2026 demonstration, never observed source costs.
# A payment linked to a purchase order does not prove that order is fully paid.
SEED_ROWS = (
    ("SCN-EXP-2026-01-MKT", "2026-01-19", "marketing", "Northline Local Media",
     4500, None, None, "Catalog launch promotion for the fictional 2026 account cohort"),
    ("SCN-EXP-2026-03-PACK", "2026-03-18", "packaging", "Parcelcraft Supplies",
     2250, None, None, "Packaging purchased for contemporary sample dispatches"),
    ("SCN-EXP-2026-04-SUP", "2026-04-15", "supplier_payment", "Weave Home Textiles Ltd",
     8500, "SUP-06", "SCN-PO-E82C3F1A2789",
     "Authored supplier settlement for the completed replenishment"),
    ("SCN-EXP-2026-05-LOG", "2026-05-20", "logistics", "Northline Parcel Service",
     3800, None, None, "Outbound carrier charge for contemporary demo orders"),
    ("SCN-EXP-2026-06-SW", "2026-06-17", "software", "Deskflow Tools",
     1900, None, None, "Fictional monthly order desk software payment"),
    ("SCN-EXP-2026-07-PACK", "2026-07-21", "packaging", "Parcelcraft Supplies",
     2800, None, None, "Additional cartons for authored July orders"),
    ("SCN-EXP-2026-08-MKT", "2026-08-19", "marketing", "Northline Local Media",
     5200, None, None, "Fictional autumn catalog campaign"),
    ("SCN-EXP-2026-09-LOG", "2026-09-18", "logistics", "Northline Parcel Service",
     4300, None, None, "Carrier charge for authored September shipments"),
    ("SCN-EXP-2026-10-DEPOSIT", "2026-10-02", "supplier_payment",
     "Ledger Paper & Office Ltd", 3000, "SUP-04", "SCN-PO-79511D9988BA",
     "Deposit on an open supplier order; remaining supplier balance is not modeled"),
    ("SCN-EXP-2026-10-SUP", "2026-10-21", "supplier_payment",
     "Solstice Seasonal Goods Ltd", 6200, "SUP-03", "SCN-PO-SPLIT-75F3A546B17E",
     "Authored payment after the final goods receipt; no supplier invoice ledger exists"),
    ("SCN-EXP-2026-10-SW", "2026-10-21", "software", "Deskflow Tools",
     1900, None, None, "Fictional October order desk software payment"),
)


def has_expense_ledger(db) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='company_expenses'"
    ).fetchone() is not None


def ensure_expense_schema(database: Path) -> None:
    db = connect(database)
    try:
        db.executescript(SCHEMA)
    finally:
        db.close()


def seed_expenses(state: Path) -> dict:
    """Install fixed 2026 entries once, preserving later manual edits."""
    database = state / "company.sqlite"
    db = connect(database)
    try:
        expected = {row[6] for row in SEED_ROWS if row[6] is not None}
        existing = {
            row[0] for row in db.execute(
                "SELECT id FROM purchase_orders WHERE id IN ("
                + ",".join("?" for _ in expected) + ")", tuple(sorted(expected))
            )
        }
        if existing != expected:
            raise ValueError("Install the authored 2026 purchase-order history first")
        db.executescript(SCHEMA)
        before = db.execute("SELECT COUNT(*) FROM company_expenses").fetchone()[0]
        db.executemany(
            "INSERT OR IGNORE INTO company_expenses VALUES(?,?,?,?,?,?,?,?,?,?)",
            [(*row[:5], "GBP", *row[5:], "fictional_contemporary_expense") for row in SEED_ROWS],
        )
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Expense ledger has broken links")
        db.commit()
        after = db.execute("SELECT COUNT(*) FROM company_expenses").fetchone()[0]
        return {"installed": after - before, "rows": after, "seed_rows": len(SEED_ROWS)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
