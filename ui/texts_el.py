"""Greek user-interface strings. ui/texts_en.py has the same names in English.

Plain constants are labels; functions build sentences that contain values.
Numbers and dates passed to the functions are already formatted.
"""

from __future__ import annotations

PAGE_TITLE = "Προγραμματισμός supply chain"

# ---------------------------------------------------------------- navigation
NAV_WAREHOUSE = "Αποθήκη"
NAV_PRODUCTS = "Προϊόντα"
NAV_ORDERS = "Παραγγελίες"
NAV_PRODUCTION = "Μηχανές και παραγωγή"
NAV_PACKAGING = "Συσκευασία"
NAV_MOVEMENTS = "Παραλαβές και αποστολές"
NAV_SETTINGS = "Ρυθμίσεις"

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
SAVE = "Αποθήκευση"
CANCEL = "Ακύρωση"
CONTINUE = "Συνέχεια"
EDIT = "Επεξεργασία"
DELETE = "Διαγραφή"
UNDO = "Αναίρεση"
SELECT_ROW_FIRST = "Επίλεξε πρώτα μια γραμμή"
NO_ROWS = "Δεν υπάρχουν γραμμές."
NOTHING_TO_UNDO = "Δεν υπάρχει ενέργεια για αναίρεση"
UNIT_KG = "kg"
UNIT_PCS = "τεμ."
UNIT_PIECES = "τεμάχια"
UNIT_BOXES = "κουτιά"
UNIT_DAYS = "ημέρες"
UNIT_HOURS = "ώρες"
UNIT_MINUTES = "λεπτά"
NOT_A_NUMBER = "Γράψε αριθμό, με κόμμα ή τελεία για τα δεκαδικά."
SAVED = "Η ενέργεια αποθηκεύτηκε."
UNDONE = "Η ενέργεια αναιρέθηκε."


def undo_label(description: str) -> str:
    return f"Αναίρεση: {description}"


def undo_confirm(description: str) -> str:
    return f"Θα αναιρεθεί: {description}. Συνέχεια;"


def parsed_as(value: str, unit: str = "") -> str:
    return f"= {value} {unit}".rstrip()


def field_required(field: str) -> str:
    return f"Το πεδίο «{field}» είναι υποχρεωτικό."


def field_positive(field: str) -> str:
    return f"Το πεδίο «{field}» πρέπει να είναι μεγαλύτερο από 0."


def field_not_negative(field: str) -> str:
    return f"Το πεδίο «{field}» δεν μπορεί να είναι αρνητικό."


def field_range(field: str, low: str, high: str) -> str:
    return f"Το πεδίο «{field}» πρέπει να είναι από {low} έως {high}."


def field_decimals(field: str) -> str:
    return f"Το πεδίο «{field}» έχει περισσότερα δεκαδικά από όσα επιτρέπονται."


def field_whole(field: str) -> str:
    return f"Το πεδίο «{field}» πρέπει να είναι ακέραιος αριθμός."


def action_failed(detail: str) -> str:
    return f"Η ενέργεια δεν ολοκληρώθηκε ({detail}). Έλεγξε τα στοιχεία και δοκίμασε ξανά."


# ---------------------------------------------------------------- statuses and labels
CATEGORY_RAW_MATERIAL = "Πρώτη ύλη"
CATEGORY_EXCIPIENT = "Έκδοχο"
CATEGORY_PACKAGING_MATERIAL = "Υλικό συσκευασίας"

EXPIRY_VALID = "Εντός ισχύος"
EXPIRY_EXPIRED = "Έληξε"
DEPLETED = "Εξαντλήθηκε"


def expires_in(days: int) -> str:
    return f"Λήγει σε {days} ημέρες"


STATUS_CANCELLED = "Ακυρώθηκε"
STATUS_SHIPPED = "Απεστάλη"
STATUS_TRANSFERRED = "Μεταφέρθηκε"
STATUS_ON_SHELF = "Στο ράφι"
STATUS_IN_PACKAGING = "Σε συσκευασία"
STATUS_IN_PRODUCTION = "Σε παραγωγή"
STATUS_READY = "Έτοιμη για παραγωγή"
STATUS_WAITING = "Περιμένει υλικά"
FLAG_NO_MACHINE = "Χωρίς μηχανή"
FLAG_NO_PACKAGING_PLAN = "Χωρίς σχεδιασμό συσκευασίας"
FLAG_MISSING_PACKAGING = "Λείπουν συσκευασίες"

RECEIPT_EXPECTED = "Αναμένεται"
RECEIPT_RECEIVED = "Παραλήφθηκε"


def receipt_delayed(days: int) -> str:
    return f"Καθυστερεί {days} ημέρες"


SHIPMENT_PENDING = "Αναμένει αποστολή"
SHIPMENT_SHIPPED = "Απεστάλη"

KIND_MATERIAL = "Υλικό"
KIND_PACKAGING = "Συσκευασία"
KIND_LABEL = "Ετικέτα"

STEP_LEVEL = "Package"
STEP_LABELLING = "Labelling"
ROLE_PRIMARY = "Συσκευασία προϊόντος"
ROLE_BOX = "Δοχείο συσκευασίας"
ROLE_CARTON = "Κιβώτιο"
ROLE_PALLET = "Παλέτα"
ROLE_OTHER = "Άλλο"

WEEKDAYS = ("Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή")

ORDER_NAME_PREFIX = "ORD-"

# ---------------------------------------------------------------- action errors


def code_exists(code: str) -> str:
    return f"Ο κωδικός {code} υπάρχει ήδη. Γράψε άλλον κωδικό."


def name_exists(name: str) -> str:
    return f"Το όνομα {name} υπάρχει ήδη. Γράψε άλλο όνομα."


def percent_total(total: str) -> str:
    return f"Τα ποσοστά δίνουν {total}%. Πρέπει να δίνουν 100%."


def duplicate_material(name: str) -> str:
    return f"Το υλικό {name} υπάρχει δύο φορές. Κάθε υλικό μπαίνει μία φορά."


PERCENT_POSITIVE = "Κάθε ποσοστό πρέπει να είναι μεγαλύτερο από 0."
OUTER_ONLY_FOR_CONTAINERS = "Εξωτερικές διαστάσεις έχουν μόνο τα κιβώτια και οι παλέτες."
NO_INNER_DIMENSIONS = "Οι ετικέτες και οι παλέτες δεν έχουν εσωτερικές διαστάσεις."
BREAKDOWN_ONLY_FOR_PACKAGING = "Ανάλυση υλικών έχουν μόνο οι συσκευασίες."
TYPE_LOCKED = "Ο τύπος ενός είδους δεν αλλάζει μετά τη δημιουργία του."

ITEM_TYPE_NAMES = {
    "packaging": "συσκευασία",
    "label": "ετικέτα",
    "carton": "κιβώτιο",
    "pallet": "παλέτα",
}


def wrong_item_type(step: int, expected: str) -> str:
    return f"Στο βήμα {step} διάλεξε {ITEM_TYPE_NAMES[expected]}."


def wrong_extra_type(step: int) -> str:
    return f"Τα πρόσθετα είδη του βήματος {step} πρέπει να είναι συσκευασίες ή ετικέτες."
RECIPE_EMPTY = "Πρόσθεσε τουλάχιστον ένα υλικό στη συνταγή."
BREAKDOWN_NEEDS_WEIGHT = "Η ανάλυση υλικών απαιτεί βάρος τεμαχίου."
DIMENSIONS_ALL_OR_NONE = "Συμπλήρωσε και τις τρεις διαστάσεις ή καμία."
NEGATIVE_STOCK = "Η ποσότητα ξεπερνά το απόθεμα."
PRODUCT_WITHOUT_RECIPE = "Το προϊόν δεν έχει αποθηκευμένη συνταγή."
PRODUCT_WITHOUT_WEIGHT = "Το προϊόν δεν έχει βάρος ανά τεμάχιο."
QUANTITY_LOCKED = "Η ποσότητα δεν αλλάζει μετά την ολοκλήρωση της πρώτης ανάθεσης."
CANCEL_LOCKED = "Η παραγγελία δεν ακυρώνεται, γιατί έχει ολοκληρωθεί ανάθεση παραγωγής."
ORDER_CLOSED = "Η παραγγελία είναι κλειστή και δεν αλλάζει."
PRODUCTION_DONE = "Η παραγωγή αυτής της παραγγελίας έχει ολοκληρωθεί."
WAITING_MATERIALS = "Η παραγγελία περιμένει υλικά. Δες τον πίνακα ελλείψεων."
ASSIGNMENT_DONE = "Η ανάθεση έχει ήδη ολοκληρωθεί."
PRODUCTION_NOT_DONE = "Η παραγωγή δεν έχει ολοκληρωθεί."
NO_PLAN = "Δεν υπάρχει σχεδιασμός συσκευασίας."
MISSING_PACKAGING = "Λείπουν συσκευασίες. Δες τον πίνακα απαιτήσεων."
PACKAGING_DONE = "Η συσκευασία αυτής της παραγγελίας έχει ολοκληρωθεί."
RECEIPT_ALREADY_RECEIVED = "Η παραλαβή έχει ήδη καταχωρηθεί ως παραληφθείσα και δεν αλλάζει."
SHIPMENT_ALREADY_SHIPPED = "Η αποστολή έχει ήδη σημειωθεί ως απεσταλμένη και δεν αλλάζει."
TRANSFER_MISMATCH = (
    "Η μεταφορά γίνεται μόνο σε γραμμή του ίδιου προϊόντος, με ίδια τεμάχια ανά κουτί "
    "και ίδια κουτιά ανά κιβώτιο."
)
TRANSFER_SAME_LINE = "Διάλεξε διαφορετική γραμμή προορισμού."
SHELF_NOT_EMPTY = "Η γραμμή ραφιού έχει ακόμα κουτιά. Διαγράφεται μόνο όταν τα κουτιά είναι 0."
RED_NOT_BELOW_YELLOW = "Το όριο κόκκινου πρέπει να είναι μικρότερο από το όριο κίτρινου."
NO_WORKING_DAYS = "Διάλεξε τουλάχιστον μία εργάσιμη ημέρα."
LOT_NUMBER_REQUIRED = "Γράψε LOT Number."
EXPIRY_REQUIRED = "Γράψε ημερομηνία λήξης."


def boxes_over_free(free: str) -> str:
    return f"Τα κουτιά ξεπερνούν τα ελεύθερα κουτιά ({free})."


def boxes_over_line(boxes: str) -> str:
    return f"Τα κουτιά ξεπερνούν τα κουτιά της γραμμής ραφιού ({boxes})."


def position_range(count: int) -> str:
    return f"Η θέση πρέπει να είναι από 1 έως {count}."


def assignment_sum(total: str, expected: str) -> str:
    return (
        f"Το άθροισμα των αναθέσεων ({total} kg) πρέπει να ισούται με την ποσότητα "
        f"που μένει να παραχθεί ({expected} kg)."
    )


def lot_not_empty(lot: str) -> str:
    return f"Το LOT {lot} έχει ακόμα ποσότητα. Διαγράφεται μόνο όταν η ποσότητα είναι 0."


def material_has_stock(name: str) -> str:
    return f"Το υλικό {name} έχει ακόμα απόθεμα. Διαγράφεται μόνο όταν όλα τα LOT είναι 0."


def material_in_recipe(material: str, product: str) -> str:
    return f"Το {material} ανήκει στη συνταγή του προϊόντος {product}."


def material_in_breakdown(material: str, item: str) -> str:
    return f"Το {material} ανήκει στην ανάλυση υλικών της συσκευασίας {item}."


def material_in_open_order(material: str, order: str) -> str:
    return f"Το {material} χρειάζεται για την ανοιχτή παραγγελία {order}."


def packaging_has_stock(name: str) -> str:
    return f"Η συσκευασία {name} έχει ακόμα τεμάχια. Διαγράφεται μόνο όταν η ποσότητα είναι 0."


def packaging_in_open_order(item: str, order: str) -> str:
    return f"Η συσκευασία {item} χρησιμοποιείται στη συσκευασία της ανοιχτής παραγγελίας {order}."


def product_has_orders(product: str, order: str) -> str:
    return f"Το προϊόν {product} έχει την παραγγελία {order}. Διαγράφεται μόνο αν δεν υπάρχει παραγγελία του."


def machine_in_open_order(machine: str, order: str) -> str:
    return f"Η μηχανή {machine} έχει ανάθεση στην ανοιχτή παραγγελία {order}."


PLAN_ISSUES = {
    "no_steps": "Πρόσθεσε τουλάχιστον ένα βήμα.",
    "labelling_before_level": "Ένα βήμα Labelling πρέπει να ακολουθεί ένα βήμα Package.",
    "level_without_role": "Κάθε βήμα Package χρειάζεται ρόλο.",
    "level_without_contents": "Συμπλήρωσε το «Περιέχει» σε κάθε βήμα Package.",
    "box_count": "Ο σχεδιασμός πρέπει να έχει ακριβώς ένα βήμα Package με ρόλο «Δοχείο συσκευασίας».",
    "carton_before_box": "Το κιβώτιο μπαίνει μετά το δοχείο συσκευασίας.",
    "multiple_cartons": "Ο σχεδιασμός έχει το πολύ ένα βήμα Package «Κιβώτιο».",
    "components_without_weight": "Μια συσκευασία με ανάλυση υλικών δεν έχει βάρος τεμαχίου.",
    "non_positive_speed": "Τα κομμάτια ανά λεπτό πρέπει να είναι μεγαλύτερα από 0.",
    "non_positive_extra": "Η ποσότητα κάθε πρόσθετου είδους πρέπει να είναι μεγαλύτερη από 0.",
    "too_many_steps": "Ο σχεδιασμός έχει το πολύ 10 βήματα.",
    "pallet_without_carton": "Η παλέτα μπαίνει μετά το κιβώτιο.",
    "multiple_pallets": "Ο σχεδιασμός έχει το πολύ ένα βήμα Package «Παλέτα».",
    "level_after_pallet": "Μετά την παλέτα μπαίνει μόνο labelling.",
}

# ---------------------------------------------------------------- confirmations (4.12)


def loses_materials(order: str) -> str:
    return f"Η παραγγελία {order} θα επιστρέψει σε Περιμένει υλικά. Συνέχεια;"


def loses_materials_started(order: str, start: str) -> str:
    return (
        f"Η παραγγελία {order} έχει ημερομηνία έναρξης {start} και πιθανόν παράγεται ήδη. "
        "Θέλεις σίγουρα να της αφαιρεθούν τα υλικά;"
    )


def expired_lot_consumed(lot: str, expiry: str) -> str:
    return f"Το LOT {lot} έληξε στις {expiry}. Καταναλώθηκε σε αυτή την παραγωγή;"


ACTUAL_OVER_PLANNED = "Τα πραγματικά τεμάχια ξεπερνούν τα προγραμματισμένα. Έλεγξε τον αριθμό."

# ---------------------------------------------------------------- warnings (4.12)


def warn_start_before_receipt(material: str, day: str) -> str:
    return f"Η έναρξη είναι πριν από την αναμενόμενη παραλαβή του {material} στις {day}."


def warn_no_covering_receipt(material: str, missing: str) -> str:
    return f"Δεν υπάρχει αναμενόμενη παραλαβή που να καλύπτει το υλικό {material}. Λείπουν {missing}."


def warn_arrival_after_delivery(arrival: str, delivery: str) -> str:
    return f"Η εκτιμώμενη άφιξη ({arrival}) είναι μετά την ημερομηνία παράδοσης ({delivery})."


def warn_red_lot(lot: str, material: str, days: int) -> str:
    return f"Το LOT {lot} του υλικού {material} λήγει σε {days} ημέρες."


# ---------------------------------------------------------------- history descriptions (11.3)


def h_material_created(name: str) -> str:
    return f"Νέο υλικό: {name}"


def h_material_updated(name: str) -> str:
    return f"Διόρθωση υλικού: {name}"


def h_material_deleted(name: str) -> str:
    return f"Διαγραφή υλικού: {name}"


def h_lot_created(lot: str, material: str, quantity: str) -> str:
    return f"Νέο LOT: {lot}, {material}, {quantity} kg"


def h_lot_quantity(lot: str, old: str, new: str) -> str:
    return f"Διόρθωση ποσότητας: LOT {lot} από {old} kg σε {new} kg"


def h_lot_updated(lot: str) -> str:
    return f"Διόρθωση LOT: {lot}"


def h_lot_deleted(lot: str) -> str:
    return f"Διαγραφή LOT: {lot}"


def h_packaging_created(name: str) -> str:
    return f"Νέα συσκευασία: {name}"


def h_packaging_updated(name: str) -> str:
    return f"Διόρθωση συσκευασίας: {name}"


def h_packaging_quantity(name: str, old: str, new: str) -> str:
    return f"Διόρθωση ποσότητας: {name} από {old} σε {new} τεμάχια"


def h_packaging_deleted(name: str) -> str:
    return f"Διαγραφή συσκευασίας: {name}"


def h_product_created(name: str) -> str:
    return f"Νέο προϊόν: {name}"


def h_product_updated(name: str) -> str:
    return f"Διόρθωση προϊόντος: {name}"


def h_product_deleted(name: str) -> str:
    return f"Διαγραφή προϊόντος: {name}"


def h_order_created(order: str, product: str, quantity: str) -> str:
    return f"Νέα παραγγελία: {order}, {product}, {quantity} kg"


def h_order_updated(order: str) -> str:
    return f"Διόρθωση παραγγελίας: {order}"


def h_sequence(order: str, old: int, new: int) -> str:
    return f"Αλλαγή σειράς: {order} από τη θέση {old} στη θέση {new}"


def h_order_cancelled(order: str) -> str:
    return f"Ακύρωση παραγγελίας: {order}"


def h_machine_created(name: str) -> str:
    return f"Νέα μηχανή: {name}"


def h_machine_updated(name: str) -> str:
    return f"Διόρθωση μηχανής: {name}"


def h_machine_deleted(name: str) -> str:
    return f"Διαγραφή μηχανής: {name}"


def h_assignments(order: str) -> str:
    return f"Ανάθεση σε μηχανή: {order}"


def h_production_completed(order: str, machine: str, pieces: str) -> str:
    return f"Ολοκληρώθηκε παραγωγή: {order}, {machine}, {pieces} τεμάχια"


def h_packaging_plan(order: str) -> str:
    return f"Σχεδιασμός συσκευασίας: {order}"


def h_packaging_completed(order: str, boxes: str, leftovers: list[str]) -> str:
    text = f"Ολοκληρώθηκε συσκευασία: {order}, {boxes} κουτιά"
    if leftovers:
        text += ", υπόλοιπο " + " και ".join(leftovers)
    return text


def h_receipt_created(item: str, quantity: str) -> str:
    return f"Νέα παραλαβή: {item}, {quantity}"


def h_receipt_updated(item: str) -> str:
    return f"Διόρθωση παραλαβής: {item}"


def h_receipt_deleted(item: str) -> str:
    return f"Διαγραφή παραλαβής: {item}"


def h_received(item: str, quantity: str, lot: str | None) -> str:
    text = f"Παραλήφθηκε: {item}, {quantity}"
    return f"{text}, LOT {lot}" if lot else text


def h_shipment_created(product: str, order: str, boxes: str) -> str:
    return f"Νέα αποστολή: {product}, {order}, {boxes} κουτιά"


def h_shipment_updated(product: str, order: str) -> str:
    return f"Διόρθωση αποστολής: {product}, {order}"


def h_shipment_deleted(product: str, order: str) -> str:
    return f"Διαγραφή αποστολής: {product}, {order}"


def h_shipped(product: str, order: str, boxes: str) -> str:
    return f"Απεστάλη: {product}, {order}, {boxes} κουτιά"


def h_transfer(boxes: str, product: str, source: str, target: str) -> str:
    return f"Μεταφορά: {boxes} κουτιά {product} από {source} σε {target}"


def h_shelf_deleted(product: str, order: str) -> str:
    return f"Διαγραφή γραμμής ραφιού: {product}, {order}"


H_SETTINGS = "Αλλαγή ρυθμίσεων"

# ---------------------------------------------------------------- shared screen texts
REMOVE = "Αφαίρεση"
CONFIRM_DELETE_TITLE = "Διαγραφή"
UNIT_FIXED_KG = "Μονάδα Μέτρησης: kg"
OPTIONAL = "προαιρετικό"


def confirm_delete(name: str) -> str:
    return f"Θα διαγραφεί: {name}. Συνέχεια;"


def expected_entry(quantity: str, day: str) -> str:
    return f"+{quantity} στις {day}"


def percent_sum(total: str) -> str:
    return f"Σύνολο ποσοστών: {total}%"


# ---------------------------------------------------------------- tab 1: warehouse
WH_MATERIALS = "Υλικά"
WH_LOTS = "LOT"
WH_PACKAGING = "Συσκευασίες"
WH_SHELF = "Έτοιμα προϊόντα"
WH_ADD_MATERIAL = "(+) Προσθήκη Υλικού"
WH_ADD_LOT = "(+) Προσθήκη LOT"
WH_EDIT_LOT = "Επεξεργασία LOT"
WH_DELETE_LOT = "Διαγραφή LOT"
WH_ADD_PACKAGING = "(+) Προσθήκη Συσκευασίας"
WH_ADD_CONTAINER = "(+) Προσθήκη Κιβωτίου/Παλέτας"
WH_LABELS = "Ετικέτες"
WH_ADD_LABEL = "(+) Προσθήκη Ετικέτας"
COL_OUTER_DIMENSIONS = "Εξωτερικές διαστάσεις (cm)"
CARTON_DIMENSIONS_NOTE = "Στα κιβώτια, οι «Διαστάσεις» είναι οι εσωτερικές. Οι παλέτες έχουν μόνο εξωτερικές: βάση και μέγιστο ύψος φόρτωσης."
F_CONTAINER_TYPE = "Τύπος"
F_INNER_DIMENSIONS = "Εσωτερικές διαστάσεις"
F_OUTER_DIMENSIONS = "Εξωτερικές διαστάσεις"
INNER_DIMENSIONS_HELP = "Για τον υπολογισμό των δοχείων συσκευασίας που χωράνε στο κιβώτιο."
OUTER_DIMENSIONS_HELP = "Για τον υπολογισμό των κιβωτίων που χωράνε στην παλέτα."
PALLET_DIMENSIONS_HELP = "Η βάση της παλέτας και το μέγιστο ύψος φόρτωσης."
F_PALLET_LENGTH = "Μήκος βάσης (cm)"
F_PALLET_WIDTH = "Πλάτος βάσης (cm)"
F_PALLET_HEIGHT = "Μέγιστο ύψος φόρτωσης (cm)"
T_NEW_CONTAINER = "Νέο κιβώτιο ή παλέτα"
T_EDIT_CONTAINER = "Επεξεργασία κιβωτίου ή παλέτας"
T_NEW_LABEL = "Νέα ετικέτα"
T_EDIT_LABEL = "Επεξεργασία ετικέτας"
WH_TRANSFER = "Μεταφορά"

COL_CODE = "Κωδικός"
COL_NAME = "Όνομα"
COL_CATEGORY = "Κατηγορία"
COL_TOTAL_KG = "Σύνολο (kg)"
COL_RESERVED_KG = "Δεσμευμένο (kg)"
COL_AVAILABLE_KG = "Διαθέσιμο (kg)"
COL_EXPECTED = "Αναμενόμενο"
COL_INDICATOR = "Ένδειξη"
COL_MATERIAL = "Υλικό"
COL_LOT_NUMBER = "LOT Number"
COL_QUANTITY_KG = "Ποσότητα (kg)"
COL_EXPIRY = "Ημερομηνία λήξης"
COL_DAYS_LEFT = "Απομένουν"
COL_STATUS = "Κατάσταση"
COL_DIMENSIONS = "Διαστάσεις (cm)"
COL_BREAKDOWN = "Ανάλυση υλικών"
COL_TOTAL_PCS = "Σύνολο (τεμ.)"
COL_RESERVED_PCS = "Δεσμευμένο (τεμ.)"
COL_AVAILABLE_PCS = "Διαθέσιμο (τεμ.)"
COL_PRODUCT = "Προϊόν"
COL_ORDER = "Παραγγελία"
COL_DESTINATION = "Προορισμός"
COL_BOXES = "Κουτιά"
COL_PIECES_PER_BOX = "Τεμάχια ανά κουτί"
COL_CARTONS = "Κιβώτια"
COL_BOXES_PER_CARTON = "Κουτιά ανά κιβώτιο"
COL_LOOSE_BOXES = "Κουτιά χύμα"
COL_PENDING_BOXES = "Προς αποστολή"
COL_FREE_BOXES = "Ελεύθερα κουτιά"
COL_DELIVERY = "Παράδοση"
COL_SHIP_BY = "Αποστολή έως"
COL_TRANSFERS = "Μεταφορές"

IMPORTED = "Εισαγόμενη"

F_MATERIAL_NAME = "Όνομα Υλικού"
F_CODE = "Κωδικός"
F_CATEGORY = "Κατηγορία"
F_DESCRIPTION = "Περιγραφή"
F_FIRST_LOT = "Πρώτο LOT (προαιρετικό)"
F_LOT_NUMBER = "LOT Number"
F_QUANTITY_KG = "Ποσότητα (kg)"
F_EXPIRY = "Ημερομηνία λήξης"
F_NAME = "Όνομα"
F_QUANTITY_PCS = "Ποσότητα (τεμάχια)"
F_LENGTH = "Μήκος (cm)"
F_WIDTH = "Πλάτος (cm)"
F_HEIGHT = "Ύψος (cm)"
DIMENSIONS_HELP = "Συμπληρώνονται και τα τρία ή κανένα."
F_UNIT_WEIGHT_G = "Βάρος τεμαχίου (g)"
F_BREAKDOWN = "Ανάλυση υλικών (προαιρετική)"
F_PERCENT = "Ποσοστό (%)"
ADD_BREAKDOWN_LINE = "(+) Προσθήκη υλικού"
F_TARGET_LINE = "Γραμμή προορισμού"
F_BOXES = "Κουτιά"
NO_COMPATIBLE_LINE = "Δεν υπάρχει άλλη γραμμή του ίδιου προϊόντος με ίδια τεμάχια ανά κουτί και ίδια κουτιά ανά κιβώτιο."

T_NEW_MATERIAL = "Νέο υλικό"
T_EDIT_MATERIAL = "Επεξεργασία υλικού"
T_NEW_LOT = "Νέο LOT"
T_EDIT_LOT = "Επεξεργασία LOT"
T_NEW_PACKAGING = "Νέα συσκευασία"
T_EDIT_PACKAGING = "Επεξεργασία συσκευασίας"
T_TRANSFER = "Μεταφορά κουτιών"


def free_boxes_note(boxes: str) -> str:
    return f"Ελεύθερα κουτιά στη γραμμή προέλευσης: {boxes}"


def transfer_entry(boxes: str, direction: str, destination: str, day: str) -> str:
    return f"{boxes} κουτιά {direction} {destination} στις {day}"


TRANSFER_TO = "προς"
TRANSFER_FROM = "από"


def breakdown_text(parts: str, weight: str) -> str:
    return f"{parts}, {weight} g"


# ---------------------------------------------------------------- tab 2: products
PR_ADD = "(+) Προσθήκη Προϊόντος"
COL_WEIGHT_G = "Βάρος ανά τεμάχιο (g)"
COL_MATERIAL_COUNT = "Υλικά"
COL_PRODUCIBLE_KG = "Διαθέσιμη ποσότητα (kg)"
COL_IN_PIECES = "Σε τεμάχια"
COL_LIMITING = "Περιοριστικό υλικό"
COL_PERCENT = "Ποσοστό"
COL_AVAILABLE = "Διαθέσιμο"
COL_ENOUGH_FOR = "Φτάνει για"
COL_CONSUMED = "Καταναλώνεται"
COL_LEFTOVER = "Περισσεύει"
LIMITING_MARK = "(περιοριστικό)"
F_PRODUCT_NAME = "Ονομασία"
F_WEIGHT_PER_PIECE = "Βάρος ανά τεμάχιο (g)"
F_RECIPE = "Συνταγή"
ADD_RECIPE_LINE = "(+) Προσθήκη Υλικού"
NEW_MATERIAL_INLINE = "Νέο υλικό"
CREATE_MATERIAL = "Δημιουργία υλικού"
T_NEW_PRODUCT = "Νέο προϊόν"
T_EDIT_PRODUCT = "Επεξεργασία προϊόντος"
PRODUCT_SHEET = "Φύλλο προϊόντος"
NO_RECIPE = "Το προϊόν δεν έχει συνταγή."


def producible_summary(quantity: str) -> str:
    return f"Διαθέσιμη ποσότητα προϊόντος: {quantity} kg."


def pieces_summary(pieces: str, weight: str) -> str:
    return f"Αντιστοιχεί σε {pieces} τεμάχια, με βάρος τεμαχίου {weight} g."


def limiting_summary(material: str) -> str:
    return f"Περιοριστικό υλικό: {material}."

# ---------------------------------------------------------------- tab 3: orders
OR_NEW = "(+) Νέα Παραγγελία"
OR_SEQUENCE = "Αλλαγή σειράς"
OR_CANCEL = "Ακύρωση παραγγελίας"
OR_SHOW_CLOSED = "Εμφάνιση κλειστών παραγγελιών"
COL_SEQUENCE = "Σειρά"
COL_START = "Έναρξη"
COL_READINESS = "Εκτιμώμενη ετοιμότητα"
COL_WARNINGS = "Προειδοποιήσεις"
COL_NEED = "Χρειάζεται"
COL_MISSING = "Λείπει"
COL_DAYS_TO_EXPIRY = "Λήγει σε (ημέρες)"
F_PRODUCT = "Προϊόν"
F_ORDER_QUANTITY = "Ποσότητα (kg)"
F_ORDER_NAME = "Όνομα"
F_DESTINATION = "Προορισμός"
F_DELIVERY = "Ημερομηνία παράδοσης"
F_TRANSIT = "Ημέρες μεταφοράς"
F_NEW_POSITION = "Νέα θέση"
SAVE_REDUCED = "Μείωση στη διαθέσιμη ποσότητα"
SAVE_WAITING = "Αποθήκευση ως Περιμένει υλικά"
T_NEW_ORDER = "Νέα παραγγελία"
T_EDIT_ORDER = "Επεξεργασία παραγγελίας"
T_SEQUENCE = "Αλλαγή σειράς"
T_CANCEL_ORDER = "Ακύρωση παραγγελίας"
DETAILS_SHORTAGES = "Πίνακας ελλείψεων"
DETAILS_LOTS = "LOT κατανάλωσης"
DETAILS_ASSIGNMENTS = "Αναθέσεις σε μηχανές"
DETAILS_PACKAGING = "Συσκευασία"
DETAILS_WARNINGS = "Προειδοποιήσεις"
NO_SHORTAGE_LINES = "Η παραγωγή έχει ολοκληρωθεί. Δεν χρειάζονται άλλα υλικά συνταγής."
NO_LOTS = "Η παραγγελία δεν έχει δεσμευμένα υλικά, άρα δεν υπάρχουν LOT κατανάλωσης."
NO_ASSIGNMENTS = "Δεν υπάρχει ανάθεση σε μηχανή."
NO_WARNINGS = "Δεν υπάρχουν προειδοποιήσεις."
NO_START = "Δεν έχει οριστεί έναρξη"
WITHOUT_PACKAGING = "χωρίς συσκευασία"
QUANTITY_LOCKED_NOTE = "Η ποσότητα δεν αλλάζει, γιατί έχει ολοκληρωθεί ανάθεση."


def available_today(quantity: str) -> str:
    return f"Διαθέσιμη ποσότητα προϊόντος σήμερα: {quantity} kg"


def order_details(name: str) -> str:
    return f"Λεπτομέρειες παραγγελίας: {name}"


def confirm_cancel(order: str) -> str:
    return f"Η παραγγελία {order} θα ακυρωθεί και τα υλικά της θα αποδεσμευτούν. Συνέχεια;"


def current_position(position: int, count: int) -> str:
    return f"Τρέχουσα θέση: {position} από {count}"


def packaging_summary(boxes: str, cartons: str, days: str) -> str:
    return f"{boxes} κουτιά, {cartons} κιβώτια, {days} ημέρες συσκευασίας"


def assignment_summary(machine: str, quantity: str, days: str, pieces: str) -> str:
    return f"{machine}: {quantity} kg, {days} ημέρες παραγωγής, {pieces} αναμενόμενα τεμάχια"


# ---------------------------------------------------------------- tab 4: machines and production
MA_TITLE = "Μηχανές"
MA_ADD = "(+) Προσθήκη Μηχανής"
PO_TITLE = "Παραγγελίες προς παραγωγή"
PO_ASSIGN = "Ανάθεση σε μηχανή"
PO_INVERSE = "Αντίστροφος υπολογισμός"
PO_COMPLETE = "Ολοκληρώθηκε"
PO_DONE_TITLE = "Ολοκληρωμένες παραγωγές"
COL_MACHINE = "Μηχανή"
COL_BATCH_KG = "Batch size (kg)"
COL_CYCLE = "Cycle time (λεπτά)"
COL_UTILIZATION = "Effective utilization (%)"
COL_HOURS_PER_DAY = "Ώρες λειτουργίας ανά ημέρα"
COL_MAX_BATCH = "Μέγιστο batch (kg)"
COL_MIN_CYCLE = "Ελάχιστος cycle time (λεπτά)"
COL_ASSIGNED_KG = "Ποσότητα ανάθεσης (kg)"
COL_BATCHES = "Παρτίδες"
COL_TIME_HOURS = "Χρόνος (ώρες)"
COL_PRODUCTION_DAYS = "Ημέρες παραγωγής"
COL_PRODUCTION_END = "Τέλος παραγωγής"
COL_PLANNED = "Προγραμματισμένα τεμάχια"
COL_EXPECTED_PIECES = "Αναμενόμενα τεμάχια"
COL_ACTUAL = "Πραγματικά τεμάχια"
COL_COMPLETED_ON = "Ημερομηνία ολοκλήρωσης"
F_MACHINE_NAME = "Όνομα"
F_BATCH = "Batch size (kg)"
F_CYCLE = "Cycle time (λεπτά)"
F_UTILIZATION = "Effective utilization (%)"
UTILIZATION_HELP = "Παράδειγμα: 6,4 παραγωγικές ώρες σε 8 ώρες λειτουργίας δίνουν 80%"
F_HOURS = "Ώρες λειτουργίας ανά ημέρα"
F_MAX_BATCH = "Μέγιστο batch (kg)"
F_MIN_CYCLE = "Ελάχιστος cycle time (λεπτά)"
F_MACHINE = "Μηχανή"
F_DEFECTS = "Ποσοστό ελαττωματικών (%)"
DEFECTS_HELP = "Η τιμή δίνεται από το QC και την παραγωγή."
F_START = "Ημερομηνία έναρξης"
ADD_MACHINE_SHARE = "Προσθήκη μηχανής"
F_TARGET_DAYS = "Ημέρες παραγωγής που θέλεις"
F_ACTUAL_PIECES = "Πραγματικά τεμάχια"
T_NEW_MACHINE = "Νέα μηχανή"
T_EDIT_MACHINE = "Επεξεργασία μηχανής"
T_ASSIGN = "Ανάθεση σε μηχανή"
T_INVERSE = "Αντίστροφος υπολογισμός"
T_COMPLETE_PRODUCTION = "Ολοκλήρωση παραγωγής"
R_BATCHES = "Παρτίδες"
R_NET = "Καθαρός χρόνος"
R_OPERATING = "Χρόνος λειτουργίας"
R_DAYS = "Ημέρες παραγωγής"
R_PER_BATCH = "Τεμάχια ανά παρτίδα"
R_PLANNED = "Προγραμματισμένα τεμάχια"
R_EXPECTED = "Αναμενόμενα τεμάχια"
R_DEFECTS = "Αναμενόμενα ελαττωματικά"
R_END = "Τέλος παραγωγής"
COL_IF_ONLY = "Αν αλλάξει μόνο"
COL_FROM = "Από"
COL_TO = "Σε"
COL_CHANGE = "Μεταβολή"
COL_LIMIT = "Όριο"
COL_RESULT = "Αποτέλεσμα"
COL_VALUE = "Τιμή"
LEVER_CYCLE = "Cycle time"
LEVER_BATCH = "Batch size"
LEVER_HOURS = "Ώρες ανά ημέρα"
FEASIBLE = "Εφικτό"
INFEASIBLE = "Ανέφικτο"
LIMIT_MIN = "Ελάχιστο"
LIMIT_MAX = "Μέγιστο"
REASON_24 = "πάνω από 24 ώρες ανά ημέρα"
REASON_MAX_BATCH = "πάνω από το μέγιστο batch της μηχανής"
REASON_MIN_CYCLE = "κάτω από τον ελάχιστο cycle time της μηχανής"
INVERSE_NOTE = "Ο υπολογισμός είναι ενημερωτικός. Καμία τιμή δεν αλλάζει αυτόματα."
NO_MACHINES = "Πρόσθεσε πρώτα μια μηχανή."
SELECT_ASSIGNMENT_FIRST = "Επίλεξε πρώτα μια γραμμή με μηχανή."


def current_days(days: str) -> str:
    return f"Τρέχων χρόνος παραγωγής: {days} ημέρες"


def share_title(number: int) -> str:
    return f"Μηχανή {number}"


def remaining_note(quantity: str) -> str:
    return f"Ποσότητα προς παραγωγή: {quantity} kg"

WARN_SHORT_START = "Έναρξη πριν από την παραλαβή"
WARN_SHORT_ARRIVAL = "Άφιξη μετά την παράδοση"
WARN_SHORT_RED_LOT = "Κόκκινο LOT"


def warn_short_no_receipt(material: str) -> str:
    return f"Χωρίς παραλαβή για {material}"

# ---------------------------------------------------------------- tab 5: packaging
PK_PLAN = "Σχεδιασμός συσκευασίας"
PK_COMPLETE = "Ολοκληρώθηκε"
COL_PIECES = "Τεμάχια"
COL_BASIS = "Βάση υπολογισμού"
COL_PLAN = "Σχεδιασμός"
COL_PACKAGING_DAYS = "Ημέρες συσκευασίας"
COL_INDICATIONS = "Ενδείξεις"
COL_STEP = "Βήμα"
COL_CONTAINS = "Περιέχει"
COL_COMES_READY = "Έρχεται έτοιμο"
COL_UNITS = "Μονάδες"
COL_REMAINDER = "Υπόλοιπο"
COL_PER_MINUTE = "Ανά λεπτό"
COL_NET_TIME = "Καθαρός χρόνος"
COL_ITEM = "Είδος"
YES = "Ναι"
NO = "Όχι"
BASIS_EXPECTED = "Αναμενόμενα"
BASIS_ACTUAL = "Πραγματικά"
BASIS_WITHOUT_DEFECTS = "Αναμενόμενα, χωρίς ποσοστό ελαττωματικών"
CALC_WITH_EXPECTED = "Υπολογισμός με αναμενόμενα τεμάχια"
CALC_WITH_ACTUAL = "Υπολογισμός με πραγματικά τεμάχια"
CALC_WITHOUT_DEFECTS = "Υπολογισμός με τεμάχια χωρίς ποσοστό ελαττωματικών"
F_PACK_HOURS = "Ώρες λειτουργίας ανά ημέρα"
F_PACK_UTILIZATION = "Effective utilization (%)"
F_STEP_KIND = "Είδος βήματος"
F_ROLE = "Ρόλος"
F_PACKAGING_ITEM = "Συσκευασία"
F_CONTAINS = "Περιέχει"
F_COMES_READY = "Έρχεται έτοιμο"
F_SPEED = "Κομμάτια ανά λεπτό"
F_EXTRAS = "Πρόσθετα είδη"
F_EXTRA_QUANTITY = "Ποσότητα ανά μονάδα"
ADD_EXTRA = "(+) Προσθήκη πρόσθετου είδους"
ADD_STEP = "(+) Προσθήκη βήματος"
F_FIT = "Τοποθέτηση κουτιών στο κιβώτιο"
F_FIT_PALLET = "Τοποθέτηση κιβωτίων στην παλέτα"
UNIT_CARTONS = "κιβώτια"
COL_PALLETS = "Παλέτες"
MAX_STEPS_NOTE = "Ο σχεδιασμός έχει ήδη 10 βήματα, το μέγιστο."
ITEM_FIELD_LABELS = {
    "packaging": "Συσκευασία",
    "label": "Ετικέτα",
    "carton": "Κιβώτιο",
    "pallet": "Παλέτα",
}
CUSTOM_NUMBER = "Δικός μου αριθμός"
SAVE_PLAN = "Αποθήκευση σχεδιασμού"
T_PLAN = "Σχεδιασμός συσκευασίας"
T_COMPLETE_PACKAGING = "Ολοκλήρωση συσκευασίας"
STEPS_TABLE = "Πίνακας βημάτων"
NEEDS_TABLE = "Πίνακας απαιτήσεων"
NO_PIECES = "Δεν υπάρχουν τεμάχια για υπολογισμό. Έλεγξε το βάρος τεμαχίου της παραγγελίας."
NO_PACKAGING_ITEMS = "Πρόσθεσε πρώτα συσκευασίες στην Αποθήκη."
WILL_DEDUCT = "Θα αφαιρεθούν από την Αποθήκη:"
WILL_SHELVE = "Θα δημιουργηθεί η γραμμή στο ράφι με:"


def step_number(number: int) -> str:
    return f"Βήμα {number}"


def labelling_of(item: str) -> str:
    return f"Labelling: {item}"


def contains_pieces(count: str) -> str:
    return f"{count} τεμάχια"


def contains_units(count: str, name: str) -> str:
    return f"{count} {name}"


def fit_option(orientation: str, per_axis: str, count: str, unit: str = "κουτιά") -> str:
    return f"{orientation} cm: {per_axis} = {count} {unit}"


def last_pallet_note(cartons: str) -> str:
    return f"η τελευταία με {cartons} κιβώτια"


def pallets_cell(pallets: str, last_cartons: str | None) -> str:
    """E.g. "13 παλέτες (η τελευταία με 5 κιβώτια)"."""
    text = f"{pallets} παλέτες"
    return f"{text} ({last_pallet_note(last_cartons)})" if last_cartons else text


def limiting_packaging(item: str, boxes: str) -> str:
    return f"Περιορίζει η συσκευασία {item}. Με τα διαθέσιμα συσκευάζονται {boxes} κουτιά."


def sequential_time(days: str) -> str:
    return f"Διαδοχικά: {days} ημέρες"


def inline_time(days: str) -> str:
    return f"Σε γραμμή: {days} ημέρες"


def readiness_estimate(day: str) -> str:
    return f"Εκτιμώμενη ετοιμότητα: {day}"


def arrival_estimate(day: str) -> str:
    return f"Εκτιμώμενη άφιξη: {day}"


def shelf_preview(boxes: str, per_box: str, per_carton: str) -> str:
    return f"{boxes} κουτιά των {per_box} τεμαχίων, {per_carton} κουτιά ανά κιβώτιο"

# ---------------------------------------------------------------- tab 6: receipts and shipments
RC_TITLE = "Παραλαβές"
RC_ADD = "(+) Προσθήκη Παραλαβής"
RC_RECEIVED = "Παραλήφθηκε"
READY_TITLE = "Έτοιμα για αποστολή"
SH_TITLE = "Αποστολές"
SH_ADD = "(+) Προσθήκη Αποστολής"
SH_SHIPPED = "Απεστάλη"
COL_TYPE = "Τύπος"
COL_KIND_ITEM = "Είδος"
COL_QUANTITY = "Ποσότητα"
COL_RECEIVED = "Παραλήφθηκε"
COL_RECEIVED_QUANTITY = "Παραληφθείσα ποσότητα"
COL_RECEIPT_DATE = "Ημερομηνία παραλαβής"
COL_ORDER_AND_DESTINATION = "Παραγγελία και προορισμός"
COL_SHIPPED = "Απεστάλη"
COL_COMPLETION_DATE = "Ημερομηνία ολοκλήρωσης"
COL_SHIPMENT_DATE = "Ημερομηνία αποστολής"
F_TYPE = "Τύπος"
F_ITEM = "Είδος"
F_QUANTITY = "Ποσότητα"
F_RECEIPT_DATE = "Ημερομηνία παραλαβής"
F_SHELF_LINE = "Γραμμή ραφιού"
F_COMPLETION_DATE = "Ημερομηνία ολοκλήρωσης"
F_SHIPMENT_DATE = "Ημερομηνία αποστολής"
T_NEW_RECEIPT = "Νέα παραλαβή"
T_EDIT_RECEIPT = "Επεξεργασία παραλαβής"
T_RECEIVED = "Παραλαβή"
T_NEW_SHIPMENT = "Νέα αποστολή"
T_EDIT_SHIPMENT = "Επεξεργασία αποστολής"
T_SHIPPED = "Αποστολή"
WAITING_FOR_ITEM = "Παραγγελίες που περιμένουν αυτό το είδος"
NO_WAITING_ORDERS = "Καμία παραγγελία δεν περιμένει αυτό το είδος."
NO_FREE_LINES = "Δεν υπάρχει γραμμή ραφιού με ελεύθερα κουτιά."
NEW_ITEM_HINT = "Αν το είδος δεν υπάρχει, πρόσθεσέ το πρώτα στην Αποθήκη, με «(+) Προσθήκη Υλικού» ή «(+) Προσθήκη Συσκευασίας»."


def unit_of(unit: str) -> str:
    return f"Μονάδα: {unit}"


def cartons_note(boxes: str, cartons: str, per_carton: str) -> str:
    return f"{boxes} κουτιά: {cartons} κιβώτια των {per_carton} κουτιών"


def cartons_cell(full: str, dims: str, loose: str) -> str:
    text = f"{full} γεμάτα"
    if dims:
        text += f", {dims} cm"
    return f"{text}, και {loose} κουτιά χύμα"


def boxes_cell(boxes: str, dims: str) -> str:
    return f"{boxes} τεμάχια, {dims} cm" if dims else f"{boxes} τεμάχια"


# ---------------------------------------------------------------- settings
ST_SETTINGS = "Ρυθμίσεις"
ST_HISTORY = "Ιστορικό"
ST_BACKUP = "Αντίγραφο ασφαλείας"
F_YELLOW = "Όριο κίτρινου (ημέρες)"
F_RED = "Όριο κόκκινου (ημέρες)"
F_WORKING_DAYS = "Εργάσιμες ημέρες"
F_MACHINE_HOURS = "Ώρες λειτουργίας ανά εργάσιμη ημέρα"
F_MACHINE_HOURS_HELP = "Προεπιλογή σε νέα μηχανή. Κάθε μηχανή κρατά τις δικές της ώρες, που αλλάζουν στη δημιουργία και στην επεξεργασία της."
F_DEFAULT_TRANSIT = "Ημέρες μεταφοράς"
F_DEFAULT_TRANSIT_HELP = "Προεπιλογή σε νέα παραγγελία."
F_PACKAGING_HOURS = "Ώρες συσκευασίας ανά ημέρα"
F_PACKAGING_UTILIZATION = "Utilization συσκευασίας (%)"
F_PACKAGING_DEFAULTS_HELP = "Προεπιλογή σε νέο σχεδιασμό συσκευασίας."
SAVE_SETTINGS = "Αποθήκευση ρυθμίσεων"
COL_WHEN = "Ημερομηνία και ώρα"
COL_ACTION = "Ενέργεια"
COL_DESCRIPTION = "Περιγραφή"
COL_UNDONE = "Αναιρέθηκε"


ST_WIPE = "Ολική εκκαθάριση"
WIPE_NOTE = "Διαγράφει όλα τα δεδομένα και τις πληροφορίες της εφαρμογής. Πριν τη διαγραφή αποθηκεύεται αυτόματα αντίγραφο ασφαλείας."
WIPE_CONFIRM = (
    "Θα διαγραφούν όλα τα δεδομένα: υλικά, LOT, συσκευασίες, προϊόντα, παραγγελίες, μηχανές, "
    "παραλαβές, αποστολές, ράφι και ιστορικό. Οι ρυθμίσεις επιστρέφουν στις προεπιλογές. "
    "Η ενέργεια δεν αναιρείται. Πριν τη διαγραφή αποθηκεύεται αυτόματα αντίγραφο ασφαλείας "
    "στον φάκελο backups. Συνέχεια;"
)


def wipe_done(path: str) -> str:
    return f"Η εφαρμογή καθαρίστηκε. Το αντίγραφο ασφαλείας αποθηκεύτηκε στο {path}."


def backup_done(path: str) -> str:
    return f"Το αντίγραφο αποθηκεύτηκε στο {path}."

ACTION_LABELS = {
    "material_create": "Νέο υλικό",
    "material_update": "Διόρθωση υλικού",
    "material_delete": "Διαγραφή υλικού",
    "lot_create": "Νέο LOT",
    "lot_update": "Διόρθωση LOT",
    "lot_delete": "Διαγραφή LOT",
    "packaging_create": "Νέα συσκευασία",
    "packaging_update": "Διόρθωση συσκευασίας",
    "packaging_delete": "Διαγραφή συσκευασίας",
    "product_create": "Νέο προϊόν",
    "product_update": "Διόρθωση προϊόντος",
    "product_delete": "Διαγραφή προϊόντος",
    "order_create": "Νέα παραγγελία",
    "order_update": "Διόρθωση παραγγελίας",
    "order_sequence": "Αλλαγή σειράς",
    "order_cancel": "Ακύρωση παραγγελίας",
    "machine_create": "Νέα μηχανή",
    "machine_update": "Διόρθωση μηχανής",
    "machine_delete": "Διαγραφή μηχανής",
    "assignments_set": "Ανάθεση σε μηχανή",
    "production_complete": "Ολοκλήρωση παραγωγής",
    "packaging_plan": "Σχεδιασμός συσκευασίας",
    "packaging_complete": "Ολοκλήρωση συσκευασίας",
    "receipt_create": "Νέα παραλαβή",
    "receipt_update": "Διόρθωση παραλαβής",
    "receipt_delete": "Διαγραφή παραλαβής",
    "receipt_received": "Παραλαβή",
    "shipment_create": "Νέα αποστολή",
    "shipment_update": "Διόρθωση αποστολής",
    "shipment_delete": "Διαγραφή αποστολής",
    "shipment_shipped": "Αποστολή",
    "shelf_transfer": "Μεταφορά",
    "shelf_delete": "Διαγραφή γραμμής ραφιού",
    "settings_update": "Αλλαγή ρυθμίσεων",
}

# Field names used in validation messages of the data actions.
FIELDS = {
    "code": "Κωδικός",
    "material_name": "Όνομα Υλικού",
    "quantity": "Ποσότητα",
    "name": "Όνομα",
    "quantity_pcs": "Ποσότητα (τεμάχια)",
    "product_name": "Ονομασία",
    "weight_per_piece": "Βάρος ανά τεμάχιο",
    "cycle_time": "Cycle time (λεπτά)",
    "hours_per_day": "Ώρες λειτουργίας ανά ημέρα",
    "length": "Μήκος",
    "width": "Πλάτος",
    "height": "Ύψος",
    "unit_weight": "Βάρος τεμαχίου",
    "description": "Περιγραφή",
    "quantity_kg": "Ποσότητα (kg)",
    "destination": "Προορισμός",
    "transit_days": "Ημέρες μεταφοράς",
    "max_batch": "Μέγιστο batch (kg)",
    "min_cycle": "Ελάχιστος cycle time (λεπτά)",
    "actual_pieces": "Πραγματικά τεμάχια",
    "item": "Είδος",
    "boxes": "Κουτιά",
    "yellow_days": "Όριο κίτρινου (ημέρες)",
    "red_days": "Όριο κόκκινου (ημέρες)",
    "machine_hours": "Ώρες λειτουργίας ανά εργάσιμη ημέρα",
    "packaging_hours": "Ώρες συσκευασίας ανά ημέρα",
    "material": "Υλικό",
    "product": "Προϊόν",
    "delivery_date": "Ημερομηνία παράδοσης",
    "receipt_date": "Ημερομηνία παραλαβής",
    "shelf_line": "Γραμμή ραφιού",
    "packaging_utilization": "Utilization συσκευασίας (%)",
    "machine": "Μηχανή",
    "defect_rate": "Ποσοστό ελαττωματικών (%)",
    "packaging_item": "Συσκευασία",
    "assignment_quantity": "Ποσότητα ανάθεσης (kg)",
    "extras": "Πρόσθετα είδη",
    "batch_size": "Batch size (kg)",
    "utilization": "Effective utilization (%)",
    "lot_number": "LOT Number",
}
