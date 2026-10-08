-- Soft delete for rows that closed orders and past records still reference.
-- A deleted material, packaging item, machine or shelf line disappears from
-- lists and choices, while old orders, receipts and shipments keep its name.
ALTER TABLE materials ADD COLUMN deleted_at TEXT;
ALTER TABLE packaging_items ADD COLUMN deleted_at TEXT;
ALTER TABLE machines ADD COLUMN deleted_at TEXT;
ALTER TABLE shelf_lines ADD COLUMN deleted_at TEXT;
