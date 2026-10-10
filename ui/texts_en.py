"""English user-interface strings. Same names as ui/texts_el.py.

Plain constants are labels; functions build sentences that contain values.
Numbers and dates passed to the functions are already formatted.
"""

from __future__ import annotations

PAGE_TITLE = "Supply Tool"

# ---------------------------------------------------------------- navigation
NAV_WAREHOUSE = "Warehouse"
NAV_PRODUCTS = "Products"
NAV_ORDERS = "Orders"
NAV_PRODUCTION = "Machines and production"
NAV_PACKAGING = "Packaging"
NAV_MOVEMENTS = "Receipts and shipments"
NAV_SETTINGS = "Settings"

NAV_LABELS: tuple[str, ...] = (
    NAV_WAREHOUSE,
    NAV_PRODUCTS,
    NAV_ORDERS,
    NAV_PRODUCTION,
    NAV_PACKAGING,
    NAV_MOVEMENTS,
    NAV_SETTINGS,
)

# ---------------------------------------------------------------- common
SAVE = "Save"
CANCEL = "Cancel"
CONTINUE = "Continue"
EDIT = "Edit"
DELETE = "Delete"
UNDO = "Undo"
SELECT_ROW_FIRST = "Select a row first"
NO_ROWS = "There are no rows."
NOTHING_TO_UNDO = "There is no action to undo"
UNIT_KG = "kg"
UNIT_PCS = "pcs"
UNIT_PIECES = "pieces"
UNIT_BOXES = "boxes"
UNIT_DAYS = "days"
UNIT_HOURS = "hours"
UNIT_MINUTES = "minutes"
NOT_A_NUMBER = "Type a number, with a comma or a dot for decimals."
SAVED = "The action was saved."
UNDONE = "The action was undone."


def undo_label(description: str) -> str:
    return f"Undo: {description}"


def undo_confirm(description: str) -> str:
    return f"This will be undone: {description}. Continue?"


def parsed_as(value: str, unit: str = "") -> str:
    return f"= {value} {unit}".rstrip()


def field_required(field: str) -> str:
    return f"The field “{field}” is required."


def field_positive(field: str) -> str:
    return f"The field “{field}” must be greater than 0."


def field_not_negative(field: str) -> str:
    return f"The field “{field}” cannot be negative."


def field_range(field: str, low: str, high: str) -> str:
    return f"The field “{field}” must be from {low} to {high}."


def field_decimals(field: str) -> str:
    return f"The field “{field}” has more decimals than allowed."


def field_whole(field: str) -> str:
    return f"The field “{field}” must be a whole number."


def action_failed(detail: str) -> str:
    return f"The action was not completed ({detail}). Check the data and try again."


# ---------------------------------------------------------------- statuses and labels
CATEGORY_RAW_MATERIAL = "Raw material"
CATEGORY_EXCIPIENT = "Excipient"
CATEGORY_PACKAGING_MATERIAL = "Packaging material"

EXPIRY_VALID = "Valid"
EXPIRY_EXPIRED = "Expired"
DEPLETED = "Depleted"


def expires_in(days: int) -> str:
    return f"Expires in {days} days"


STATUS_CANCELLED = "Cancelled"
STATUS_SHIPPED = "Shipped"
STATUS_TRANSFERRED = "Transferred"
STATUS_ON_SHELF = "On the shelf"
STATUS_IN_PACKAGING = "In packaging"
STATUS_IN_PRODUCTION = "In production"
STATUS_READY = "Ready for production"
STATUS_WAITING = "Waiting for materials"
FLAG_NO_MACHINE = "No machine"
FLAG_NO_PACKAGING_PLAN = "No packaging plan"
FLAG_MISSING_PACKAGING = "Packaging missing"

RECEIPT_EXPECTED = "Expected"
RECEIPT_RECEIVED = "Received"


def receipt_delayed(days: int) -> str:
    return f"Late by {days} days"


SHIPMENT_PENDING = "Awaiting shipment"
SHIPMENT_SHIPPED = "Shipped"

KIND_MATERIAL = "Material"
KIND_PACKAGING = "Packaging"
KIND_LABEL = "Label"

STEP_LEVEL = "Package"
STEP_LABELLING = "Labelling"
ROLE_PRIMARY = "Product packaging"
ROLE_BOX = "Packaging container"
ROLE_CARTON = "Case"
ROLE_PALLET = "Pallet"
ROLE_OTHER = "Other"

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

ORDER_NAME_PREFIX = "ORD-"

# ---------------------------------------------------------------- action errors


def code_exists(code: str) -> str:
    return f"The code {code} already exists. Choose another code."


def name_exists(name: str) -> str:
    return f"The name {name} already exists. Choose another name."


def percent_total(total: str) -> str:
    return f"The percentages add up to {total}%. They must add up to 100%."


def duplicate_material(name: str) -> str:
    return f"The material {name} appears twice. Each material goes in once."


PERCENT_POSITIVE = "Every percentage must be greater than 0."
OUTER_ONLY_FOR_CONTAINERS = "Only cases and pallets have outer dimensions."
NO_INNER_DIMENSIONS = "Labels and pallets have no inner dimensions."
BREAKDOWN_ONLY_FOR_PACKAGING = "Only packaging items have a material breakdown."
TYPE_LOCKED = "The type of an item does not change after it is created."

ITEM_TYPE_NAMES = {
    "packaging": "a packaging item",
    "label": "a label",
    "carton": "a case",
    "pallet": "a pallet",
}


def wrong_item_type(step: int, expected: str) -> str:
    return f"In step {step}, choose {ITEM_TYPE_NAMES[expected]}."


def wrong_extra_type(step: int) -> str:
    return f"The extra items of step {step} must be packaging items or labels."


RECIPE_EMPTY = "Add at least one material to the recipe."
BREAKDOWN_NEEDS_WEIGHT = "A material breakdown needs a unit weight."
DIMENSIONS_ALL_OR_NONE = "Fill in all three dimensions or none."
NEGATIVE_STOCK = "The quantity exceeds the stock."
PRODUCT_WITHOUT_RECIPE = "The product has no saved recipe."
PRODUCT_WITHOUT_WEIGHT = "The product has no weight per piece."
QUANTITY_LOCKED = "The quantity cannot change after the first assignment is completed."
CANCEL_LOCKED = "The order cannot be cancelled, because a production assignment is completed."
ORDER_CLOSED = "The order is closed and cannot change."
PRODUCTION_DONE = "Production of this order is completed."
WAITING_MATERIALS = "The order is waiting for materials. See the shortage table."
ASSIGNMENT_DONE = "The assignment is already completed."
PRODUCTION_NOT_DONE = "Production is not completed."
NO_PLAN = "There is no packaging plan."
MISSING_PACKAGING = "Packaging is missing. See the requirements table."
PACKAGING_DONE = "Packaging of this order is completed."
RECEIPT_ALREADY_RECEIVED = "The receipt is already recorded as received and cannot change."
SHIPMENT_ALREADY_SHIPPED = "The shipment is already marked as shipped and cannot change."
TRANSFER_MISMATCH = (
    "A transfer goes only to a line of the same product, with the same pieces per box "
    "and the same boxes per case."
)
TRANSFER_SAME_LINE = "Choose a different target line."
SHELF_NOT_EMPTY = "The shelf line still has boxes. It can be deleted only when the boxes are 0."
RED_NOT_BELOW_YELLOW = "The red limit must be lower than the yellow limit."
NO_WORKING_DAYS = "Choose at least one working day."
LOT_NUMBER_REQUIRED = "Type a LOT Number."
EXPIRY_REQUIRED = "Type an expiry date."


def boxes_over_free(free: str) -> str:
    return f"The boxes exceed the free boxes ({free})."


def boxes_over_line(boxes: str) -> str:
    return f"The boxes exceed the boxes of the shelf line ({boxes})."


def position_range(count: int) -> str:
    return f"The position must be from 1 to {count}."


def assignment_sum(total: str, expected: str) -> str:
    return (
        f"The assignments add up to {total} kg; they must equal the quantity "
        f"still to be produced ({expected} kg)."
    )


def lot_not_empty(lot: str) -> str:
    return f"LOT {lot} still has quantity. It can be deleted only when the quantity is 0."


def material_has_stock(name: str) -> str:
    return f"The material {name} still has stock. It can be deleted only when all LOTs are 0."


def material_in_recipe(material: str, product: str) -> str:
    return f"{material} belongs to the recipe of the product {product}."


def material_in_breakdown(material: str, item: str) -> str:
    return f"{material} belongs to the material breakdown of the packaging item {item}."


def material_in_open_order(material: str, order: str) -> str:
    return f"{material} is needed for the open order {order}."


def packaging_has_stock(name: str) -> str:
    return f"The packaging item {name} still has pieces. It can be deleted only when the quantity is 0."


def packaging_in_open_order(item: str, order: str) -> str:
    return f"The packaging item {item} is used in the packaging of the open order {order}."


def product_has_orders(product: str, order: str) -> str:
    return f"The product {product} has the order {order}. It can be deleted only if it has no orders."


def machine_in_open_order(machine: str, order: str) -> str:
    return f"The machine {machine} has an assignment in the open order {order}."


PLAN_ISSUES = {
    "no_steps": "Add at least one step.",
    "labelling_before_level": "A Labelling step must follow a Package step.",
    "level_without_role": "Every Package step needs a role.",
    "level_without_contents": "Fill in “Contains” in every Package step.",
    "box_count": "The plan must have exactly one Package step with the role “Packaging container”.",
    "carton_before_box": "The case goes after the packaging container.",
    "multiple_cartons": "The plan has at most one Package step “Case”.",
    "components_without_weight": "A packaging item with a material breakdown has no unit weight.",
    "non_positive_speed": "The pieces per minute must be greater than 0.",
    "non_positive_extra": "The quantity of every extra item must be greater than 0.",
    "too_many_steps": "The plan has at most 10 steps.",
    "pallet_without_carton": "The pallet goes after the case.",
    "multiple_pallets": "The plan has at most one Package step “Pallet”.",
    "level_after_pallet": "After the pallet only labelling can follow.",
}

# ---------------------------------------------------------------- confirmations (4.12)


def loses_materials(order: str) -> str:
    return f"The order {order} will go back to Waiting for materials. Continue?"


def loses_materials_started(order: str, start: str) -> str:
    return (
        f"The order {order} has the start date {start} and may already be in production. "
        "Do you really want to take its materials away?"
    )


def expired_lot_consumed(lot: str, expiry: str) -> str:
    return f"LOT {lot} expired on {expiry}. Was it consumed in this production?"


ACTUAL_OVER_PLANNED = "The actual pieces exceed the planned pieces. Check the number."

# ---------------------------------------------------------------- warnings (4.12)


def warn_start_before_receipt(material: str, day: str) -> str:
    return f"The start is before the expected receipt of {material} on {day}."


def warn_no_covering_receipt(material: str, missing: str) -> str:
    return f"No expected receipt covers the material {material}. Missing: {missing}."


def warn_arrival_after_delivery(arrival: str, delivery: str) -> str:
    return f"The estimated arrival ({arrival}) is after the delivery date ({delivery})."


def warn_red_lot(lot: str, material: str, days: int) -> str:
    return f"LOT {lot} of the material {material} expires in {days} days."


# ---------------------------------------------------------------- history descriptions (11.3)


def h_material_created(name: str) -> str:
    return f"New material: {name}"


def h_material_updated(name: str) -> str:
    return f"Material corrected: {name}"


def h_material_deleted(name: str) -> str:
    return f"Material deleted: {name}"


def h_lot_created(lot: str, material: str, quantity: str) -> str:
    return f"New LOT: {lot}, {material}, {quantity} kg"


def h_lot_quantity(lot: str, old: str, new: str) -> str:
    return f"Quantity corrected: LOT {lot} from {old} kg to {new} kg"


def h_lot_updated(lot: str) -> str:
    return f"LOT corrected: {lot}"


def h_lot_deleted(lot: str) -> str:
    return f"LOT deleted: {lot}"


def h_packaging_created(name: str) -> str:
    return f"New packaging item: {name}"


def h_packaging_updated(name: str) -> str:
    return f"Packaging item corrected: {name}"


def h_packaging_quantity(name: str, old: str, new: str) -> str:
    return f"Quantity corrected: {name} from {old} to {new} pieces"


def h_packaging_deleted(name: str) -> str:
    return f"Packaging item deleted: {name}"


def h_product_created(name: str) -> str:
    return f"New product: {name}"


def h_product_updated(name: str) -> str:
    return f"Product corrected: {name}"


def h_product_deleted(name: str) -> str:
    return f"Product deleted: {name}"


def h_order_created(order: str, product: str, quantity: str) -> str:
    return f"New order: {order}, {product}, {quantity} kg"


def h_order_updated(order: str) -> str:
    return f"Order corrected: {order}"


def h_sequence(order: str, old: int, new: int) -> str:
    return f"Sequence changed: {order} from position {old} to position {new}"


def h_order_cancelled(order: str) -> str:
    return f"Order cancelled: {order}"


def h_machine_created(name: str) -> str:
    return f"New machine: {name}"


def h_machine_updated(name: str) -> str:
    return f"Machine corrected: {name}"


def h_machine_deleted(name: str) -> str:
    return f"Machine deleted: {name}"


def h_assignments(order: str) -> str:
    return f"Machine assignment: {order}"


def h_production_completed(order: str, machine: str, pieces: str) -> str:
    return f"Production completed: {order}, {machine}, {pieces} pieces"


def h_packaging_plan(order: str) -> str:
    return f"Packaging plan: {order}"


def h_packaging_completed(order: str, boxes: str, leftovers: list[str]) -> str:
    text = f"Packaging completed: {order}, {boxes} boxes"
    if leftovers:
        text += ", left over " + " and ".join(leftovers)
    return text


def h_receipt_created(item: str, quantity: str) -> str:
    return f"New receipt: {item}, {quantity}"


def h_receipt_updated(item: str) -> str:
    return f"Receipt corrected: {item}"


def h_receipt_deleted(item: str) -> str:
    return f"Receipt deleted: {item}"


def h_received(item: str, quantity: str, lot: str | None) -> str:
    text = f"Received: {item}, {quantity}"
    return f"{text}, LOT {lot}" if lot else text


def h_shipment_created(product: str, order: str, boxes: str) -> str:
    return f"New shipment: {product}, {order}, {boxes} boxes"


def h_shipment_updated(product: str, order: str) -> str:
    return f"Shipment corrected: {product}, {order}"


def h_shipment_deleted(product: str, order: str) -> str:
    return f"Shipment deleted: {product}, {order}"


def h_shipped(product: str, order: str, boxes: str) -> str:
    return f"Shipped: {product}, {order}, {boxes} boxes"


def h_transfer(boxes: str, product: str, source: str, target: str) -> str:
    return f"Transfer: {boxes} boxes of {product} from {source} to {target}"


def h_shelf_deleted(product: str, order: str) -> str:
    return f"Shelf line deleted: {product}, {order}"


H_SETTINGS = "Settings changed"

# ---------------------------------------------------------------- shared screen texts
REMOVE = "Remove"
CONFIRM_DELETE_TITLE = "Delete"
UNIT_FIXED_KG = "Unit of measure: kg"
OPTIONAL = "optional"


def confirm_delete(name: str) -> str:
    return f"This will be deleted: {name}. Continue?"


def expected_entry(quantity: str, day: str) -> str:
    return f"+{quantity} on {day}"


def percent_sum(total: str) -> str:
    return f"Total of percentages: {total}%"


# ---------------------------------------------------------------- tab 1: warehouse
WH_MATERIALS = "Materials"
WH_LOTS = "LOT"
WH_PACKAGING = "Packaging"
WH_SHELF = "Finished goods"
WH_ADD_MATERIAL = "(+) Add Material"
WH_ADD_LOT = "(+) Add LOT"
WH_EDIT_LOT = "Edit LOT"
WH_DELETE_LOT = "Delete LOT"
WH_ADD_PACKAGING = "(+) Add Packaging"
WH_ADD_CONTAINER = "(+) Add Case/Pallet"
WH_LABELS = "Labels"
WH_ADD_LABEL = "(+) Add Label"
COL_OUTER_DIMENSIONS = "Outer dimensions (cm)"
CARTON_DIMENSIONS_NOTE = "For cases, “Dimensions” are the inner ones. Pallets have only outer dimensions: base and maximum load height."
F_CONTAINER_TYPE = "Type"
F_INNER_DIMENSIONS = "Inner dimensions"
F_OUTER_DIMENSIONS = "Outer dimensions"
INNER_DIMENSIONS_HELP = "To work out how many packaging containers fit in the case."
OUTER_DIMENSIONS_HELP = "To work out how many cases fit on the pallet."
PALLET_DIMENSIONS_HELP = "The base of the pallet and the maximum load height."
F_PALLET_LENGTH = "Base length (cm)"
F_PALLET_WIDTH = "Base width (cm)"
F_PALLET_HEIGHT = "Maximum load height (cm)"
T_NEW_CONTAINER = "New case or pallet"
T_EDIT_CONTAINER = "Edit case or pallet"
T_NEW_LABEL = "New label"
T_EDIT_LABEL = "Edit label"
WH_TRANSFER = "Transfer"

COL_CODE = "Code"
COL_NAME = "Name"
COL_CATEGORY = "Category"
COL_TOTAL_KG = "Total (kg)"
COL_RESERVED_KG = "Reserved (kg)"
COL_AVAILABLE_KG = "Available (kg)"
COL_EXPECTED = "Expected"
COL_INDICATOR = "Indicator"
COL_MATERIAL = "Material"
COL_LOT_NUMBER = "LOT Number"
COL_QUANTITY_KG = "Quantity (kg)"
COL_EXPIRY = "Expiry date"
COL_DAYS_LEFT = "Days left"
COL_STATUS = "Status"
COL_DIMENSIONS = "Dimensions (cm)"
COL_BREAKDOWN = "Material breakdown"
COL_TOTAL_PCS = "Total (pcs)"
COL_RESERVED_PCS = "Reserved (pcs)"
COL_AVAILABLE_PCS = "Available (pcs)"
COL_PRODUCT = "Product"
COL_ORDER = "Order"
COL_DESTINATION = "Destination"
COL_BOXES = "Boxes"
COL_PIECES_PER_BOX = "Pieces per box"
COL_CARTONS = "Cases"
COL_BOXES_PER_CARTON = "Boxes per case"
COL_LOOSE_BOXES = "Loose boxes"
COL_PENDING_BOXES = "To be shipped"
COL_FREE_BOXES = "Free boxes"
COL_DELIVERY = "Delivery"
COL_SHIP_BY = "Ship by"
COL_TRANSFERS = "Transfers"

IMPORTED = "Bought in"

F_MATERIAL_NAME = "Material name"
F_CODE = "Code"
F_CATEGORY = "Category"
F_DESCRIPTION = "Description"
F_FIRST_LOT = "First LOT (optional)"
F_LOT_NUMBER = "LOT Number"
F_QUANTITY_KG = "Quantity (kg)"
F_EXPIRY = "Expiry date"
F_NAME = "Name"
F_QUANTITY_PCS = "Quantity (pieces)"
F_LENGTH = "Length (cm)"
F_WIDTH = "Width (cm)"
F_HEIGHT = "Height (cm)"
DIMENSIONS_HELP = "Fill in all three or none."
F_UNIT_WEIGHT_G = "Unit weight (g)"
F_BREAKDOWN = "Material breakdown (optional)"
F_PERCENT = "Percentage (%)"
ADD_BREAKDOWN_LINE = "(+) Add material"
F_TARGET_LINE = "Target line"
F_BOXES = "Boxes"
NO_COMPATIBLE_LINE = "There is no other line of the same product with the same pieces per box and the same boxes per case."

T_NEW_MATERIAL = "New material"
T_EDIT_MATERIAL = "Edit material"
T_NEW_LOT = "New LOT"
T_EDIT_LOT = "Edit LOT"
T_NEW_PACKAGING = "New packaging item"
T_EDIT_PACKAGING = "Edit packaging item"
T_TRANSFER = "Transfer boxes"


def free_boxes_note(boxes: str) -> str:
    return f"Free boxes on the source line: {boxes}"


def transfer_entry(boxes: str, direction: str, destination: str, day: str) -> str:
    return f"{boxes} boxes {direction} {destination} on {day}"


TRANSFER_TO = "to"
TRANSFER_FROM = "from"


def breakdown_text(parts: str, weight: str) -> str:
    return f"{parts}, {weight} g"


# ---------------------------------------------------------------- tab 2: products
PR_ADD = "(+) Add Product"
COL_WEIGHT_G = "Weight per piece (g)"
COL_MATERIAL_COUNT = "Materials"
COL_PRODUCIBLE_KG = "Available quantity (kg)"
COL_IN_PIECES = "In pieces"
COL_LIMITING = "Limiting material"
COL_PERCENT = "Percentage"
COL_AVAILABLE = "Available"
COL_ENOUGH_FOR = "Enough for"
COL_CONSUMED = "Consumed"
COL_LEFTOVER = "Left over"
LIMITING_MARK = "(limiting)"
F_PRODUCT_NAME = "Name"
F_WEIGHT_PER_PIECE = "Weight per piece (g)"
F_RECIPE = "Recipe"
ADD_RECIPE_LINE = "(+) Add Material"
NEW_MATERIAL_INLINE = "New material"
CREATE_MATERIAL = "Create material"
T_NEW_PRODUCT = "New product"
T_EDIT_PRODUCT = "Edit product"
PRODUCT_SHEET = "Product sheet"
NO_RECIPE = "The product has no recipe."


def producible_summary(quantity: str) -> str:
    return f"Available product quantity: {quantity} kg."


def pieces_summary(pieces: str, weight: str) -> str:
    return f"This is {pieces} pieces, at a unit weight of {weight} g."


def limiting_summary(material: str) -> str:
    return f"Limiting material: {material}."


# ---------------------------------------------------------------- tab 3: orders
OR_NEW = "(+) New Order"
OR_SEQUENCE = "Change sequence"
OR_CANCEL = "Cancel order"
OR_SHOW_CLOSED = "Show closed orders"
COL_SEQUENCE = "Sequence"
COL_START = "Start"
COL_READINESS = "Estimated readiness"
COL_WARNINGS = "Warnings"
COL_NEED = "Needed"
COL_MISSING = "Missing"
COL_DAYS_TO_EXPIRY = "Expires in (days)"
F_PRODUCT = "Product"
F_ORDER_QUANTITY = "Quantity (kg)"
F_ORDER_NAME = "Name"
F_DESTINATION = "Destination"
F_DELIVERY = "Delivery date"
F_TRANSIT = "Transit days"
F_NEW_POSITION = "New position"
SAVE_REDUCED = "Reduce to the available quantity"
SAVE_WAITING = "Save as Waiting for materials"
T_NEW_ORDER = "New order"
T_EDIT_ORDER = "Edit order"
T_SEQUENCE = "Change sequence"
T_CANCEL_ORDER = "Cancel order"
DETAILS_SHORTAGES = "Shortage table"
DETAILS_LOTS = "LOTs to consume"
DETAILS_ASSIGNMENTS = "Machine assignments"
DETAILS_PACKAGING = "Packaging"
DETAILS_WARNINGS = "Warnings"
NO_SHORTAGE_LINES = "Production is completed. No more recipe materials are needed."
NO_LOTS = "The order holds no reserved materials, so there are no LOTs to consume."
NO_ASSIGNMENTS = "There is no machine assignment."
NO_WARNINGS = "There are no warnings."
NO_START = "No start date set"
WITHOUT_PACKAGING = "without packaging"
QUANTITY_LOCKED_NOTE = "The quantity cannot change, because an assignment is completed."


def available_today(quantity: str) -> str:
    return f"Available product quantity today: {quantity} kg"


def order_details(name: str) -> str:
    return f"Order details: {name}"


def confirm_cancel(order: str) -> str:
    return f"The order {order} will be cancelled and its materials released. Continue?"


def current_position(position: int, count: int) -> str:
    return f"Current position: {position} of {count}"


def packaging_summary(boxes: str, cartons: str, days: str) -> str:
    return f"{boxes} boxes, {cartons} cases, {days} packaging days"


def assignment_summary(machine: str, quantity: str, days: str, pieces: str) -> str:
    return f"{machine}: {quantity} kg, {days} production days, {pieces} expected pieces"


# ---------------------------------------------------------------- tab 4: machines and production
MA_TITLE = "Machines"
MA_ADD = "(+) Add Machine"
PO_TITLE = "Orders to produce"
PO_ASSIGN = "Assign to machine"
PO_INVERSE = "Inverse calculation"
PO_COMPLETE = "Completed"
PO_DONE_TITLE = "Completed productions"
COL_MACHINE = "Machine"
COL_BATCH_KG = "Batch size (kg)"
COL_CYCLE = "Cycle time (minutes)"
COL_UTILIZATION = "Effective utilization (%)"
COL_HOURS_PER_DAY = "Operating hours per day"
COL_MAX_BATCH = "Maximum batch (kg)"
COL_MIN_CYCLE = "Minimum cycle time (minutes)"
COL_ASSIGNED_KG = "Assigned quantity (kg)"
COL_BATCHES = "Batches"
COL_TIME_HOURS = "Time (hours)"
COL_PRODUCTION_DAYS = "Production days"
COL_PRODUCTION_END = "Production end"
COL_PLANNED = "Planned pieces"
COL_EXPECTED_PIECES = "Expected pieces"
COL_ACTUAL = "Actual pieces"
COL_COMPLETED_ON = "Completion date"
F_MACHINE_NAME = "Name"
F_BATCH = "Batch size (kg)"
F_CYCLE = "Cycle time (minutes)"
F_UTILIZATION = "Effective utilization (%)"
UTILIZATION_HELP = "Example: 6.4 productive hours in 8 operating hours give 80%"
F_HOURS = "Operating hours per day"
F_MAX_BATCH = "Maximum batch (kg)"
F_MIN_CYCLE = "Minimum cycle time (minutes)"
F_MACHINE = "Machine"
F_DEFECTS = "Defect rate (%)"
DEFECTS_HELP = "The value comes from QC and production."
F_START = "Start date"
ADD_MACHINE_SHARE = "Add machine"
F_TARGET_DAYS = "Production days you want"
F_ACTUAL_PIECES = "Actual pieces"
T_NEW_MACHINE = "New machine"
T_EDIT_MACHINE = "Edit machine"
T_ASSIGN = "Assign to machine"
T_INVERSE = "Inverse calculation"
T_COMPLETE_PRODUCTION = "Complete production"
R_BATCHES = "Batches"
R_NET = "Net time"
R_OPERATING = "Operating time"
R_DAYS = "Production days"
R_PER_BATCH = "Pieces per batch"
R_PLANNED = "Planned pieces"
R_EXPECTED = "Expected pieces"
R_DEFECTS = "Expected defects"
R_END = "Production end"
COL_IF_ONLY = "If only this changes"
COL_FROM = "From"
COL_TO = "To"
COL_CHANGE = "Change"
COL_LIMIT = "Limit"
COL_RESULT = "Result"
COL_VALUE = "Value"
LEVER_CYCLE = "Cycle time"
LEVER_BATCH = "Batch size"
LEVER_HOURS = "Hours per day"
FEASIBLE = "Feasible"
INFEASIBLE = "Not feasible"
LIMIT_MIN = "Minimum"
LIMIT_MAX = "Maximum"
REASON_24 = "more than 24 hours per day"
REASON_MAX_BATCH = "above the maximum batch of the machine"
REASON_MIN_CYCLE = "below the minimum cycle time of the machine"
INVERSE_NOTE = "The calculation is for information. No value changes automatically."
NO_MACHINES = "Add a machine first."
SELECT_ASSIGNMENT_FIRST = "Select a row with a machine first."


def current_days(days: str) -> str:
    return f"Current production time: {days} days"


def share_title(number: int) -> str:
    return f"Machine {number}"


def remaining_note(quantity: str) -> str:
    return f"Quantity to produce: {quantity} kg"


WARN_SHORT_START = "Start before receipt"
WARN_SHORT_ARRIVAL = "Arrival after delivery"
WARN_SHORT_RED_LOT = "Red LOT"


def warn_short_no_receipt(material: str) -> str:
    return f"No receipt for {material}"


# ---------------------------------------------------------------- tab 5: packaging
PK_PLAN = "Packaging plan"
PK_COMPLETE = "Completed"
COL_PIECES = "Pieces"
COL_BASIS = "Calculation basis"
COL_PLAN = "Plan"
COL_PACKAGING_DAYS = "Packaging days"
COL_INDICATIONS = "Indications"
COL_STEP = "Step"
COL_CONTAINS = "Contains"
COL_COMES_READY = "Comes ready"
COL_UNITS = "Units"
COL_REMAINDER = "Remainder"
COL_PER_MINUTE = "Per minute"
COL_NET_TIME = "Net time"
COL_ITEM = "Item"
YES = "Yes"
NO = "No"
BASIS_EXPECTED = "Expected"
BASIS_ACTUAL = "Actual"
BASIS_WITHOUT_DEFECTS = "Expected, without defect rate"
CALC_WITH_EXPECTED = "Calculated with expected pieces"
CALC_WITH_ACTUAL = "Calculated with actual pieces"
CALC_WITHOUT_DEFECTS = "Calculated with pieces without a defect rate"
F_PACK_HOURS = "Operating hours per day"
F_PACK_UTILIZATION = "Effective utilization (%)"
F_STEP_KIND = "Step kind"
F_ROLE = "Role"
F_PACKAGING_ITEM = "Packaging"
F_CONTAINS = "Contains"
F_COMES_READY = "Comes ready"
F_SPEED = "Pieces per minute"
F_EXTRAS = "Extra items"
F_EXTRA_QUANTITY = "Quantity per unit"
ADD_EXTRA = "(+) Add extra item"
ADD_STEP = "(+) Add step"
F_FIT = "Placement of boxes in the case"
F_FIT_PALLET = "Placement of cases on the pallet"
UNIT_CARTONS = "cases"
COL_PALLETS = "Pallets"
MAX_STEPS_NOTE = "The plan already has 10 steps, the maximum."
ITEM_FIELD_LABELS = {
    "packaging": "Packaging",
    "label": "Label",
    "carton": "Case",
    "pallet": "Pallet",
}
CUSTOM_NUMBER = "My own number"
SAVE_PLAN = "Save plan"
T_PLAN = "Packaging plan"
T_COMPLETE_PACKAGING = "Complete packaging"
STEPS_TABLE = "Steps table"
NEEDS_TABLE = "Requirements table"
NO_PIECES = "There are no pieces to calculate with. Check the unit weight of the order."
NO_PACKAGING_ITEMS = "Add packaging items to the Warehouse first."
WILL_DEDUCT = "This will be taken from the Warehouse:"
WILL_SHELVE = "The shelf line will be created with:"


def step_number(number: int) -> str:
    return f"Step {number}"


def labelling_of(item: str) -> str:
    return f"Labelling: {item}"


def contains_pieces(count: str) -> str:
    return f"{count} pieces"


def contains_units(count: str, name: str) -> str:
    return f"{count} {name}"


def fit_option(orientation: str, per_axis: str, count: str, unit: str = "boxes") -> str:
    return f"{orientation} cm: {per_axis} = {count} {unit}"


def last_pallet_note(cartons: str) -> str:
    return f"the last with {cartons} cases"


def pallets_cell(pallets: str, last_cartons: str | None) -> str:
    """E.g. "13 pallets (the last with 5 cases)"."""
    text = f"{pallets} pallets"
    return f"{text} ({last_pallet_note(last_cartons)})" if last_cartons else text


def limiting_packaging(item: str, boxes: str) -> str:
    return f"Limited by the packaging item {item}. With the available stock, {boxes} boxes can be packed."


def sequential_time(days: str) -> str:
    return f"One after another: {days} days"


def inline_time(days: str) -> str:
    return f"In line: {days} days"


def readiness_estimate(day: str) -> str:
    return f"Estimated readiness: {day}"


def arrival_estimate(day: str) -> str:
    return f"Estimated arrival: {day}"


def shelf_preview(boxes: str, per_box: str, per_carton: str) -> str:
    return f"{boxes} boxes of {per_box} pieces, {per_carton} boxes per case"


# ---------------------------------------------------------------- tab 6: receipts and shipments
RC_TITLE = "Receipts"
RC_ADD = "(+) Add Receipt"
RC_RECEIVED = "Received"
READY_TITLE = "Ready for shipment"
SH_TITLE = "Shipments"
SH_ADD = "(+) Add Shipment"
SH_SHIPPED = "Shipped"
COL_TYPE = "Type"
COL_KIND_ITEM = "Item"
COL_QUANTITY = "Quantity"
COL_RECEIVED = "Received"
COL_RECEIVED_QUANTITY = "Received quantity"
COL_RECEIPT_DATE = "Receipt date"
COL_ORDER_AND_DESTINATION = "Order and destination"
COL_SHIPPED = "Shipped"
COL_COMPLETION_DATE = "Completion date"
COL_SHIPMENT_DATE = "Shipment date"
F_TYPE = "Type"
F_ITEM = "Item"
F_QUANTITY = "Quantity"
F_RECEIPT_DATE = "Receipt date"
F_SHELF_LINE = "Shelf line"
F_COMPLETION_DATE = "Completion date"
F_SHIPMENT_DATE = "Shipment date"
T_NEW_RECEIPT = "New receipt"
T_EDIT_RECEIPT = "Edit receipt"
T_RECEIVED = "Receipt"
T_NEW_SHIPMENT = "New shipment"
T_EDIT_SHIPMENT = "Edit shipment"
T_SHIPPED = "Shipment"
WAITING_FOR_ITEM = "Orders waiting for this item"
NO_WAITING_ORDERS = "No order is waiting for this item."
NO_FREE_LINES = "There is no shelf line with free boxes."
NEW_ITEM_HINT = "If the item does not exist, add it to the Warehouse first, with “(+) Add Material” or “(+) Add Packaging”."


def unit_of(unit: str) -> str:
    return f"Unit: {unit}"


def cartons_note(boxes: str, cartons: str, per_carton: str) -> str:
    return f"{boxes} boxes: {cartons} cases of {per_carton} boxes"


def cartons_cell(full: str, dims: str, loose: str) -> str:
    text = f"{full} full"
    if dims:
        text += f", {dims} cm"
    return f"{text}, and {loose} loose boxes"


def boxes_cell(boxes: str, dims: str) -> str:
    return f"{boxes} pieces, {dims} cm" if dims else f"{boxes} pieces"


# ---------------------------------------------------------------- settings
ST_SETTINGS = "Settings"
ST_HISTORY = "History"
ST_BACKUP = "Backup"
F_YELLOW = "Yellow limit (days)"
F_RED = "Red limit (days)"
F_WORKING_DAYS = "Working days"
F_MACHINE_HOURS = "Operating hours per working day"
F_MACHINE_HOURS_HELP = "Default for a new machine. Every machine keeps its own hours, which change when it is created or edited."
F_DEFAULT_TRANSIT = "Transit days"
F_DEFAULT_TRANSIT_HELP = "Default for a new order."
F_PACKAGING_HOURS = "Packaging hours per day"
F_PACKAGING_UTILIZATION = "Packaging utilization (%)"
F_PACKAGING_DEFAULTS_HELP = "Default for a new packaging plan."
SAVE_SETTINGS = "Save settings"
COL_WHEN = "Date and time"
COL_ACTION = "Action"
COL_DESCRIPTION = "Description"
COL_UNDONE = "Undone"


ST_WIPE = "Full wipe"
WIPE_NOTE = "Deletes all data and information of the application. A backup is saved automatically before deleting."
WIPE_CONFIRM = (
    "All data will be deleted: materials, LOTs, packaging, products, orders, machines, "
    "receipts, shipments, shelf and history. The settings go back to their defaults. "
    "This cannot be undone. A backup is saved automatically in the backups folder "
    "before deleting. Continue?"
)


def wipe_done(path: str) -> str:
    return f"The application was wiped. The backup was saved to {path}."


def backup_done(path: str) -> str:
    return f"The backup was saved to {path}."


ACTION_LABELS = {
    "material_create": "New material",
    "material_update": "Material corrected",
    "material_delete": "Material deleted",
    "lot_create": "New LOT",
    "lot_update": "LOT corrected",
    "lot_delete": "LOT deleted",
    "packaging_create": "New packaging item",
    "packaging_update": "Packaging item corrected",
    "packaging_delete": "Packaging item deleted",
    "product_create": "New product",
    "product_update": "Product corrected",
    "product_delete": "Product deleted",
    "order_create": "New order",
    "order_update": "Order corrected",
    "order_sequence": "Sequence changed",
    "order_cancel": "Order cancelled",
    "machine_create": "New machine",
    "machine_update": "Machine corrected",
    "machine_delete": "Machine deleted",
    "assignments_set": "Machine assignment",
    "production_complete": "Production completed",
    "packaging_plan": "Packaging plan",
    "packaging_complete": "Packaging completed",
    "receipt_create": "New receipt",
    "receipt_update": "Receipt corrected",
    "receipt_delete": "Receipt deleted",
    "receipt_received": "Receipt",
    "shipment_create": "New shipment",
    "shipment_update": "Shipment corrected",
    "shipment_delete": "Shipment deleted",
    "shipment_shipped": "Shipment",
    "shelf_transfer": "Transfer",
    "shelf_delete": "Shelf line deleted",
    "settings_update": "Settings changed",
}

# Field names used in validation messages of the data actions.
FIELDS = {
    "code": "Code",
    "material_name": "Material name",
    "quantity": "Quantity",
    "name": "Name",
    "quantity_pcs": "Quantity (pieces)",
    "product_name": "Name",
    "weight_per_piece": "Weight per piece",
    "cycle_time": "Cycle time (minutes)",
    "hours_per_day": "Operating hours per day",
    "length": "Length",
    "width": "Width",
    "height": "Height",
    "unit_weight": "Unit weight",
    "description": "Description",
    "quantity_kg": "Quantity (kg)",
    "destination": "Destination",
    "transit_days": "Transit days",
    "max_batch": "Maximum batch (kg)",
    "min_cycle": "Minimum cycle time (minutes)",
    "actual_pieces": "Actual pieces",
    "item": "Item",
    "boxes": "Boxes",
    "yellow_days": "Yellow limit (days)",
    "red_days": "Red limit (days)",
    "machine_hours": "Operating hours per working day",
    "packaging_hours": "Packaging hours per day",
    "material": "Material",
    "product": "Product",
    "delivery_date": "Delivery date",
    "receipt_date": "Receipt date",
    "shelf_line": "Shelf line",
    "packaging_utilization": "Packaging utilization (%)",
    "machine": "Machine",
    "defect_rate": "Defect rate (%)",
    "packaging_item": "Packaging",
    "assignment_quantity": "Assigned quantity (kg)",
    "extras": "Extra items",
    "batch_size": "Batch size (kg)",
    "utilization": "Effective utilization (%)",
    "lot_number": "LOT Number",
}
