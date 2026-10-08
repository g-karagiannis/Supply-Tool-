-- Labels, cartons and pallets.
--
-- Packaging items get a type: ordinary packaging, label, carton or pallet.
-- A carton keeps its inner dimensions in length/width/height and gets outer
-- dimensions; a pallet has only outer dimensions (base and maximum load height).
-- Items already used in saved plans are classified from their use: the item
-- of a labelling step becomes a label, the item of a carton level a carton,
-- whose existing dimensions are its inner ones.

ALTER TABLE packaging_items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'packaging'
    CHECK (item_type IN ('packaging', 'label', 'carton', 'pallet'));
ALTER TABLE packaging_items ADD COLUMN outer_length_mm INTEGER CHECK (outer_length_mm > 0);
ALTER TABLE packaging_items ADD COLUMN outer_width_mm INTEGER CHECK (outer_width_mm > 0);
ALTER TABLE packaging_items ADD COLUMN outer_height_mm INTEGER CHECK (outer_height_mm > 0);

UPDATE packaging_items SET item_type = 'label'
WHERE id IN (SELECT packaging_item_id FROM packaging_steps WHERE kind = 'labelling');

UPDATE packaging_items SET item_type = 'carton'
WHERE id IN (SELECT packaging_item_id FROM packaging_steps WHERE kind = 'level' AND role = 'carton');

-- The role check gains 'pallet'. SQLite cannot change a CHECK in place, so the
-- table is rebuilt with the same columns and ids (foreign keys are off while
-- migrations run and are verified before commit).
CREATE TABLE packaging_steps_new (
    id                INTEGER PRIMARY KEY,
    order_id          INTEGER NOT NULL
                      REFERENCES packaging_plans(order_id) DEFERRABLE INITIALLY DEFERRED,
    position          INTEGER NOT NULL CHECK (position > 0),
    kind              TEXT NOT NULL CHECK (kind IN ('level', 'labelling')),
    role              TEXT CHECK (role IN ('primary', 'box', 'carton', 'pallet', 'other')),
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
INSERT INTO packaging_steps_new
    (id, order_id, position, kind, role, packaging_item_id, units_per, comes_ready, speed_per_min)
SELECT id, order_id, position, kind, role, packaging_item_id, units_per, comes_ready, speed_per_min
FROM packaging_steps;
DROP TABLE packaging_steps;
ALTER TABLE packaging_steps_new RENAME TO packaging_steps;

-- The shelf line remembers how many cartons go on a pallet and which pallet.
ALTER TABLE shelf_lines ADD COLUMN cartons_per_pallet INTEGER CHECK (cartons_per_pallet > 0);
ALTER TABLE shelf_lines ADD COLUMN pallet_item_id INTEGER
    REFERENCES packaging_items(id) DEFERRABLE INITIALLY DEFERRED;
