-- Initial schema: every table of specification section 3, plus default settings.
-- Only user input and the results of user actions are stored. Derived values
-- (available, reserved, shortages, statuses, dates) are never stored.
--
-- Units: mass in integer mg, percentages in integer basis points (100% = 10000),
-- dimensions in integer mm, dates as 'YYYY-MM-DD', timestamps as ISO text.
-- Cycle times, hours per day and speeds are text parsed as Decimal.
--
-- Foreign keys are DEFERRABLE INITIALLY DEFERRED so that a multi-row action or
-- an undo can restore rows in any order inside one transaction; integrity is
-- still checked at commit.

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE materials (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL
                CHECK (category IN ('raw_material', 'excipient', 'packaging_material')),
    description TEXT
);

CREATE TABLE material_lots (
    id          INTEGER PRIMARY KEY,
    material_id INTEGER NOT NULL
                REFERENCES materials(id) DEFERRABLE INITIALLY DEFERRED,
    lot_number  TEXT NOT NULL,
    quantity_mg INTEGER NOT NULL CHECK (quantity_mg >= 0),
    expiry_date TEXT NOT NULL
);
CREATE INDEX idx_material_lots_material ON material_lots(material_id);

CREATE TABLE packaging_items (
    id             INTEGER PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    description    TEXT,
    quantity_pcs   INTEGER NOT NULL DEFAULT 0 CHECK (quantity_pcs >= 0),
    length_mm      INTEGER CHECK (length_mm > 0),
    width_mm       INTEGER CHECK (width_mm > 0),
    height_mm      INTEGER CHECK (height_mm > 0),
    unit_weight_mg INTEGER CHECK (unit_weight_mg > 0),
    CHECK (
        (length_mm IS NULL AND width_mm IS NULL AND height_mm IS NULL)
        OR (length_mm IS NOT NULL AND width_mm IS NOT NULL AND height_mm IS NOT NULL)
    )
);

CREATE TABLE packaging_item_components (
    packaging_item_id INTEGER NOT NULL
                      REFERENCES packaging_items(id) DEFERRABLE INITIALLY DEFERRED,
    material_id       INTEGER NOT NULL
                      REFERENCES materials(id) DEFERRABLE INITIALLY DEFERRED,
    percent_bp        INTEGER NOT NULL CHECK (percent_bp > 0 AND percent_bp <= 10000),
    PRIMARY KEY (packaging_item_id, material_id)
);

CREATE TABLE products (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    unit_weight_mg INTEGER CHECK (unit_weight_mg > 0)
);

CREATE TABLE recipe_lines (
    product_id  INTEGER NOT NULL
                REFERENCES products(id) DEFERRABLE INITIALLY DEFERRED,
    material_id INTEGER NOT NULL
                REFERENCES materials(id) DEFERRABLE INITIALLY DEFERRED,
    percent_bp  INTEGER NOT NULL CHECK (percent_bp > 0 AND percent_bp <= 10000),
    PRIMARY KEY (product_id, material_id)
);

CREATE TABLE machines (
    id                 INTEGER PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,
    batch_size_mg      INTEGER NOT NULL CHECK (batch_size_mg > 0),
    cycle_time_min     TEXT NOT NULL,
    utilization_bp     INTEGER NOT NULL CHECK (utilization_bp BETWEEN 100 AND 10000),
    hours_per_day      TEXT NOT NULL,
    max_batch_mg       INTEGER CHECK (max_batch_mg > 0),
    min_cycle_time_min TEXT
);

CREATE TABLE orders (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    product_id     INTEGER NOT NULL
                   REFERENCES products(id) DEFERRABLE INITIALLY DEFERRED,
    quantity_mg    INTEGER NOT NULL CHECK (quantity_mg > 0),
    unit_weight_mg INTEGER CHECK (unit_weight_mg > 0),
    destination    TEXT NOT NULL,
    delivery_date  TEXT NOT NULL,
    transit_days   INTEGER NOT NULL CHECK (transit_days >= 0),
    sequence       INTEGER NOT NULL CHECK (sequence > 0),
    created_at     TEXT NOT NULL,
    cancelled_at   TEXT
);
CREATE INDEX idx_orders_product ON orders(product_id);

CREATE TABLE order_recipe_lines (
    order_id    INTEGER NOT NULL
                REFERENCES orders(id) DEFERRABLE INITIALLY DEFERRED,
    material_id INTEGER NOT NULL
                REFERENCES materials(id) DEFERRABLE INITIALLY DEFERRED,
    percent_bp  INTEGER NOT NULL CHECK (percent_bp > 0 AND percent_bp <= 10000),
    PRIMARY KEY (order_id, material_id)
);

CREATE TABLE order_assignments (
    id             INTEGER PRIMARY KEY,
    order_id       INTEGER NOT NULL
                   REFERENCES orders(id) DEFERRABLE INITIALLY DEFERRED,
    machine_id     INTEGER NOT NULL
                   REFERENCES machines(id) DEFERRABLE INITIALLY DEFERRED,
    quantity_mg    INTEGER NOT NULL CHECK (quantity_mg > 0),
    batch_size_mg  INTEGER NOT NULL CHECK (batch_size_mg > 0),
    cycle_time_min TEXT NOT NULL,
    defect_bp      INTEGER NOT NULL DEFAULT 0 CHECK (defect_bp BETWEEN 0 AND 10000),
    start_date     TEXT,
    completed_at   TEXT,
    actual_pieces  INTEGER CHECK (actual_pieces >= 0)
);
CREATE INDEX idx_order_assignments_order ON order_assignments(order_id);
CREATE INDEX idx_order_assignments_machine ON order_assignments(machine_id);

CREATE TABLE packaging_plans (
    order_id       INTEGER PRIMARY KEY
                   REFERENCES orders(id) DEFERRABLE INITIALLY DEFERRED,
    hours_per_day  TEXT NOT NULL,
    utilization_bp INTEGER NOT NULL CHECK (utilization_bp BETWEEN 100 AND 10000),
    saved_at       TEXT NOT NULL,
    completed_at   TEXT
);

-- A later migration can add a nullable packaging machine reference here
-- (specification section 14) without changing any other column.
CREATE TABLE packaging_steps (
    id                INTEGER PRIMARY KEY,
    order_id          INTEGER NOT NULL
                      REFERENCES packaging_plans(order_id) DEFERRABLE INITIALLY DEFERRED,
    position          INTEGER NOT NULL CHECK (position > 0),
    kind              TEXT NOT NULL CHECK (kind IN ('level', 'labelling')),
    role              TEXT CHECK (role IN ('primary', 'box', 'carton', 'other')),
    packaging_item_id INTEGER NOT NULL
                      REFERENCES packaging_items(id) DEFERRABLE INITIALLY DEFERRED,
    units_per         INTEGER CHECK (units_per > 0),
    comes_ready       INTEGER NOT NULL DEFAULT 0 CHECK (comes_ready IN (0, 1)),
    speed_per_min     TEXT,
    UNIQUE (order_id, position),
    CHECK (
        (kind = 'level' AND role IS NOT NULL AND units_per IS NOT NULL)
        OR (kind = 'labelling' AND role IS NULL AND units_per IS NULL)
    )
);

CREATE TABLE packaging_step_extras (
    step_id           INTEGER NOT NULL
                      REFERENCES packaging_steps(id) DEFERRABLE INITIALLY DEFERRED,
    packaging_item_id INTEGER NOT NULL
                      REFERENCES packaging_items(id) DEFERRABLE INITIALLY DEFERRED,
    quantity_per_unit INTEGER NOT NULL CHECK (quantity_per_unit > 0),
    PRIMARY KEY (step_id, packaging_item_id)
);

CREATE TABLE shelf_lines (
    id               INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL UNIQUE
                     REFERENCES orders(id) DEFERRABLE INITIALLY DEFERRED,
    boxes            INTEGER NOT NULL CHECK (boxes >= 0),
    pieces_per_box   INTEGER NOT NULL CHECK (pieces_per_box > 0),
    boxes_per_carton INTEGER CHECK (boxes_per_carton > 0),
    box_item_id      INTEGER NOT NULL
                     REFERENCES packaging_items(id) DEFERRABLE INITIALLY DEFERRED,
    carton_item_id   INTEGER
                     REFERENCES packaging_items(id) DEFERRABLE INITIALLY DEFERRED,
    created_at       TEXT NOT NULL
);

CREATE TABLE shelf_transfers (
    id             INTEGER PRIMARY KEY,
    from_line_id   INTEGER NOT NULL
                   REFERENCES shelf_lines(id) DEFERRABLE INITIALLY DEFERRED,
    to_line_id     INTEGER NOT NULL
                   REFERENCES shelf_lines(id) DEFERRABLE INITIALLY DEFERRED,
    boxes          INTEGER NOT NULL CHECK (boxes > 0),
    transferred_on TEXT NOT NULL,
    CHECK (from_line_id <> to_line_id)
);

CREATE TABLE receipts (
    id                INTEGER PRIMARY KEY,
    kind              TEXT NOT NULL CHECK (kind IN ('material', 'packaging')),
    material_id       INTEGER
                      REFERENCES materials(id) DEFERRABLE INITIALLY DEFERRED,
    packaging_item_id INTEGER
                      REFERENCES packaging_items(id) DEFERRABLE INITIALLY DEFERRED,
    quantity          INTEGER NOT NULL CHECK (quantity > 0),
    receipt_date      TEXT NOT NULL,
    received_at       TEXT,
    received_quantity INTEGER CHECK (received_quantity > 0),
    lot_id            INTEGER
                      REFERENCES material_lots(id) DEFERRABLE INITIALLY DEFERRED,
    CHECK (
        (kind = 'material' AND material_id IS NOT NULL AND packaging_item_id IS NULL)
        OR (kind = 'packaging' AND packaging_item_id IS NOT NULL
            AND material_id IS NULL AND lot_id IS NULL)
    )
);

CREATE TABLE shipments (
    id              INTEGER PRIMARY KEY,
    shelf_line_id   INTEGER NOT NULL
                    REFERENCES shelf_lines(id) DEFERRABLE INITIALLY DEFERRED,
    boxes           INTEGER NOT NULL CHECK (boxes > 0),
    completion_date TEXT,
    shipment_date   TEXT,
    shipped_at      TEXT
);

-- AUTOINCREMENT keeps history ids strictly increasing and never reused, so the
-- latest id can safely key any cache of computed state (section 11.2).
CREATE TABLE history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    action_code  TEXT NOT NULL,
    description  TEXT NOT NULL,
    changes_json TEXT NOT NULL,
    undone_at    TEXT
);

-- Default settings (section 11.5). Working days use Python weekday numbers,
-- Monday = 0 to Sunday = 6.
INSERT INTO settings (key, value) VALUES
    ('yellow_days', '120'),
    ('red_days', '30'),
    ('working_days', '0,1,2,3,4'),
    ('default_transit_days', '5'),
    ('packaging_hours_per_day', '8'),
    ('packaging_utilization_bp', '10000');
