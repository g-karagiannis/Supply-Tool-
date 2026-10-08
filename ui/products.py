"""Tab 2: Products. Recipes, and how much of each product today's materials allow (section 6)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import streamlit as st

from core.models import MaterialCategory
from core.units import bp_to_percent, format_g, format_int, format_kg, format_number, g_to_mg, mg_to_g
from data import actions
from data.repositories import load_snapshot
from ui import common, texts
from ui.common import Fields, Page, Table, widget_key
from ui.warehouse import material_options, percent_lines, show_percent_total


def render(page: Page) -> None:
    bar = st.container()
    materials = {m.id: m.name for m in page.snapshot.materials}
    table = Table([texts.COL_PRODUCT, texts.COL_WEIGHT_G, texts.COL_MATERIAL_COUNT, texts.COL_PRODUCIBLE_KG,
                   texts.COL_IN_PIECES, texts.COL_LIMITING])
    table.formats = {texts.COL_WEIGHT_G: lambda v: format_g(int(v)), texts.COL_MATERIAL_COUNT: common.int_format,
                     texts.COL_PRODUCIBLE_KG: common.kg_format, texts.COL_IN_PIECES: common.int_format}
    for product in page.snapshot.products:
        availability = page.state.products[product.id]
        count = sum(1 for line in page.snapshot.recipe_lines if line.product_id == product.id)
        table.add(product.id, [
            product.name, product.unit_weight_mg, count,
            availability.producible_mg if availability else None,
            availability.pieces if availability else None,
            materials[availability.limiting_material_id] if availability else "",
        ])
    table.sort(lambda row: row[0].casefold())
    selected = common.show_table(page, "products", table)
    with bar:
        pressed = common.toolbar([texts.PR_ADD, texts.EDIT, texts.DELETE], "products")
        if pressed == texts.PR_ADD:
            common.open_dialog("product_form")
        elif pressed == texts.EDIT and common.need_selection(selected):
            common.open_dialog("product_form", product_id=selected)
        elif pressed == texts.DELETE and common.need_selection(selected):
            product = next(p for p in page.snapshot.products if p.id == selected)
            common.confirm_action(texts.CONFIRM_DELETE_TITLE, texts.confirm_delete(product.name),
                                  actions.delete_product, selected)
    if selected is not None:
        _sheet(page, selected)


def _sheet(page: Page, product_id: int) -> None:
    """The availability table of section 4.3 for one product, with its summary."""
    product = next(p for p in page.snapshot.products if p.id == product_id)
    availability = page.state.products[product_id]
    st.subheader(f"{texts.PRODUCT_SHEET}: {product.name}", anchor=False)
    if availability is None:
        st.info(texts.NO_RECIPE)
        return
    materials = {m.id: m.name for m in page.snapshot.materials}
    table = Table([texts.COL_MATERIAL, texts.COL_PERCENT, texts.COL_AVAILABLE, texts.COL_ENOUGH_FOR,
                   texts.COL_CONSUMED, texts.COL_LEFTOVER])
    kg = lambda v: f"{format_kg(Decimal(str(v)))} {texts.UNIT_KG}"
    table.formats = {texts.COL_PERCENT: lambda v: f"{format_number(Decimal(str(v)), 2)}%", texts.COL_AVAILABLE: kg,
                     texts.COL_ENOUGH_FOR: kg, texts.COL_CONSUMED: kg, texts.COL_LEFTOVER: kg}
    for line in availability.lines:
        name = materials[line.material_id]
        if line.is_limiting:
            name = f"{name} {texts.LIMITING_MARK}"
        table.add(line.material_id, [
            name, common.as_number(bp_to_percent(line.percent_bp)), line.available_mg,
            common.as_number(line.enough_for_mg), line.consumed_mg, line.leftover_mg,
        ])
    common.show_table(page, f"sheet:{product_id}", table, selectable=False)
    st.write(texts.producible_summary(format_kg(availability.producible_mg)))
    if availability.pieces is not None and product.unit_weight_mg:
        st.write(texts.pieces_summary(format_int(availability.pieces), format_g(product.unit_weight_mg)))
    st.write(texts.limiting_summary(materials[availability.limiting_material_id]))


def _product_title(page: Page, params: dict[str, Any]) -> str:
    return texts.T_EDIT_PRODUCT if params.get("product_id") else texts.T_NEW_PRODUCT


@common.dialog("product_form", _product_title, width="large")
def product_form(page: Page, params: dict[str, Any]) -> None:
    """Name, weight per piece and recipe of a product. Percentages must add up to 100%."""
    if common.confirmation_pending(page, params):
        return
    product = next((p for p in page.snapshot.products if p.id == params.get("product_id")), None)
    fields = Fields()
    name = st.text_input(texts.F_PRODUCT_NAME, value=product.name if product else "", key=widget_key(params, "name"))
    weight = fields.stored(texts.F_WEIGHT_PER_PIECE, widget_key(params, "weight"), g_to_mg, mg_to_g,
                           product.unit_weight_mg if product else None, "g")
    st.markdown(f"**{texts.F_RECIPE}**")
    initial = [(l.material_id, bp_to_percent(l.percent_bp)) for l in page.snapshot.recipe_lines
               if product and l.product_id == product.id]
    lines = common.line_editor(params, "recipe", material_options(page), initial, fields,
                               texts.COL_MATERIAL, texts.F_PERCENT, texts.ADD_RECIPE_LINE, "%", 2)
    show_percent_total(lines)
    _new_material(page, params)
    if common.form_buttons(params):
        recipe = percent_lines(lines, fields)
        if not fields.ok() or recipe is None:
            return
        if product is None:
            common.run_action(page, params, actions.create_product, name=name, unit_weight_mg=weight, recipe=recipe)
        else:
            common.run_action(page, params, actions.update_product, product.id, name=name, unit_weight_mg=weight,
                              recipe=recipe)


def _new_material(page: Page, params: dict[str, Any]) -> None:
    """"Νέο υλικό": create a material without leaving the product form (section 6)."""
    with st.expander(texts.NEW_MATERIAL_INLINE):
        name = st.text_input(texts.F_MATERIAL_NAME, key=widget_key(params, "new_material_name"))
        code = st.text_input(texts.F_CODE, key=widget_key(params, "new_material_code"))
        categories = list(MaterialCategory)
        category = st.selectbox(texts.F_CATEGORY, categories, format_func=lambda c: common.CATEGORY_LABELS[c],
                                key=widget_key(params, "new_material_category"))
        st.caption(texts.UNIT_FIXED_KG)
        if st.button(texts.CREATE_MATERIAL, key=widget_key(params, "new_material_create")):
            try:
                actions.create_material(page.conn, code=code, name=name, category=category)
            except actions.ActionError as error:
                st.error(str(error))
                return
            # Reload choices: the new material now appears in the recipe lists.
            page.snapshot = load_snapshot(page.conn)
            st.rerun(scope="fragment")
