"""
Should-Cost Model Builder — v3.14 (template-based, fully linked)

Strategy: load reference files as templates, replace content cell-by-cell.
This preserves all theme fills, fonts, row heights, and column widths exactly.

Reference files (embedded in skill assets):
  assets/reference_model_plate.xlsx  → template for calculation model
  assets/input_template_empty.xlsx   → template for slide values

CATEGORY    = from "Purchasing Category" column in HAGER PPE 2025.xlsx
SUB-CATEGORY = from "Product Family" column in HAGER PPE 2025.xlsx

Fully linked: all Calculation E-column and Overview C-column cells are Excel formulas.
Changing any Base value (F-column) in '2. Inputs' updates all results automatically.
"""
import os, copy
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, '..', 'assets')

# Fallback: if template not in assets, build from scratch using known good styles
CALC_TEMPLATE  = os.path.join(ASSETS_DIR, 'reference_model_plate.xlsx')
SV_TEMPLATE    = os.path.join(ASSETS_DIR, 'input_template_empty.xlsx')

# ── Style helpers (for SlideValues which doesn't use template) ──────────────
NAVY   = 'FF003755'
WHITE  = 'FFFFFFFF'
LBLUE  = 'FFD9E1F2'
ARIAL  = 'Arial'
NO_FILL  = PatternFill(fill_type=None)
FMT_EUR  = '_-* #,##0.00\ "€"_-;\-* #,##0.00\ "€"_-;_-* "-"??\ "€"_-;_-@_-'
FMT_INP  = '#,##0.00;[Red]\(#,##0.00\);\u2013'
FMT_2DP  = '#,##0.00'
FMT_PCT  = '0.00%'

def solid(hex6):
    return PatternFill('solid', fgColor=hex6, bgColor=hex6)

def fnt(bold=False, sz=10, color=None):
    if color:
        return Font(name=ARIAL, size=sz, bold=bold, color=color)
    return Font(name=ARIAL, size=sz, bold=bold)


# ════════════════════════════════════════════════════════════════════════════
# BUILD CALCULATION MODEL  (template-based, fully linked)
# ════════════════════════════════════════════════════════════════════════════

def build_calc_model(general_info, inputs, calculations, out_path):
    """
    Build the calculation model by cloning the reference template and
    writing new content into it. All theme fills and fonts are preserved.

    inputs: list of bucket-header strings and parameter tuples
        (row_num, param, unit, low, base, high, source)
        Valid bucket strings: 'Material' | 'Conversion' | 'Quality and Packaging' |
                              'Logistics' | 'SG&A and Margin' | 'Reference Data (fixed)'

    calculations: list of section-header strings and formula tuples
        (id_code, element_name, units, formula_string)
        formula_string must be a valid Excel formula starting with '='.

    Fully linked: Calculation E-column contains formulas referencing '2. Inputs'!F{row}.
    Overview C-column contains formulas referencing '3. Calculation'!E{row}.
    """
    # Load template if available, else create fresh workbook
    if os.path.exists(CALC_TEMPLATE):
        wb = load_workbook(CALC_TEMPLATE)
    else:
        wb = Workbook()
        # Minimal sheet setup — won't have theme fills but will work
        _setup_calc_sheets(wb)

    # ── 0. Introduction ─────────────────────────────────────────────────
    ws0 = wb['0. Introduction']
    intro = [
        ('B2',  'Purpose',      True),
        ('B3',  '- Leverage analysis in negotiations to gain transparency on the cost structure.', False),
        ('B4',  '- Clear indication for the supplier, that Hager has done the homework.', False),
        ('B5',  '- Enforce a fact-based discussion with the suppliers.', False),
        ('B7',  'Output format', True),
        ('B8',  '- Cost build in five buckets: Material, Conversion, Packaging & Logistics, Overheads, Margin (quality costs not modelled).', False),
        ('B10', 'Contents', True),
        ('B11', '1. Overview & Results'),
        ('C11', 'Summary on the material and the Cost Build in six buckets, plus Key Results.'),
        ('B12', '2. Inputs'),
        ('C12', '20-40 individual parameters for each material used to build up the should cost.'),
        ('B13', '3. Calculation'),
        ('C13', 'Calculation of the model outputs.'),
        ('B15', 'How to use this file', True),
        ('B16', '- The file is completely linked — changing the input parameters in the "2. Inputs" tab (Base column F) updates all results automatically.', False),
        ('B17', '- The base value for each parameter is used in the calculation. Low/High define the sensitivity range.', False),
    ]
    for item in intro:
        addr, val = item[0], item[1]
        bold = item[2] if len(item) > 2 else False
        ws0[addr].value = val

    # ── 2. Inputs ───────────────────────────────────────────────────────
    ws2 = wb['2. Inputs']
    # Clear existing content rows (keep header row 2 intact)
    for row in ws2.iter_rows(min_row=3, max_row=ws2.max_row):
        for cell in row:
            cell.value = None

    BUCKET_DISPLAY = {
        'Material':               'Material',
        'Conversion':             'Conversion',
        'Packaging & Logistics':  'Packaging & Logistics',
        'Manufacturing Overheads':'Manufacturing Overheads',
        'SG&A':                   'SG&A',
        'Margin':                 'Margin',
        'Overheads':              'Overheads',               # legacy
        'SG&A and Margin':        'SG&A and Margin',         # legacy
        'Quality and Packaging':  'Quality and Packaging',   # legacy
        'Logistics':              'Logistics',               # legacy
        'Reference Data (fixed)': 'Reference Data (fixed)',
    }

    param_row_map = {}   # param_num → excel_row
    r = 3

    for item in inputs:
        if isinstance(item, str):
            # Bucket header — write in col C with same style as template
            ws2.cell(r, 3).value = BUCKET_DISPLAY.get(item, item)
            # Copy style from template row 3 (Material header) if possible
            r += 1
        else:
            num, param, unit, low, base, high, source = item
            param_row_map[num] = r
            ws2.cell(r, 2).value = num
            ws2.cell(r, 3).value = param
            ws2.cell(r, 4).value = unit
            ws2.cell(r, 5).value = low    # Low  (col E)
            ws2.cell(r, 6).value = base   # Base (col F) ← formulas reference this
            ws2.cell(r, 7).value = high   # High (col G)
            ws2.cell(r, 8).value = source or ''
            r += 1

    # ── 3. Calculation ─────────────────────────────────────────────────
    ws3 = wb['3. Calculation']

    # ── Grab fills BEFORE clearing (clear loop would destroy theme fills) ──
    # Section header grey:  theme=0 tint=-0.15 → B3 in template
    # Subtotal light green: theme=6 tint=0.80  → B20 in template
    sect_fill  = copy.copy(ws3['B3'].fill)   # grey bar
    green_fill = copy.copy(ws3['B20'].fill)  # light green subtotal

    # Now clear all existing content
    for row in ws3.iter_rows(min_row=3, max_row=ws3.max_row):
        for cell in row:
            cell.value = None
            cell.fill  = PatternFill(fill_type=None)

    calc_row_map = {}
    calc_row = 3


    def apply_sect(r):
        """Apply grey section-header fill to cols B-E of row r."""
        for col in [2, 3, 4, 5]:
            ws3.cell(r, col).fill = copy.copy(sect_fill)

    def apply_green(r):
        """Apply light-green subtotal fill to cols B-E of row r."""
        for col in [2, 3, 4, 5]:
            ws3.cell(r, col).fill = copy.copy(green_fill)

    def clear_row(r):
        """Blank row — ensure no fill, no value."""
        for col in range(1, 7):
            ws3.cell(r, col).value = None
            ws3.cell(r, col).fill  = NO_FILL

    for item in calculations:
        # ── Section header (grey bar): e.g. '  1. Material' ───────────────
        if isinstance(item, str) and item != '_BLANK':
            apply_sect(calc_row)
            ws3.cell(calc_row, 2).value = item
            ws3.cell(calc_row, 2).font  = fnt(bold=True, sz=10)
            calc_row += 1

        # ── Blank white separator row ──────────────────────────────────────
        elif item == '_BLANK':
            clear_row(calc_row)
            calc_row += 1

        else:
            id_code = item[0]
            element = item[1] if len(item) > 1 else None
            units   = item[2] if len(item) > 2 else None
            formula = item[3] if len(item) > 3 else None

            if id_code == '_SIGMA_C':
                # Sigma subtotal: col B empty (no fill), label in col C bold
                # Font size sz=10 on all cells for consistent row height
                calc_row_map[element] = calc_row
                ws3.cell(calc_row, 2).value = None
                ws3.cell(calc_row, 2).fill  = NO_FILL
                ws3.cell(calc_row, 3).value = element
                ws3.cell(calc_row, 3).font  = fnt(bold=True, sz=10)
                ws3.cell(calc_row, 3).fill  = NO_FILL
                ws3.cell(calc_row, 3).alignment = Alignment(horizontal='left')
                ws3.cell(calc_row, 4).value = None
                ws3.cell(calc_row, 4).fill  = NO_FILL
                ws3.cell(calc_row, 5).value = formula
                ws3.cell(calc_row, 5).font  = fnt(sz=10)   # sz=10 matches data rows
                ws3.cell(calc_row, 5).fill  = NO_FILL
                ws3.cell(calc_row, 5).number_format = FMT_EUR

            elif id_code == '_SUBTOTAL_B':
                # Light green subtotal bar: col B label, green fill across B-E
                calc_row_map[element] = calc_row
                apply_green(calc_row)
                ws3.cell(calc_row, 2).value = element
                ws3.cell(calc_row, 2).font  = fnt(bold=True, sz=10)
                ws3.cell(calc_row, 2).alignment = Alignment(horizontal='left')
                ws3.cell(calc_row, 3).value = None
                ws3.cell(calc_row, 4).value = units
                ws3.cell(calc_row, 4).font  = fnt(sz=10)
                ws3.cell(calc_row, 5).value = formula
                ws3.cell(calc_row, 5).font  = fnt(bold=True, sz=10)  # bold on subtotals
                ws3.cell(calc_row, 5).number_format = FMT_EUR

            elif id_code == '_SIGMA_B':
                # Post-SHOULD COST rows: col B bold, no fill, sz=10 for consistency
                calc_row_map[element] = calc_row
                ws3.cell(calc_row, 2).value = element
                ws3.cell(calc_row, 2).font  = fnt(bold=True, sz=10)
                ws3.cell(calc_row, 2).fill  = NO_FILL
                ws3.cell(calc_row, 2).alignment = Alignment(horizontal='left')
                ws3.cell(calc_row, 3).value = None
                ws3.cell(calc_row, 3).fill  = NO_FILL
                ws3.cell(calc_row, 4).value = units
                ws3.cell(calc_row, 4).font  = fnt(sz=10)
                ws3.cell(calc_row, 4).fill  = NO_FILL
                ws3.cell(calc_row, 5).value = formula
                ws3.cell(calc_row, 5).font  = fnt(sz=10)
                ws3.cell(calc_row, 5).fill  = NO_FILL
                ws3.cell(calc_row, 5).number_format = FMT_PCT if element == 'Impact %' else FMT_EUR

            else:
                # Regular data row: id in col B bold, element in col C, no fill
                calc_row_map[id_code] = calc_row
                ws3.cell(calc_row, 2).value = id_code
                ws3.cell(calc_row, 2).font  = fnt(bold=True, sz=10)
                ws3.cell(calc_row, 2).fill  = NO_FILL
                ws3.cell(calc_row, 2).alignment = Alignment(horizontal='left')
                ws3.cell(calc_row, 3).value = element or ''
                ws3.cell(calc_row, 3).font  = fnt(sz=10)
                ws3.cell(calc_row, 3).fill  = NO_FILL
                ws3.cell(calc_row, 3).alignment = Alignment(horizontal='left')
                ws3.cell(calc_row, 4).value = units or ''
                ws3.cell(calc_row, 4).font  = fnt(sz=10)
                ws3.cell(calc_row, 4).fill  = NO_FILL
                ws3.cell(calc_row, 5).value = formula
                ws3.cell(calc_row, 5).font  = fnt(sz=10)
                ws3.cell(calc_row, 5).fill  = NO_FILL
                ws3.cell(calc_row, 5).number_format = FMT_EUR

            calc_row += 1

    # ── 1. Overview & Results ──────────────────────────────────────────
    ws1 = wb['1. Overview & Results']

    # Grab fills BEFORE any clearing (clear loop would destroy theme fills)
    fill_sub  = copy.copy(ws1['B18'].fill)   # green subtotal (theme=6)
    fill_key  = copy.copy(ws1['B28'].fill)   # grey header    (theme=0)

    # Title
    ws1['B2'].value = f"Should- Cost Analysis - {general_info['title']}"

    # General info rows 5-11 (label in B, value in C — linked where formula, else literal)
    for ri, (lbl, val) in enumerate(general_info['rows'], 5):
        ws1.cell(ri, 2).value = lbl
        ws1.cell(ri, 3).value = val

    # Clear old template rows 13-40
    for r in range(13, 41):
        for col in [2, 3]:
            ws1.cell(r, col).value = None
            ws1.cell(r, col).fill  = NO_FILL

    # Cost Build header
    ws1['B13'].value = 'Cost Build [\u20ac/unit, estimated values]'
    ws1['B13'].fill  = copy.copy(fill_key)
    ws1['B15'].value = 'Cost Element'
    ws1['C15'].value = 'Value [\u20ac/unit]'

    # Locate key input rows for formulas
    cp_row  = next((param_row_map[it[0]] for it in inputs
                    if isinstance(it, tuple) and 'current' in it[1].lower() and 'price' in it[1].lower()), None)
    vol_row = next((param_row_map[it[0]] for it in inputs
                    if isinstance(it, tuple) and 'volume' in it[1].lower() and 'annual' in it[1].lower()), None)

    def calc_ref(id_code):
        row = calc_row_map.get(id_code)
        return f"=\'3. Calculation\'!E{row}" if row else ''

    cp_formula = f"=\'2. Inputs\'!F{cp_row}" if cp_row else ''
    sc_ref     = calc_ref('SHOULD COST')

    # Cost build rows 16-24 — 5-bucket fixed structure (NO COGS subtotal per skill spec)
    # Material → Conversion → Manufacturing Costs (subtotal) →
    # Packaging & Logistics → Overheads → Margin → Should Cost → Impact Potential → Current Price
    cost_map = [
        (16, 'Material',                calc_ref('\u03a3 Material'),              False),
        (17, 'Conversion',              calc_ref('\u03a3 Conversion'),            False),
        (18, 'Manufacturing Costs',     calc_ref('Manufacturing Costs'),           True),
        (19, 'Packaging & Logistics',   calc_ref('\u03a3 Packaging & Logistics'), False),
        (20, 'Overheads',               calc_ref('O1'),                            False),
        (21, 'Margin',                  calc_ref('S1'),                            False),
        (22, 'Should Cost',             sc_ref,                                    True),
        (23, 'Impact Potential',        f"={cp_formula[1:]}-C22" if cp_formula else '', False),
        (24, 'Current Price',           cp_formula,                                False),
    ]
    for row_num, label, formula, is_sub in cost_map:
        ws1.cell(row_num, 2).value = label
        ws1.cell(row_num, 2).font  = fnt(bold=is_sub, sz=10)
        ws1.cell(row_num, 3).value = formula
        ws1.cell(row_num, 3).number_format = FMT_EUR
        if is_sub:
            ws1.cell(row_num, 2).fill = copy.copy(fill_sub)
            ws1.cell(row_num, 3).fill = copy.copy(fill_sub)
        else:
            ws1.cell(row_num, 2).fill = NO_FILL
            ws1.cell(row_num, 3).fill = NO_FILL

    # Key Results header
    ws1['B28'].value = 'Key Results'
    ws1['B28'].fill  = copy.copy(fill_key)

    # Key result rows 30-35 — all linked formulas
    key_map = [
        (30, 'Current price (weighted avg)',    cp_formula,                    FMT_EUR),
        (31, 'Should-Cost (calculated)',         sc_ref,                        FMT_EUR),
        (32, 'Impact potential per unit',        calc_ref('Impact Potential'),  FMT_EUR),
        (33, 'Impact %',                         calc_ref('Impact %'),          '0.0%'),
        (34, 'Annual volume (units)',             f"=\'2. Inputs\'!F{vol_row}" if vol_row else '', '#,##0'),
        (35, 'Annual impact potential (\u20ac)','=C34*C32',                   FMT_EUR),
    ]
    for row_num, label, formula, numfmt in key_map:
        ws1.cell(row_num, 2).value = label
        ws1.cell(row_num, 2).font  = fnt(sz=10)
        ws1.cell(row_num, 2).fill  = NO_FILL
        ws1.cell(row_num, 3).value = formula
        ws1.cell(row_num, 3).font  = fnt(sz=10)
        ws1.cell(row_num, 3).fill  = NO_FILL
        ws1.cell(row_num, 3).number_format = numfmt
        ws1.row_dimensions[row_num].height = 19.5

    wb.save(out_path)
    return out_path, param_row_map, calc_row_map


# ════════════════════════════════════════════════════════════════════════════
# BUILD SLIDE VALUES FILE  (pixel-perfect, matches reference SlideValues)
# ════════════════════════════════════════════════════════════════════════════

def build_slide_values(material_id, d, slide3_params, slide5_data, out_path):
    """
    d['category']     = from "Purchasing Category" column in HAGER PPE 2025.xlsx
    d['sub_category'] = from "Product Family" column in HAGER PPE 2025.xlsx
    """
    # Always build SlideValues from scratch (no template — styles are written explicitly)
    wb = Workbook()
    wb.active.title = 'Slide 1 - Cover'
    for name in ['Slide 2 - Cost Build', 'Slide 3 - Inputs', 'Slide 4 - Sensitivity']:
        wb.create_sheet(name)

    def sv_hdr(cell, lbl):
        cell.value = lbl
        cell.font  = fnt(bold=True, sz=11, color=WHITE)
        cell.fill  = solid(NAVY)

    def sv_sec(ws, cell_addr, text, merge=None):
        ws[cell_addr].value = text
        ws[cell_addr].font  = fnt(bold=True, sz=11, color=NAVY)
        ws[cell_addr].fill  = solid(LBLUE)
        if merge:
            ws.merge_cells(merge)

    def sv_row(ws, r, slide_ref, label, value, numfmt='General'):
        ws.cell(r,1).value = slide_ref; ws.cell(r,1).font = fnt(sz=10); ws.cell(r,1).fill = NO_FILL
        ws.cell(r,2).value = label;     ws.cell(r,2).font = fnt(sz=10); ws.cell(r,2).fill = NO_FILL
        ws.cell(r,3).value = value;     ws.cell(r,3).font = fnt(bold=True,sz=10); ws.cell(r,3).fill = NO_FILL
        ws.cell(r,3).number_format = numfmt

    # ── Slide 1 - Cover ─────────────────────────────────────────────────
    ws1 = wb['Slide 1 - Cover']
    ws1.row_dimensions[1].height = 18
    ws1.column_dimensions['A'].width = 10
    ws1.column_dimensions['B'].width = 38

    ws1['A1'].value = 'Slide 1 \u2014 Cover'
    ws1['A1'].font  = fnt(bold=True, sz=14, color=NAVY)
    ws1['A1'].fill  = NO_FILL

    for col, lbl in [('A','Slide'),('B','PPT element'),('C','Value')]:
        sv_hdr(ws1[f'{col}3'], lbl)

    for i, (lbl, val) in enumerate([
        ('Title \u2014 Material name', d['material_name'].upper()),
        ('Subtitle \u2014 Date',       d.get('date_str', 'May 2026')),
        ('Material ID',                material_id),
    ], 4):
        sv_row(ws1, i, 'Slide 1', lbl, val)

    # ── Slide 2 - Cost Build ────────────────────────────────────────────
    ws2 = wb['Slide 2 - Cost Build']
    ws2.row_dimensions[1].height = 18
    ws2.column_dimensions['A'].width = 10
    ws2.column_dimensions['B'].width = 38
    ws2.column_dimensions['C'].width = 28

    ws2['A1'].value = 'Slide 2 \u2014 Cost Build'
    ws2['A1'].font  = fnt(bold=True, sz=14, color=NAVY)
    ws2['A1'].fill  = NO_FILL

    for col, lbl in [('A','Slide'),('B','PPT element'),('C','Value')]:
        sv_hdr(ws2[f'{col}3'], lbl)

    info = [
        ('Material name',      d['material_name'],   'General'),
        ('Material number',    material_id,           'General'),
        ('Category',           d['category'],         'General'),   # ← Purchasing Category
        ('Sub-category',       d['sub_category'],     'General'),   # ← Product Family
        ('Quantity p.a.',      d['qty_pa'],           'General'),
        ('Spend',              d['spend_str'],        'General'),
        ('Avg price per unit', d['avg_price'],        '#,##0.00'),
        ('Incumbent supplier', d['supplier'],         'General'),
        ('Supplier location',  d['location'],         'General'),
    ]
    for i, (lbl, val, nf) in enumerate(info, 4):
        sv_row(ws2, i, 'Slide 2', lbl, val, numfmt=nf)

    sv_sec(ws2, 'A14', 'Cost Build Waterfall [\u20ac/unit]', merge='A14:C14')

    mc   = round(d['material_eur'] + d['conversion_eur'], 2)
    # 5-bucket fixed structure: Material, Conversion, Mfg Costs (subtotal),
    # Packaging & Logistics, Overheads, Margin, Should Cost (subtotal),
    # Impact Potential, Current Price.  NO COGS subtotal.
    # Accepts both old keys (qp_eur/sga_eur) and new unified keys (pl_eur/overheads_eur)
    pl   = round(d.get('pl_eur', d.get('qp_eur', 0)), 2)
    oh   = round(d.get('overheads_eur', d.get('sga_eur', 0) + d.get('mfg_oh_eur', 0)), 2)
    mg   = round(d['margin_eur'], 2)
    sc   = round(mc + pl + oh + mg, 2)
    ip   = round(d['current_price_eur'] - sc, 2)

    waterfall = [
        ('Material',                       d['material_eur']),
        ('Conversion',                     d['conversion_eur']),
        ('Manufacturing Costs (subtotal)', mc),
        ('Packaging & Logistics',          pl),
        ('Overheads',                      oh),
        ('Margin',                         mg),
        ('Should Cost (subtotal)',         sc),
        ('Impact Potential',               ip),
        ('Current Price',                  d['current_price_eur']),
    ]
    for i, (lbl, val) in enumerate(waterfall, 15):
        sv_row(ws2, i, 'Slide 2', lbl, val, numfmt='#,##0.00')

    # Key result tiles start 2 rows after waterfall end (9 waterfall rows → last at row 23, blank at 24, header at 25)
    sv_sec(ws2, 'A25', 'Key Result Tiles', merge='A25:C25')

    for i, (lbl, val, nf) in enumerate([
        ('Current Price tile',    d['current_price_eur'], '#,##0.00'),
        ('Benchmark Price tile',  sc,                     '#,##0.00'),
        ('Impact potential tile', d['impact_tile_str'],   'General'),
    ], 26):
        sv_row(ws2, i, 'Slide 2', lbl, val, numfmt=nf)

    # ── Slide 3 - Inputs ────────────────────────────────────────────────
    # Tab name: "Slide 3 - Inputs"
    # A1 title:  "Slide 4 — Inputs"  (matches reference)
    # Col A data: "Slide 4"           (matches reference)
    ws3 = wb['Slide 3 - Inputs']
    ws3.row_dimensions[1].height = 18
    for col, w in [('A',10),('B',8),('C',50),('D',12),('E',10),('H',20)]:
        ws3.column_dimensions[col].width = w

    ws3['A1'].value = 'Slide 4 \u2014 Inputs'
    ws3['A1'].font  = fnt(bold=True, sz=14, color=NAVY)
    ws3['A1'].fill  = NO_FILL

    for col, lbl in [('A','Slide'),('B','Row#'),('C','Parameter'),('D','Unit'),
                     ('E','Low'),('F','Base'),('G','High'),('H','Bucket')]:
        sv_hdr(ws3[f'{col}3'], lbl)

    BUCKET_SEP = {
        'Material':               'MATERIAL',
        'Conversion':             'CONVERSION',
        'Packaging & Logistics':  'PACKAGING & LOGISTICS',
        'Overheads':              'OVERHEADS',                  # primary 5-bucket name
        'Margin':                 'MARGIN',
        'Reference':              'REFERENCE DATA (FIXED)',
        # Legacy names — kept for backward compatibility
        'Manufacturing Overheads':'OVERHEADS',
        'SG&A':                   'OVERHEADS',
        'SG&A and Margin':        'OVERHEADS',
        'Quality and Packaging':  'PACKAGING & LOGISTICS',
        'Logistics':              'PACKAGING & LOGISTICS',
    }
    BUCKET_H = {
        'Material':               'Material',
        'Conversion':             'Conversion',
        'Packaging & Logistics':  'Packaging & Logistics',
        'Overheads':              'Overheads',                  # primary 5-bucket name
        'Margin':                 'Margin',
        'Reference':              'Reference',
        # Legacy names
        'Manufacturing Overheads':'Overheads',
        'SG&A':                   'Overheads',
        'SG&A and Margin':        'Overheads',
        'Quality and Packaging':  'Packaging & Logistics',
        'Logistics':              'Packaging & Logistics',
    }

    row = 4
    cur_bucket = None
    for p in slide3_params:
        bucket = p['bucket']
        if bucket != cur_bucket:
            sep = BUCKET_SEP.get(bucket, bucket.upper())
            ws3.cell(row, 1).value = sep
            ws3.cell(row, 1).font  = fnt(bold=True, sz=11, color=NAVY)
            ws3.cell(row, 1).fill  = solid(LBLUE)
            ws3.merge_cells(f'A{row}:H{row}')
            cur_bucket = bucket
            row += 1

        h_label = p.get('h_override') or BUCKET_H.get(bucket, bucket)
        ws3.cell(row, 1).value = 'Slide 4'; ws3.cell(row, 1).font = fnt(sz=10); ws3.cell(row, 1).fill = NO_FILL
        ws3.cell(row, 2).value = p['row_num']; ws3.cell(row, 2).font = fnt(sz=10); ws3.cell(row, 2).fill = NO_FILL
        ws3.cell(row, 3).value = p['parameter']; ws3.cell(row, 3).font = fnt(sz=10); ws3.cell(row, 3).fill = NO_FILL
        ws3.cell(row, 4).value = p['unit']; ws3.cell(row, 4).font = fnt(sz=10); ws3.cell(row, 4).fill = NO_FILL
        ws3.cell(row, 5).value = p['low']; ws3.cell(row, 5).font = fnt(sz=10); ws3.cell(row, 5).fill = NO_FILL
        ws3.cell(row, 6).value = p['base']; ws3.cell(row, 6).font = fnt(bold=True, sz=10); ws3.cell(row, 6).fill = NO_FILL
        ws3.cell(row, 7).value = p['high']; ws3.cell(row, 7).font = fnt(sz=10); ws3.cell(row, 7).fill = NO_FILL
        ws3.cell(row, 8).value = h_label; ws3.cell(row, 8).font = fnt(sz=10); ws3.cell(row, 8).fill = NO_FILL
        row += 1

    # ── Slide 4 - Sensitivity ───────────────────────────────────────────
    # Tab: "Slide 4 - Sensitivity", A1: "Slide 5 — Sensitivity", col A: "Slide 5"
    ws4 = wb['Slide 4 - Sensitivity']
    ws4.row_dimensions[1].height = 18
    ws4.column_dimensions['A'].width = 10
    ws4.column_dimensions['B'].width = 30
    ws4.column_dimensions['C'].width = 12
    ws4.column_dimensions['D'].width = 14
    ws4.column_dimensions['E'].width = 22

    ws4['A1'].value = 'Slide 5 \u2014 Sensitivity'
    ws4['A1'].font  = fnt(bold=True, sz=14, color=NAVY)
    ws4['A1'].fill  = NO_FILL

    base_sc = slide5_data['base_sc']
    ws4['A3'].value = f'Tornado \u2014 Top 5 sensitivity drivers (Base SC = {base_sc:.2f} \u20ac/unit)'
    ws4['A3'].font  = fnt(bold=True, sz=11, color=NAVY)
    ws4['A3'].fill  = solid(LBLUE)
    ws4.merge_cells('A3:E3')

    for col, lbl in [('A','Slide'),('B','Driver'),('C','Scenario'),
                     ('D','Input value'),('E','Should Cost [\u20ac/unit]')]:
        sv_hdr(ws4[f'{col}4'], lbl)

    row = 5
    for drv in slide5_data['drivers'][:5]:
        for sr in drv['rows']:
            ws4.cell(row,1).value='Slide 5'; ws4.cell(row,1).font=fnt(sz=10); ws4.cell(row,1).fill=NO_FILL
            ws4.cell(row,2).value=drv['name']; ws4.cell(row,2).font=fnt(sz=10); ws4.cell(row,2).fill=NO_FILL
            ws4.cell(row,3).value=sr['scenario']; ws4.cell(row,3).font=fnt(sz=10); ws4.cell(row,3).fill=NO_FILL
            ws4.cell(row,4).value=str(sr['input_val']); ws4.cell(row,4).font=fnt(sz=10); ws4.cell(row,4).fill=NO_FILL
            ws4.cell(row,5).value=sr['sc_result']; ws4.cell(row,5).font=fnt(bold=True,sz=10)
            ws4.cell(row,5).fill=NO_FILL; ws4.cell(row,5).number_format='#,##0.00'
            row += 1

    wb.save(out_path)
    return out_path


# ════════════════════════════════════════════════════════════════════════════
# EXAMPLE DATA — material 1000126756 (Bagholder 5L welded)
# Formulas reference '2. Inputs'!F{row} based on the parameter row positions
# below. Row positions are determined by the EXAMPLE_INPUTS list order.
# ════════════════════════════════════════════════════════════════════════════

EXAMPLE_GENERAL_INFO = {
    'title': 'Bagholder 5L welded',
    'rows': [
        ('Material ID',       '1000126756'),
        ('Material name',     'Bagholder 5L welded (Baghalter 5L geschwei\u00dft)'),
        ('Plant',             'Sartorius Stedim Systems GmbH'),
        ('Incumbent supplier','Sedlbauer AG (934082), Grafenau/DE'),
        ('Category',          'Assembled Metal Parts > Welded Subassemblies (M10600)'),
        ('Process',           'Sheet-metal welded subassembly: laser cut + bend + certified SS-TIG weld + 3-step surface treatment'),
        ('BOM size',          '13 components (9 sheet-metal parts + 4 fastener/turned parts)'),
    ]
}

# Row mapping after processing EXAMPLE_INPUTS:
# Row 3: Material header
# Row 4: param 1 (price)        → F4
# Row 5: param 2 (weight)       → F5
# Row 6: param 3 (yield)        → F6
# Row 7: param 4 (fasteners M3x8) → F7
# Row 8: param 5 (fasteners M3)  → F8
# Row 9: param 6 (fasteners M5)  → F9
# Row 10: Conversion header
# Row 11: param 7 (laser_rate)   → F11
# Row 12: param 8 (laser_time)   → F12
# Row 13: param 9 (brake_rate)   → F13
# Row 14: param 10 (bends)       → F14
# Row 15: param 11 (bend_time)   → F15
# Row 16: param 12 (weld_rate)   → F16
# Row 17: param 13 (weld_time)   → F17
# Row 18: param 14 (fstner_time) → F18
# Row 19: param 15 (surface)     → F19
# Row 20: param 16 (setup_time)  → F20
# Row 21: param 17 (setup_rate)  → F21
# Row 22: param 18 (op_rate)     → F22
# Row 23: param 19 (QC_time)     → F23
# Row 24: param 20 (marking)     → F24
# Row 25: Quality and Packaging header
# Row 26: param 21 (pkg)         → F26
# Row 27: param 22 (CoA)         → F27
# Row 28: param 23 (QA_admin)    → F28
# Row 29: param 24 (FAI)         → F29
# Row 30: Logistics header
# Row 31: param 25 (freight)     → F31
# Row 32: param 26 (incoming)    → F32
# Row 33: SG&A and Margin header
# Row 34: param 27 (SGA_pct)     → F34
# Row 35: param 28 (margin_pct)  → F35
# Row 36: Reference Data header
# Row 37: param 29 (volume)      → F37
# Row 38: param 30 (spend)       → F38
# Row 39: param 31 (price)       → F39
# Row 40: param 32 (lot_count)   → F40
# Row 41: param 33 (lot_size)    → F41
# Row 42: param 34 (risk_score)  → F42
# Row 43: param 35 (uplift)      → F43

EXAMPLE_INPUTS = [
    # ── MATERIAL ─────────────────────────────────────────────────────────
    # row 3: header | rows 4-8: params 1-5
    # Rule 1: Nesting yield + scrap credit MUST both be explicit inputs
    # Gross weight = Net weight / (Nesting yield / 100)
    # Net material cost = Gross weight × Price − Scrap credit
    'Material',
    (1, 'Stainless 1.4301 sheet price (DE, certified MTC, 1.5mm)', 'EUR/kg',
     3.0, 3.8, 4.5,
     'Klöckner/Service Center DE wholesale 2025; LME Ni-premium spot + DE small-qty surcharge 30-80%'),
    (2, 'Net material weight per assembly (9 child parts summed)', 'kg',
     3.95, 3.96, 3.96,
     'STL-1000126756-03 + 13 child drawings; component mass sum verified; Tier 1 if drawing weight stated'),
    (3, 'Nesting yield (sheet utilization — Rule 1)', '%',
     60, 65, 75,
     'Rule 1: laser-cut sheet; complex 9-part geometry with curved profile; nesting software estimate; '
     '55-80% range per benchmarks.md; 65% base is conservative for irregular shapes'),
    (4, 'Scrap recovery credit (% of raw material cost — Rule 1)', '%',
     15, 20, 25,
     'Rule 6: stainless 1.4301 scrap recovery 15-25% of buy price; DE metal recycler 2025; '
     'skeleton offcuts sold per kg at ~75-80% of LME; costing_accuracy_rules.md Rule 6'),
    (5, 'Fasteners total (28× studs M3x8 + 6× rivet nut M3 + 1× M5)', 'EUR/asm',
     1.95, 2.75, 3.9,
     'KVT FASTEKS FWB M3x8 SS A2 ~0.04-0.08€/PC; KVT M3 HC ROKSG ~0.10-0.22€/PC; '
     'KVT M5 HC ROKS ~0.15-0.40€/PC; quantities from BOM STL-1000126756-03'),

    # ── CONVERSION ───────────────────────────────────────────────────────
    # row 9: header | rows 10-24: params 6-20
    # Rule 3: Separate critical from non-critical features in cycle time derivation
    # Rule 4: Rates from DE regional table (Sedlbauer = DE SME, Grafenau)
    # Rule 5: Setup is ONE per lot across ALL machines (not per-part)
    'Conversion',
    (6,  'Laser cutting hourly rate (DE, machine-only — Rule 4)', 'EUR/h',
     70, 90, 115,
     'Rule 4: DE fiber laser 4kW machine-only; costing_accuracy_rules.md regional table 2025; '
     'VDW 2024 / Maschinenmarkt; incl. assist gas but excl. operator (separate)'),
    (7,  'Laser cutting time per assembly (9 parts — Rule 3)', 'min/asm',
     28, 42, 60,
     'Rule 3: critical features (tolerance holes) at full speed; cosmetic profiles at 1.2× feed; '
     'perimeter sum from drawing + 25% nesting repositioning; Tier 3 estimate; validate with supplier'),
    (8,  'Press brake hourly rate (DE, machine-only — Rule 4)', 'EUR/h',
     48, 65, 88,
     'Rule 4: DE CNC press brake 80-160t machine-only; costing_accuracy_rules.md regional table 2025; '
     'VDW 2024; lower bound = older/depreciated machine, upper = newer 4-axis CNC'),
    (9,  'Total bends per assembly', 'bends/asm',
     35, 50, 65,
     'Rule 3: count from drawings — outer shell ~15, inner brackets ~10, bottom plate ~6, '
     'frame ~14, misc ~5; verify against drawing bend table if available'),
    (10, 'Bending time per bend (incl. die-change amort.)', 'min/bend',
     0.5, 0.9, 1.4,
     'Rule 3: standard bends at 0.5-0.7 min; close-tolerance bends at 1.0-1.4 min; '
     'Trumpf/Schuler application data; die-change amortised across lot, not per-part'),
    (11, 'Welding cell hourly rate (cert. SS-TIG, Hager-audited — Rule 4)', 'EUR/h',
     85, 108, 135,
     'Rule 4: DE manual TIG certified welder; costing_accuracy_rules.md DE table 2025 €80-120/h; '
     'Sedlbauer has certified welders per MAI Spec — use upper half of range'),
    (12, 'Total welding time per assembly (Rule 3 + Rule 5 sanity check)', 'h/asm',
     3.0, 5.5, 8.5,
     'Rule 3+5: critical seams (root + cap, full penetration) + tack welds + cosmetic caps; '
     'weld speed manual TIG 100-180 mm/min; estimated weld length 600-1500mm total; '
     'sanity: 600mm÷150mm/min=4min weld + 55min positioning/tacking = ~1h; '
     '5.5h base for full assembly incl. fixture time + passivation; challenge if >8h'),
    (13, 'Fastener installation time (28 studs + 7 rivet nuts)', 'min/asm',
     25, 40, 55,
     'Rule 5: resistance stud welding ~25s/PC × 28 = 11.7min; rivet press ~40s/PC × 7 = 4.7min; '
     'total ~16min + handling; Tier 3 estimate'),
    (14, '3-step surface treatment (external supplier)', 'EUR/asm',
     45, 80, 130,
     'Rule 5: single job-lot op (not per-part); DE pharma SS surface treatment job-shop; '
     'mask threads + clean + pickle + blast + passivate; Transporeon/supplier RFQ 2025; '
     'NOT double-counted with freight — treatment transport in service rate'),
    (15, 'Setup time per lot (ONE setup across all machines — Rule 2+5)', 'h/lot',
     10, 15, 22,
     'Rule 2+5: ONE setup per lot = laser program load (~4h for 9 parts) + brake tooling (~4h) '
     '+ weld fixture (~7h); NOT one setup per part; Tier 3 estimate; '
     'validate: ask supplier for last changeover log'),
    (16, 'Setup hourly rate (blended skilled — Rule 4)', 'EUR/h',
     72, 88, 108,
     'Rule 4: DE blended programmer+operator; Eurostat lc_lci_lev 2024 DE mfg + 15% non-wage burden; '
     'costing_accuracy_rules.md DE operator base €45-75/h fully loaded'),
    (17, 'Operator rate fully-loaded (assembly/QC — Rule 4)', 'EUR/h',
     48, 62, 78,
     'Rule 4: DE sheet metal worker; Eurostat lc_lci_lev 2024 NACE C25 + IGM tariff 2025; '
     'base wage ~€28-32/h + 2.2-2.4× statutory burden = €62-77/h; '
     'costing_accuracy_rules.md DE table base €58/h'),
    (18, 'Final QC + MIP completion time per assembly', 'min/asm',
     18, 30, 55,
     'Rule 3: critical inspection points per MAI Spec Q1/Q2; visual 15s × ~8 zones + '
     'MIP form completion ~10min; non-critical dimensional check waived per drawing note; '
     'Tier 3 estimate — validate with Hager QA'),
    (19, 'Laser marking per unit (datamatrix + serial)', 'EUR/asm',
     1.0, 1.8, 3.5,
     'External laser marking DE; includes setup amort. for serial-specific program; '
     'market rate 2025; single-station op — not a multi-machine op (Rule 5 N/A)'),
    (20, 'Lot count per year (Rule 2 — CRITICAL for setup cost)', '#/yr',
     4, 3.5, 3.0,
     'Rule 2: MANDATORY — from HAGER PPE 2025 order history; '
     'drives setup cost per unit; do NOT substitute annual volume here'),

    # ── PACKAGING & LOGISTICS ─────────────────────────────────────────────
    # row 24: header | rows 25-26: params 20-21
    'Packaging & Logistics',
    (20, 'Packaging per unit (foam insert + carton, Hager spec)', 'EUR/asm',
     8, 12, 20, 'Hager-designated packaging spec; Bito / Garant catalogue pricing 2025'),
    (21, 'Freight Grafenau → Guxhagen (~600km, intra-DE road)', 'EUR/asm',
     3, 5, 9, 'Transporeon/Upply 2025 DE LTL spot rate; single-pallet allocation ~600km'),

    # ── OVERHEADS (combines Mfg OH + SG&A — single bucket per 5-bucket structure) ──
    # row 28: header | row 29: param 23
    'Overheads',
    (23, 'Overheads rate on manufacturing costs (mfg OH + SG&A combined)', '%',
     10, 14, 20,
     'DE metal fabricator: mfg overhead ~8% + SG&A ~9% on mfg cost base; '
     'Sedlbauer FY23 data (BCG Negotiation Dossier 2025-12); combined into single Overheads bucket'),

    # ── MARGIN ───────────────────────────────────────────────────────────
    # row 30: header | row 31: param 24
    'Margin',
    (24, 'Supplier margin on (Manufacturing Costs + P&L + Overheads)', '%',
     10, 13, 16, 'Sedlbauer Group EBITDA FY23 10.7%; DE welded subassemblies benchmark 10-16%; benchmarks.md'),

    # ── REFERENCE DATA (FIXED) ────────────────────────────────────────────
    # row 32: header | rows 33-37: params 25-29
    'Reference Data (fixed)',
    (25, 'Annual Volume',    'PC/yr',  45, 45, 45,
     'HAGER PPE 2025.xlsx — FIXED, do not change'),
    (26, 'Annual Spend',     'EUR/yr', 92406.38, 92406.38, 92406.38,
     'HAGER PPE 2025.xlsx — FIXED, do not change'),
    (27, 'Current Avg Price','EUR/PC', 2053.475111, 2053.475111, 2053.475111,
     'Annual Spend / Annual Volume — HAGER PPE 2025.xlsx'),
    (28, 'Lot count per year (reference)', '#/yr', 4, 3.5, 3.0,
     'HAGER PPE 2025 order history'),
    (29, 'Avg lot size', 'PC/lot', 11.25, 12.86, 15.0,
     'Derived: Volume / Lot count'),
]
# Formulas — row numbers match EXAMPLE_INPUTS layout above
# EXAMPLE_INPUTS row mapping (5-bucket layout):
#   Row 3:  Material header
#   Row 4:  param 1  — sheet price             → F4
#   Row 5:  param 2  — net weight              → F5
#   Row 6:  param 3  — nesting yield           → F6
#   Row 7:  param 4  — scrap recovery          → F7
#   Row 8:  param 5  — fasteners total         → F8
#   Row 9:  Conversion header
#   Row 10: param 6  — laser rate              → F10
#   Row 11: param 7  — laser time              → F11
#   Row 12: param 8  — brake rate              → F12
#   Row 13: param 9  — bends                   → F13
#   Row 14: param 10 — bend time               → F14
#   Row 15: param 11 — weld rate               → F15
#   Row 16: param 12 — weld time               → F16
#   Row 17: param 13 — fastener install time   → F17
#   Row 18: param 14 — surface treatment       → F18
#   Row 19: param 15 — setup time              → F19
#   Row 20: param 16 — setup rate              → F20
#   Row 21: param 17 — operator rate           → F21
#   Row 22: param 18 — QC time                 → F22
#   Row 23: param 19 — laser marking           → F23
#   Row 24: param 20 — lot count               → F24
#   Row 25: Packaging & Logistics header
#   Row 26: param 21 — packaging per unit      → F26
#   Row 27: param 22 — freight                 → F27
#   Row 28: Overheads header
#   Row 29: param 23 — overhead rate           → F29
#   Row 30: Margin header
#   Row 31: param 24 — margin rate             → F31
#   Row 32: Reference Data header
#   Row 33: param 25 — annual volume           → F33
#   Row 34: param 26 — annual spend            → F34
#   Row 35: param 27 — current price           → F35
#   Row 36: param 28 — lot count (ref)         → F36
#   Row 37: param 29 — avg lot size            → F37
EXAMPLE_CALCULATIONS = [
    # ── 1. Material ──────────────────────────────────────────────────────────
    '  1. Material',
    # Gross weight = net_weight / (nesting_yield / 100)
    # Sheet cost net of scrap credit = Gross*Price − (Gross-Net)*Price*recovery%/100
    ('M1', 'Gross material weight (net ÷ nesting yield)', 'kg/asm',
     "='2. Inputs'!F5/('2. Inputs'!F6/100)"),
    ('M2', 'Sheet metal cost net of scrap credit', '€/asm',
     "=E4*'2. Inputs'!F4-(E4-'2. Inputs'!F5)*'2. Inputs'!F4*'2. Inputs'!F7/100"),
    ('M3', 'Fasteners total', '€/asm', "='2. Inputs'!F8"),
    ('_SIGMA_C', 'Σ Material', '€/asm', '=E5+E6'),
    '_BLANK',
    # ── 2. Conversion ────────────────────────────────────────────────────────
    '  2. Conversion',
    ('C1', 'Laser cutting', '€/asm', "=('2. Inputs'!F11/60)*'2. Inputs'!F10"),
    ('C2', 'Bending',       '€/asm', "=('2. Inputs'!F13*'2. Inputs'!F14/60)*'2. Inputs'!F12"),
    ('C3', 'Welding cert. SS-TIG', '€/asm', "='2. Inputs'!F16*'2. Inputs'!F15"),
    ('C4', 'Fastener installation', '€/asm', "=('2. Inputs'!F17/60)*'2. Inputs'!F21"),
    ('C5', 'Surface treatment', '€/asm', "='2. Inputs'!F18"),
    ('C6', 'Setup per unit (time×rate×lots÷vol)', '€/asm',
     "=('2. Inputs'!F19*'2. Inputs'!F20*'2. Inputs'!F24)/'2. Inputs'!F33"),
    ('C7', 'Final QC + MIP', '€/asm', "=('2. Inputs'!F22/60)*'2. Inputs'!F21"),
    ('C8', 'Laser marking',   '€/asm', "='2. Inputs'!F23"),
    ('_SIGMA_C', 'Σ Conversion', '€/asm', '=E10+E11+E12+E13+E14+E15+E16+E17'),
    '_BLANK',
    # Manufacturing Costs subtotal = Material + Conversion
    ('_SUBTOTAL_B', 'Manufacturing Costs', '€/asm', '=E7+E18'),
    '_BLANK',
    # ── 3. Packaging & Logistics ─────────────────────────────────────────────
    '  3. Packaging & Logistics',
    ('P1', 'Packaging per unit', '€/asm', "='2. Inputs'!F26"),
    ('P2', 'Freight',            '€/asm', "='2. Inputs'!F27"),
    ('_SIGMA_C', 'Σ Packaging & Logistics', '€/asm', '=E23+E24'),
    '_BLANK',
    # ── 4. Overheads (Mfg OH + SG&A combined — 5-bucket structure, NO COGS) ──
    '  4. Overheads',
    # Applied on Manufacturing Costs base; covers both mfg overhead and SG&A
    ('O1', 'Overheads (mfg OH + SG&A on mfg costs base)', '€/asm',
     "=E20*'2. Inputs'!F29/100"),
    '_BLANK',
    # ── 5. Margin ─────────────────────────────────────────────────────────────
    '  5. Margin',
    # Margin on (Manufacturing Costs + P&L + Overheads) per skill fixed structure
    ('S1', 'Margin', '€/asm',
     "=(E20+E25+E28)*'2. Inputs'!F31/100"),
    '_BLANK',
    # ── Totals (NO COGS subtotal — 5-bucket structure) ────────────────────────
    # Should Cost = Manufacturing Costs + P&L + Overheads + Margin
    ('_SUBTOTAL_B', 'SHOULD COST', '€/asm', '=E20+E25+E28+E31'),
    ('_SIGMA_B', 'Σ CURRENT PRICE',       '€/asm', "='2. Inputs'!F35"),
    ('_SIGMA_B', 'Impact Potential',            '€/asm', '=E34-E33'),
    ('_SIGMA_B', 'Impact %',                    '%',          '=E35/E34'),
    ('_SIGMA_B', 'Annual saving potential',     '€',     "=E35*'2. Inputs'!F33"),
]
EXAMPLE_SV_DATA = {
    'material_name':     'Bagholder 5L welded',
    'category':          'Assembled Metal Parts',    # ← from Purchasing Category
    'sub_category':      'Welded Subassemblies',     # ← from Product Family
    'qty_pa':            45,
    'spend_str':         '\u20ac92k',
    'avg_price':         2053.48,
    'supplier':          'Sedlbauer AG',
    'location':          'Grafenau, Germany',
    'date_str':          'May 2026',
    'material_eur':      31.69,
    'conversion_eur':    1239.67,
    'pl_eur':            50.67,        # Packaging & Logistics bucket (was qp_eur + logistics_eur)
    'overheads_eur':     145.42,       # Overheads bucket (Mfg OH + SG&A combined)
    'margin_eur':        190.77,
    'current_price_eur': 2053.48,
    'impact_tile_str':   '\u20ac18k p.a. (19.2%)',
}

EXAMPLE_SLIDE3 = [
    {'bucket':'Material',              'row_num':1,  'parameter':'Stainless 1.4301 sheet price (DE, certified MTC)', 'unit':'\u20ac/kg',  'low':3,    'base':3.8,  'high':4.5},
    {'bucket':'Material',              'row_num':2,  'parameter':'Material utilization (nesting yield)',             'unit':'%',          'low':60,   'base':52,   'high':45},
    {'bucket':'Material',              'row_num':3,  'parameter':'Net material weight per assembly',                 'unit':'kg',         'low':3.95, 'base':3.96, 'high':3.96},
    {'bucket':'Material',              'row_num':4,  'parameter':'Fasteners total (studs + rivet nuts)',             'unit':'\u20ac/asm','low':1.95, 'base':2.75, 'high':3.9},
    {'bucket':'Conversion',            'row_num':5,  'parameter':'Laser cutting time (9 parts)',                    'unit':'min/asm',    'low':30,   'base':45,   'high':65},
    {'bucket':'Conversion',            'row_num':6,  'parameter':'Laser cutting rate (machine-only)',               'unit':'\u20ac/h',  'low':75,   'base':90,   'high':110},
    {'bucket':'Conversion',            'row_num':7,  'parameter':'Total bends per assembly',                        'unit':'#/asm',      'low':35,   'base':50,   'high':65},
    {'bucket':'Conversion',            'row_num':8,  'parameter':'Bending time per bend',                           'unit':'min',        'low':0.6,  'base':1.0,  'high':1.5},
    {'bucket':'Conversion',            'row_num':9,  'parameter':'Press brake rate (machine-only)',                 'unit':'\u20ac/h',  'low':60,   'base':75,   'high':95},
    {'bucket':'Conversion',            'row_num':10, 'parameter':'Welding time per assembly',                       'unit':'h/asm',      'low':4.5,  'base':7.0,  'high':10.0},
    {'bucket':'Conversion',            'row_num':11, 'parameter':'Welding cell rate (cert. SS-TIG)',                'unit':'\u20ac/h',  'low':90,   'base':115,  'high':140},
    {'bucket':'Conversion',            'row_num':12, 'parameter':'Fastener installation time',                      'unit':'min/asm',    'low':30,   'base':45,   'high':60},
    {'bucket':'Conversion',            'row_num':13, 'parameter':'3-step surface treatment',                        'unit':'\u20ac/asm','low':50,   'base':90,   'high':140},
    {'bucket':'Conversion',            'row_num':14, 'parameter':'Setup time per lot',                              'unit':'h/lot',      'low':12,   'base':18,   'high':26},
    {'bucket':'Conversion',            'row_num':15, 'parameter':'Setup hourly rate (blended)',                     'unit':'\u20ac/h',  'low':75,   'base':90,   'high':110},
    {'bucket':'Conversion',            'row_num':16, 'parameter':'Operator rate fully-loaded',                      'unit':'\u20ac/h',  'low':50,   'base':65,   'high':80},
    {'bucket':'Conversion',            'row_num':17, 'parameter':'Final QC + MIP time',                             'unit':'min/asm',    'low':20,   'base':35,   'high':60},
    {'bucket':'Conversion',            'row_num':18, 'parameter':'Laser marking per unit',                          'unit':'\u20ac/asm','low':1,    'base':2,    'high':4},
    {'bucket':'Packaging & Logistics', 'row_num':19, 'parameter':'Packaging per unit (foam + carton)',              'unit':'\u20ac/asm','low':8,    'base':12,   'high':20},
    {'bucket':'Packaging & Logistics', 'row_num':20, 'parameter':'Freight Grafenau \u2192 Guxhagen (~600km DE)',   'unit':'\u20ac/asm','low':3,    'base':5,    'high':9},
    {'bucket':'Overheads',             'row_num':21, 'parameter':'Overheads rate on mfg costs (mfg OH + SG&A)',   'unit':'%',          'low':10,   'base':14,   'high':20},
    {'bucket':'Margin',                'row_num':22, 'parameter':'Supplier margin on (Mfg Costs + P&L + OH)',     'unit':'%',          'low':10,   'base':13,   'high':16},
    {'bucket':'Reference',             'row_num':23, 'parameter':'Annual volume',                                   'unit':'PC/yr',      'low':45,   'base':45,   'high':45},
    {'bucket':'Reference',             'row_num':24, 'parameter':'Current price (weighted avg)',                    'unit':'\u20ac/unit','low':2053.48,'base':2053.48,'high':2053.48},
]
EXAMPLE_SLIDE5 = {
    'base_sc': 1658.21,
    'drivers': [
        {'name':'Welding time (h/asm)',           'rows':[{'scenario':'Low','input_val':'4.5', 'sc_result':1297.60},{'scenario':'Mid','input_val':'7.0', 'sc_result':1658.21},{'scenario':'High','input_val':'10.0','sc_result':2090.95}]},
        {'name':'Welding rate (\u20ac/h)',         'rows':[{'scenario':'Low','input_val':'90',  'sc_result':1438.71},{'scenario':'Mid','input_val':'115', 'sc_result':1658.21},{'scenario':'High','input_val':'140', 'sc_result':1877.71}]},
        {'name':'Setup time per lot (h)',          'rows':[{'scenario':'Low','input_val':'12',  'sc_result':1605.53},{'scenario':'Mid','input_val':'18',  'sc_result':1658.21},{'scenario':'High','input_val':'26', 'sc_result':1728.45}]},
        {'name':'Surface treatment (\u20ac/asm)',  'rows':[{'scenario':'Low','input_val':'50',  'sc_result':1608.04},{'scenario':'Mid','input_val':'90',  'sc_result':1658.21},{'scenario':'High','input_val':'140','sc_result':1720.93}]},
        {'name':'Supplier margin (%)',             'rows':[{'scenario':'Low','input_val':'10%', 'sc_result':1614.19},{'scenario':'Mid','input_val':'13%', 'sc_result':1658.21},{'scenario':'High','input_val':'16%','sc_result':1702.24}]},
    ]
}


if __name__ == '__main__':
    result = build_calc_model(
        EXAMPLE_GENERAL_INFO, EXAMPLE_INPUTS, EXAMPLE_CALCULATIONS,
        '/tmp/Should_Cost_1000126756_v6.xlsx'
    )
    print(f'Calc model written. {len(result[1])} params, {len(result[2])} calc rows')

    build_slide_values(
        '1000126756', EXAMPLE_SV_DATA, EXAMPLE_SLIDE3, EXAMPLE_SLIDE5,
        '/tmp/1000126756_SlideValues_v6.xlsx'
    )
    print('SlideValues written')
