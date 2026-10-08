"""Every tab and every dialog of the application renders without an error.

Runs the real app.py headless with Streamlit's AppTest, on a temporary
database that holds an order at each stage.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import dates
from core.models import ItemKind, MaterialCategory, PackagingItemType, StepKind, StepRole
from data import actions, db
from data.actions import AssignmentInput, MachineInput, PackagingItemInput, StepSpec
from ui import texts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 10, 5)


def kg(value: int | str) -> int:
    return int(Decimal(str(value)) * 1_000_000)


def _seed(path: Path) -> dict[str, int]:
    """One order on the shelf with a pending shipment, one ready for production, one receipt."""
    conn = db.connect(db.init_db(path))
    m = lambda code, name, qty: actions.create_material(
        conn, code=code, name=name, category=MaterialCategory.EXCIPIENT, lot_number=f"L-{code}",
        lot_quantity_mg=kg(qty), lot_expiry=date(2027, 6, 30)).value
    api, excipient, film = m("A", "Δραστική", 500), m("B", "Έκδοχο", 500), m("F", "Φιλμ", 500)
    item = lambda code, name, pcs, **kw: actions.create_packaging_item(conn, PackagingItemInput(code, name, pcs, **kw)).value
    blister = item("P1", "Blister", 0, unit_weight_mg=5_000, components=((film, 10_000),))
    box = item("P2", "Κουτί", 50_000, length_mm=100, width_mm=60, height_mm=30)
    carton = item("P3", "Κιβώτιο", 500, length_mm=400, width_mm=300, height_mm=250,
                  outer_length_mm=410, outer_width_mm=310, outer_height_mm=260, item_type=PackagingItemType.CARTON)
    pallet = item("P4", "Παλέτα EUR", 100, outer_length_mm=1200, outer_width_mm=800, outer_height_mm=1500,
                  item_type=PackagingItemType.PALLET)
    label = item("L1", "Ετικέτα blister", 50_000, item_type=PackagingItemType.LABEL)
    product = actions.create_product(conn, name="Depon", unit_weight_mg=500, recipe=[(api, 5_000), (excipient, 5_000)]).value
    machine = actions.create_machine(conn, MachineInput("Μηχανή 1", kg(50), Decimal(120), 8_000, Decimal(8))).value
    steps = [
        StepSpec(StepKind.LEVEL, blister, StepRole.PRIMARY, 12, False, Decimal(200)),
        StepSpec(StepKind.LABELLING, label, None, None, False, Decimal(150)),
        StepSpec(StepKind.LEVEL, box, StepRole.BOX, 2, True),
        StepSpec(StepKind.LEVEL, carton, StepRole.CARTON, 160, True),
        StepSpec(StepKind.LEVEL, pallet, StepRole.PALLET, 20, True),
    ]

    def order(name: str) -> int:
        order_id = actions.create_order(conn, product_id=product, quantity_mg=kg(100), name=name,
                                        destination="Βουλγαρία", delivery_date=date(2026, 10, 26),
                                        transit_days=5).value
        actions.set_assignments(conn, order_id, [AssignmentInput(machine, kg(100), kg(50), Decimal(120), 300, TODAY)])
        actions.save_packaging_plan(conn, order_id, hours_per_day=Decimal(8), utilization_bp=8_500, steps=steps)
        return order_id

    shelved = order("ΠΑΡ-001")
    assignment = conn.execute("SELECT id FROM order_assignments WHERE order_id = ?", (shelved,)).fetchone()[0]
    actions.complete_assignment(conn, assignment, actual_pieces=190_000)
    actions.complete_packaging(conn, shelved)
    line = conn.execute("SELECT id FROM shelf_lines").fetchone()[0]
    shipment = actions.create_shipment(conn, shelf_line_id=line, boxes=100).value
    ready = order("ΠΑΡ-002")
    open_assignment = conn.execute("SELECT id FROM order_assignments WHERE order_id = ?", (ready,)).fetchone()[0]
    receipt = actions.create_receipt(conn, kind=ItemKind.MATERIAL, item_id=excipient, quantity=kg(50),
                                     receipt_date=date(2026, 10, 1)).value
    lot = conn.execute("SELECT id FROM material_lots WHERE material_id = ?", (api,)).fetchone()[0]
    conn.close()
    return {"material": api, "lot": lot, "item": box, "carton": carton, "pallet": pallet, "label": label, "product": product, "machine": machine, "line": line,
            "shipment": shipment, "order": ready, "shelved": shelved, "assignment": open_assignment,
            "receipt": receipt}


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dates, "today", lambda: TODAY)
    path = tmp_path / "app.db"
    ids = _seed(path)
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", path)
    monkeypatch.setattr(db, "BACKUPS_DIR", tmp_path / "backups")
    at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at, ids


@pytest.mark.parametrize("label", texts.NAV_LABELS)
def test_every_tab_renders(app, label: str) -> None:
    at, _ = app
    at.session_state["nav"] = label
    at.run()
    assert not at.exception, [e.value for e in at.exception]


DIALOGS = [
    ("material_form", {}), ("material_form", {"material_id": "material"}),
    ("lot_form", {"material_id": "material"}), ("lot_form", {"lot_id": "lot"}),
    ("packaging_form", {}), ("packaging_form", {"item_id": "item"}),
    ("container_form", {}), ("container_form", {"item_id": "carton"}), ("container_form", {"item_id": "pallet"}),
    ("label_form", {}), ("label_form", {"item_id": "label"}),
    ("transfer_form", {"line_id": "line"}),
    ("product_form", {}), ("product_form", {"product_id": "product"}),
    ("order_new", {}), ("order_edit", {"order_id": "order"}), ("order_sequence", {"order_id": "order"}),
    ("machine_form", {}), ("machine_form", {"machine_id": "machine"}),
    ("assign_form", {"order_id": "order"}), ("inverse_form", {"assignment_id": "assignment"}),
    ("complete_form", {"assignment_id": "assignment"}),
    ("plan_form", {"order_id": "order"}), ("packaging_complete", {"order_id": "order"}),
    ("receipt_form", {}), ("receipt_form", {"receipt_id": "receipt"}),
    ("receipt_received", {"receipt_id": "receipt"}),
    ("shipment_form", {}), ("shipment_form", {"shipment_id": "shipment"}),
    ("shipment_shipped", {"shipment_id": "shipment"}),
    ("undo", {}),
]


@pytest.mark.parametrize("name, params", DIALOGS, ids=[f"{n}-{'-'.join(p) or 'new'}" for n, p in DIALOGS])
def test_every_dialog_renders(app, name: str, params: dict[str, str]) -> None:
    at, ids = app
    resolved = {key: ids[value] for key, value in params.items()}
    at.session_state["open_dialog"] = {"name": name, "params": {**resolved, "_token": 1}}
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_confirm_dialog_runs_the_action(app) -> None:
    at, ids = app
    at.session_state["open_dialog"] = {"name": "confirm", "params": {
        "title": texts.T_CANCEL_ORDER, "message": texts.confirm_cancel("ΠΑΡ-002"),
        "func": actions.cancel_order, "args": (ids["order"],), "kwargs": {}, "_token": 2,
    }}
    at.run()
    assert not at.exception
    yes = next(b for b in at.button if b.label == texts.CONTINUE)
    yes.click().run()
    assert not at.exception
    assert texts.undo_label(texts.h_order_cancelled("ΠΑΡ-002")) in [c.value for c in at.caption]


def _text_value(at: AppTest, label: str) -> str:
    return next(t.value for t in at.text_input if t.label == label)


def test_settings_tab_shows_machine_hours(app) -> None:
    at, _ = app
    at.session_state["nav"] = texts.NAV_SETTINGS
    at.run()
    assert _text_value(at, texts.F_MACHINE_HOURS) == "8"


def test_new_machine_prefills_hours_from_settings(app) -> None:
    from core.models import Settings

    at, ids = app
    conn = db.connect(db.DEFAULT_DB_PATH)
    actions.update_settings(conn, Settings(machine_hours_per_day=Decimal("16")))
    conn.close()
    at.session_state["open_dialog"] = {"name": "machine_form", "params": {"_token": 3}}
    at.run()
    assert _text_value(at, texts.F_HOURS) == "16"
    at.session_state["open_dialog"] = {"name": "machine_form", "params": {"machine_id": ids["machine"], "_token": 4}}
    at.run()
    assert _text_value(at, texts.F_HOURS) == "8"


def test_plan_role_shows_packaging_container(app) -> None:
    at, ids = app
    at.session_state["open_dialog"] = {"name": "plan_form", "params": {"order_id": ids["order"], "_token": 5}}
    at.run()
    role_boxes = [s for s in at.selectbox if s.label == texts.F_ROLE]
    assert any(s.value == StepRole.BOX for s in role_boxes)
    assert texts.ROLE_BOX == "Δοχείο συσκευασίας"
    assert texts.ROLE_BOX in role_boxes[0].options


def test_wipe_takes_a_backup_then_clears_everything(app, tmp_path: Path) -> None:
    at, _ = app
    at.session_state["nav"] = texts.NAV_SETTINGS
    at.run()
    assert any(b.label == texts.ST_WIPE for b in at.button)
    at.session_state["open_dialog"] = {"name": "wipe_all", "params": {"_token": 6}}
    at.run()
    assert not at.exception
    next(b for b in at.button if b.label == texts.CONTINUE).click().run()
    assert not at.exception
    backups = list((tmp_path / "backups").glob("app_*.db"))
    assert len(backups) == 1
    saved = db.connect(backups[0])
    assert saved.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2
    saved.close()
    conn = db.connect(db.DEFAULT_DB_PATH)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0
    conn.close()
    assert texts.NOTHING_TO_UNDO in [c.value for c in at.caption]


def test_wipe_cancel_keeps_data(app) -> None:
    at, _ = app
    at.session_state["open_dialog"] = {"name": "wipe_all", "params": {"_token": 7}}
    at.run()
    next(b for b in at.button if b.label == texts.CANCEL).click().run()
    conn = db.connect(db.DEFAULT_DB_PATH)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2
    conn.close()


def test_every_order_status_has_a_label() -> None:
    from core.state import OrderStatus
    from ui import common

    assert set(common.ORDER_STATUS) == set(OrderStatus)
    assert common.ORDER_STATUS[OrderStatus.IN_PRODUCTION][0] == "Σε παραγωγή"


def _shelf_orders(at: AppTest) -> list[str]:
    """Order names in the warehouse shelf table ("Έτοιμα προϊόντα")."""
    for frame in at.dataframe:
        data = frame.value.data if hasattr(frame.value, "data") else frame.value
        if texts.COL_PIECES_PER_BOX in data.columns:
            return list(data[texts.COL_ORDER])
    return []


def test_shipped_line_leaves_the_shelf_and_undo_brings_it_back(app) -> None:
    from data import history

    at, ids = app
    at.session_state["nav"] = texts.NAV_WAREHOUSE
    at.run()
    assert "ΠΑΡ-001" in _shelf_orders(at)

    conn = db.connect(db.DEFAULT_DB_PATH)
    boxes = conn.execute("SELECT boxes FROM shelf_lines WHERE id = ?", (ids["line"],)).fetchone()[0]
    actions.update_shipment(conn, ids["shipment"], boxes=boxes)
    actions.mark_shipped(conn, ids["shipment"], boxes=boxes)
    at.run()
    assert "ΠΑΡ-001" not in _shelf_orders(at)

    history.undo_last(conn)
    conn.close()
    at.run()
    assert "ΠΑΡ-001" in _shelf_orders(at)



def test_plan_offers_only_matching_items_and_pallet_fits(app) -> None:
    at, ids = app
    at.session_state["open_dialog"] = {"name": "plan_form", "params": {"order_id": ids["order"], "_token": 8}}
    at.run()
    assert not at.exception
    by_label = {}
    for box in at.selectbox:
        by_label.setdefault(box.label, []).append(box)
    assert [b.value for b in by_label[texts.ITEM_FIELD_LABELS["label"]]] == [ids["label"]]
    assert [b.value for b in by_label[texts.ITEM_FIELD_LABELS["pallet"]]] == [ids["pallet"]]
    pallet_box = by_label[texts.ITEM_FIELD_LABELS["pallet"]][0]
    assert len(pallet_box.options) == 1
    radios = {r.label: r for r in at.radio}
    assert texts.F_FIT_PALLET in radios and texts.F_FIT in radios
    assert "20 κιβώτια" in radios[texts.F_FIT_PALLET].options[0]


def test_warehouse_lists_labels_separately(app) -> None:
    at, _ = app
    at.session_state["nav"] = texts.NAV_WAREHOUSE
    at.run()
    assert texts.WH_LABELS in [h.value for h in at.subheader]
    assert any(b.label == texts.WH_ADD_CONTAINER for b in at.button)
    assert any(b.label == texts.WH_ADD_LABEL for b in at.button)


def test_terms_kivotio_and_package(app) -> None:
    source = (PROJECT_ROOT / "ui" / "texts.py").read_text(encoding="utf-8")
    assert "χαρτοκιβ" not in source.lower()
    at, ids = app
    at.session_state["open_dialog"] = {"name": "plan_form", "params": {"order_id": ids["order"], "_token": 9}}
    at.run()
    kinds = [s for s in at.selectbox if s.label == texts.F_STEP_KIND]
    assert kinds and "Package" in kinds[0].options and "Labelling" in kinds[0].options
    roles = next(s for s in at.selectbox if s.label == texts.F_ROLE)
    assert "Κιβώτιο" in roles.options


def test_language_switch_keeps_the_tab_and_is_saved(app) -> None:
    at, _ = app
    at.session_state["nav"] = texts.NAV_PRODUCTS
    at.run()
    switch = at.segmented_control[0] if hasattr(at, "segmented_control") else None
    if switch is None:
        pytest.skip("AppTest has no segmented_control element in this Streamlit version")
    switch.set_value("en").run()
    assert not at.exception
    assert at.session_state["nav"] == "Products"
    assert any(b.label == "(+) Add Product" for b in at.button)
    assert "Supply chain planning" in [t.value for t in at.title]
    conn = db.connect(db.DEFAULT_DB_PATH)
    from data.repositories import get_language

    assert get_language(conn) == "en"
    assert conn.execute("SELECT COUNT(*) FROM history WHERE action_code = 'settings_update'").fetchone()[0] == 0
    conn.close()
    switch = at.segmented_control[0]
    switch.set_value("el").run()
    assert at.session_state["nav"] == "Προϊόντα"


@pytest.mark.parametrize("name, params", DIALOGS, ids=[f"en-{n}-{'-'.join(p) or 'new'}" for n, p in DIALOGS])
def test_every_dialog_renders_in_english(app, name: str, params: dict[str, str]) -> None:
    at, ids = app
    conn = db.connect(db.DEFAULT_DB_PATH)
    from data.repositories import set_language

    set_language(conn, "en")
    conn.close()
    resolved = {key: ids[value] for key, value in params.items()}
    at.session_state["open_dialog"] = {"name": name, "params": {**resolved, "_token": 1}}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
