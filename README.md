# Supply Tool

**A production and warehouse planning application for a manufacturing plant.**

It makes it easier to organise the supply chain in an industrial environment:
what can I produce with the materials I have, what is missing and when will it
arrive, when will each order be ready, how will it be packed and what is on the
shelf ready to ship. Every figure is recalculated after each movement, so no
screen ever shows an outdated value.

## What it does

- **Warehouse by LOT:** materials with expiry dates and colour warnings,
  packaging, labels, cases and pallets.
- **Recipes and production capacity:** for each product the user sets the
  percentage of every material. The application shows how many pieces can be
  made with the available materials and which material limits production.
- **Orders with priority:** materials are reserved in the sequence of the
  orders. Shortages are shown before saving, together with the expected
  receipts.
- **Machine scheduling:** an order is assigned to one or more machines, and
  completion dates follow the working days and operating hours. Materials are
  consumed by the FEFO rule: first expired, first out.
- **Packaging design:** up to 10 steps (product, container, case, pallet,
  labelling), with time and material calculations. The application proposes
  every possible way of placing the containers inside the case and the cases on
  the pallet (up to 6 orientations, each with the number that fits). It
  preselects the one that fits the most; the user can pick another or type their
  own number.
- **Receipts and shipments:** each receipt creates a new LOT. Shipments leave
  from the shelf, with the number of pallets calculated.
- **History and undo:** every action is recorded and can be undone step by step.
- **Two languages:** Greek and English, with one button.

## Technical characteristics

- Python 3.13, Streamlit and SQLite. A local, single-user application that can
  be opened only from the same computer.
- Three layers with strict boundaries, checked automatically:
  - `core/`: pure calculations, with no screens and no database.
  - `data/`: database, transactions, history.
  - `ui/`: screens.
- Precision: quantities are held as `Decimal` and integers, never as `float`.
  Masses are rounded up to whole milligrams.
- Every action runs in a single SQLite transaction and records the state before
  and after, which is what makes undo possible.
- Automated pytest tests for the calculations, the database, the actions and
  every screen, plus an end-to-end scenario.
- Reproducible environment: `.venv` with locked versions
  (`requirements-lock.txt`).

## Installation

Python 3.13 is required. The application runs from its own `.venv` environment
inside the project folder, with the exact versions in `requirements-lock.txt`.
`start_windows.bat` creates it automatically the first time. To do it by hand,
from the project folder:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

| File | Contents |
|------|----------|
| `requirements.txt` | The libraries the application uses directly, with a minimum version |
| `requirements-lock.txt` | The exact versions of every package the application needs |
| `requirements-dev.txt` | The lock file plus pytest, for the tests only |

## Starting the application

On Windows: double-click `start_windows.bat`. The first time it creates the
`.venv` and installs the packages (an internet connection is needed), then
opens the application in the browser. To stop it, close the black window.

Alternatively, from a command line in the project folder:

```
.venv\Scripts\python.exe -m streamlit run app.py
```

The application opens in the browser at `http://localhost:8501`. It can be
opened only from this computer; other devices on the network have no access
(`server.address = "localhost"` in `.streamlit/config.toml`). On the first start
the database `data/app.db` is created with the default settings. If an older
database exists, its schema is updated automatically.

## Backups

In Settings, the «Backup» button copies the database to the `backups/` folder,
with the date and time in the file name. To restore, close the application and
copy the backup file over `data/app.db`.

## Usage

The workflow for a new order:

1. **Warehouse.** Enter materials with their LOTs, packaging and labels.
   Packaging made in the plant (e.g. a blister) gets a unit weight and a
   material breakdown. Cases and pallets are added with «(+) Add Case/Pallet»:
   a case with inner dimensions (for the packaging containers it holds) and
   outer dimensions (for the pallet), a pallet with its base and maximum load
   height. Labels have their own section.
2. **Products.** Define the product, the weight per piece and the recipe
   (percentages that add up to 100%). Selecting a product shows how much can be
   made with the available materials and which material is the limit.
3. **Orders.** A new order with quantity, destination and delivery date. The
   shortage table appears while you type. The «Sequence» decides which order
   gets the materials first.
4. **Machines and production.** Enter machines, assign the order to one or more
   of them, and press «Completed» with the actual pieces produced. Materials are
   taken from the LOTs, starting with the one that expires first.
5. **Packaging.** Design up to 10 steps: product packaging, packaging container,
   case, pallet, and Labelling steps after any Package step you choose (one
   label per unit of that step). For the case and the pallet the application
   proposes the placements. Pallets are rounded up (e.g. «13 pallets, the last
   one with 5 cases»). The time of a Labelling step that follows product
   packaging runs in parallel with it; all other steps add up. Everything is
   updated before saving. «Completed» deducts the packaging and creates the line
   on the shelf.
6. **Receipts and shipments.** Expected receipts appear in the Warehouse and in
   the shortages. «Received» creates a new LOT. Shipments take boxes off the
   shelf.
7. **Settings.** Expiry limits, working days, operating hours per working day
   (the default for new machines; every machine keeps its own hours), defaults,
   the action history, backup and full wipe.

Every action is recorded in the history. The «Undo» button above the tabs
undoes the most recent action, and further presses go further back.

Number fields accept both a comma and a dot as the decimal separator. Under
each field the application shows how the number was read, e.g. «= 1,5 kg». In
whole-number fields (pieces, boxes, days) the dot separates thousands, so
«385.000» is read as three hundred eighty-five thousand.

## Language

The «ΕΛ | EN» button at the top right switches the whole application between
Greek and English without changing the tab. The choice is saved in the
database, so the application opens in the last language used. It is not
recorded in the history, cannot be undone and is kept after a full wipe.

- Numbers use the Greek format in both languages (comma for decimals, dot for
  thousands).
- History entries stay in the language they were written in.
- Names given by the user (materials, products, orders) are not translated.
- New orders are suggested as ORD-001, ORD-002 and so on in both languages;
  numbering continues after the highest existing number, including older names
  such as ΠΑΡ-007.

## Full wipe

In Settings, the «Full wipe» button deletes all data (materials, LOTs,
packaging, products, orders, machines, receipts, shipments, shelf and history)
and restores the default settings. It cannot be undone with the «Undo» button.
Before deleting, a backup is saved automatically in the `backups/` folder, from
which it can be restored as described above.

## Tests

```
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
```

The tests cover every example in section 12 of the specification, the
end-to-end scenario (12.9), the no-emoji check (12.10) and the separation of
the layers.

## Structure

| Folder | Contents |
|--------|----------|
| `core/` | Calculations, pure functions with no Streamlit and no SQLite |
| `data/` | Database schema, migrations, reading, writing, actions, history |
| `ui/` | Streamlit screens; the texts are in `ui/texts_el.py` (Greek) and `ui/texts_en.py` (English), selected by `ui/texts.py` |
| `tests/` | pytest tests |
| `backups/` | Database backups |

The cycle of every action: the screen calls one function in `data/actions.py`,
which in a single transaction validates, writes the changes and one history
entry. The page then reloads all data and `core.state.compute_state()`
recalculates from scratch the available stock, reservations, shortages,
statuses and dates. This way no tab shows an outdated figure.

Schema changes are made with numbered scripts in `data/migrations/`
(`0001_initial.sql`, `0002_soft_delete.sql`, ...). The applied version is
recorded in the `schema_version` table.
