from __future__ import annotations

import datetime as dt
import os
import xml.sax.saxutils as saxutils
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "model" / "TGP_Fund_One_Model.xlsx"


def col_letter(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def escape(text: str) -> str:
    return saxutils.escape(str(text))


class Sheet:
    def __init__(self, name: str):
        self.name = name
        self.cells: dict[tuple[int, int], dict] = {}
        self.col_widths: dict[int, float] = {}
        self.merges: list[str] = []
        self.freeze = None
        self.auto_filter = None

    def set_col(self, col: int, width: float) -> None:
        self.col_widths[col] = width

    def merge(self, ref: str) -> None:
        self.merges.append(ref)

    def cell(
        self,
        row: int,
        col: int,
        *,
        value=None,
        formula: str | None = None,
        style: int = 0,
        kind: str = "n",
    ) -> None:
        self.cells[(row, col)] = {
            "value": value,
            "formula": formula,
            "style": style,
            "kind": kind,
        }

    def inline(self, row: int, col: int, text: str, style: int = 0) -> None:
        self.cell(row, col, value=text, style=style, kind="inlineStr")

    def number(self, row: int, col: int, value, style: int = 0) -> None:
        self.cell(row, col, value=value, style=style, kind="n")

    def formula_cell(self, row: int, col: int, formula: str, style: int = 0) -> None:
        self.cell(row, col, formula=formula, style=style, kind="n")

    def bool_number(self, row: int, col: int, value: int, style: int = 0) -> None:
        self.cell(row, col, value=value, style=style, kind="n")

    def build_xml(self, sheet_id: int) -> str:
        rows: dict[int, list[tuple[int, dict]]] = {}
        for (r, c), meta in self.cells.items():
            rows.setdefault(r, []).append((c, meta))
        for r in rows:
            rows[r].sort(key=lambda item: item[0])

        max_row = max(rows) if rows else 1
        max_col = max((c for (_, c) in self.cells), default=1)
        dim = f"A1:{col_letter(max_col)}{max_row}"

        parts = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
            f"<dimension ref=\"{dim}\"/>",
            "<sheetViews><sheetView workbookViewId=\"0\">",
        ]
        if self.freeze:
            col, row = self.freeze
            top_left = f"{col_letter(col + 1)}{row + 1}"
            parts.append(
                f'<pane xSplit="{col}" ySplit="{row}" topLeftCell="{top_left}" '
                'activePane="bottomRight" state="frozen"/>'
            )
        parts.append("</sheetView></sheetViews>")

        if self.col_widths:
            parts.append("<cols>")
            for col in sorted(self.col_widths):
                width = self.col_widths[col]
                parts.append(
                    f'<col min="{col}" max="{col}" width="{width}" customWidth="1"/>'
                )
            parts.append("</cols>")

        parts.append("<sheetData>")
        for r in range(1, max_row + 1):
            row_cells = rows.get(r)
            if not row_cells:
                continue
            parts.append(f'<row r="{r}">')
            for c, meta in row_cells:
                ref = f"{col_letter(c)}{r}"
                style_attr = f' s="{meta["style"]}"' if meta["style"] else ""
                kind = meta["kind"]
                if kind == "inlineStr":
                    text = escape(meta["value"] or "")
                    parts.append(
                        f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{text}</t></is></c>'
                    )
                    continue
                if meta["formula"] is not None:
                    formula = escape(meta["formula"])
                    value = meta["value"]
                    if value is None:
                        parts.append(f'<c r="{ref}"{style_attr}><f>{formula}</f></c>')
                    else:
                        parts.append(
                            f'<c r="{ref}"{style_attr}><f>{formula}</f><v>{value}</v></c>'
                        )
                    continue
                value = meta["value"]
                if value is None or value == "":
                    parts.append(f'<c r="{ref}"{style_attr}/>')
                else:
                    parts.append(f'<c r="{ref}"{style_attr}><v>{value}</v></c>')
            parts.append("</row>")
        parts.append("</sheetData>")

        if self.auto_filter:
            parts.append(f'<autoFilter ref="{self.auto_filter}"/>')

        if self.merges:
            parts.append(f'<mergeCells count="{len(self.merges)}">')
            for ref in self.merges:
                parts.append(f'<mergeCell ref="{ref}"/>')
            parts.append("</mergeCells>")

        parts.append(
            "<pageMargins left=\"0.3\" right=\"0.3\" top=\"0.5\" bottom=\"0.5\" "
            "header=\"0.3\" footer=\"0.3\"/>"
        )
        parts.append("</worksheet>")
        return "".join(parts)


STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="6">
    <numFmt numFmtId="164" formatCode="$#,##0"/>
    <numFmt numFmtId="165" formatCode="$#,##0.0,,&quot;M&quot;"/>
    <numFmt numFmtId="166" formatCode="$#,##0.00,,,&quot;B&quot;"/>
    <numFmt numFmtId="167" formatCode="0.0%"/>
    <numFmt numFmtId="168" formatCode="$#,##0.00"/>
    <numFmt numFmtId="169" formatCode="0.0"/>
  </numFmts>
  <fonts count="4">
    <font><sz val="11"/><name val="Aptos"/></font>
    <font><b/><sz val="20"/><name val="Aptos Display"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font>
    <font><b/><sz val="11"/><name val="Aptos"/></font>
  </fonts>
  <fills count="9">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF5F2EC"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFB38B57"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF7E9BF"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE4F3E8"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE8EFF8"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFCE8E6"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF1EBE1"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD6C9B8"/></left>
      <right style="thin"><color rgb="FFD6C9B8"/></right>
      <top style="thin"><color rgb="FFD6C9B8"/></top>
      <bottom style="thin"><color rgb="FFD6C9B8"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="14">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="3" fillId="8" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
    <xf numFmtId="169" fontId="0" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="167" fontId="0" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="3" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="167" fontId="3" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="168" fontId="3" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="0" fillId="2" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="167" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="169" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
"""


def build_inputs_sheet() -> Sheet:
    s = Sheet("Inputs")
    s.freeze = (0, 4)
    for idx, width in {
        1: 28, 2: 18, 3: 26, 4: 26
    }.items():
        s.set_col(idx, width)

    s.merge("A1:D1")
    s.inline(1, 1, "TGP Fund One Model Inputs", style=1)
    s.merge("A2:D2")
    s.inline(
        2,
        1,
        "Built by Reif Tauati · 4176197004 · reif@thegoodproject.net",
        style=10,
    )

    s.inline(4, 1, "Core Assumptions", style=2)
    labels = [
        ("Max Fund Size ($B)", 1.0, 5),
        ("Capital Calls On (1=yes, 0=no)", 1, 5),
        ("Hardcore Mode (1=yes, 0=no)", 0, 5),
        ("Loan Size ($M)", 25.0, 5),
        ("Base Deals / Month", 3.0, 5),
        ("Loan Term (months)", 18, 5),
        ("Debt / Equity", 0.0, 5),
        ("Borrower Rate", 0.25, 6),
        ("Fund Take", 0.18, 6),
        ("Cost of Debt", 0.08, 6),
        ("Target IRR", 0.15, 6),
        ("View Months", 120, 5),
    ]
    start_row = 5
    for i, (label, default, style) in enumerate(labels, start=start_row):
        s.inline(i, 1, label, style=3)
        kind_style = 6 if i in (12, 13, 14, 15) else style
        if isinstance(default, str):
            s.inline(i, 2, default, style=kind_style)
        else:
            s.number(i, 2, default, style=kind_style)

    s.inline(5, 3, "Investor-facing guidance", style=2)
    notes = [
        "Max Fund Size is the hard ceiling on total LP capital called.",
        "Capital Calls On means equity is called only when needed. Hardcore Mode forces fully funded upfront deployment with zero idle cash.",
        "Borrower Rate is what the developer pays. Fund Take is what the fund retains after origination partners are paid.",
        "Debt / Equity of 0.25 means $0.25 of debt for each $1.00 of LP equity.",
    ]
    for idx, note in enumerate(notes, start=6):
        s.inline(idx, 3, note, style=10)

    s.inline(18, 1, "Derived", style=2)
    s.inline(19, 1, "Just-in-Time Calls Active", style=3)
    s.formula_cell(19, 2, 'IF(B7=1,0,B6)', style=5)
    s.inline(20, 1, "Total Lending Multiple", style=3)
    s.formula_cell(20, 2, '1+B11', style=5)
    s.inline(21, 1, "Shares Outstanding", style=3)
    s.formula_cell(21, 2, 'B5*1000000000/1000', style=5)
    s.inline(22, 1, "Initial LP Call ($)", style=3)
    s.formula_cell(22, 2, 'IF(B19=1,0,B5*1000000000)', style=11)
    return s


def build_summary_sheet() -> Sheet:
    s = Sheet("Summary")
    s.freeze = (0, 5)
    for idx, width in {1: 28, 2: 18, 3: 28, 4: 18}.items():
        s.set_col(idx, width)

    s.merge("A1:D1")
    s.inline(1, 1, "Fund One Excel Model Summary", style=1)
    s.merge("A2:D2")
    s.inline(2, 1, "Contact Reif Tauati · 4176197004 · reif@thegoodproject.net", style=10)

    s.inline(4, 1, "Scenario Output", style=2)
    metrics = [
        ("Projected IRR", "Monthly_Model!AI127", 8),
        ("Year 10 NAV / Share", "Monthly_Model!AC127", 9),
        ("Lowest Cash", "MIN(Monthly_Model!$Z$7:$Z$127)", 7),
        ("Peak LP Capital Out", "MAX(Monthly_Model!$AD$7:$AD$127)", 7),
        ("Peak Debt", "MAX(Monthly_Model!$AE$7:$AE$127)", 7),
        ("Peak New Loan Volume / Month", "MAX(Monthly_Model!$V$8:$V$127)", 7),
        ("Peak Loans / Month", "MAX(Monthly_Model!$AG$8:$AG$127)", 13),
        ("Total LP Called", "MAX(Monthly_Model!$AH$7:$AH$127)", 7),
        ("Total Loans Originated", "SUM(Monthly_Model!$AG$8:$AG$127)", 13),
        ("Target vs Projected Gap", "Monthly_Model!AI127-Inputs!B15", 8),
    ]
    row = 5
    for label, formula, style in metrics:
        s.inline(row, 1, label, style=3)
        s.formula_cell(row, 2, formula, style=style)
        row += 1

    s.inline(5, 3, "How to use this workbook", style=2)
    help_rows = [
        "Yellow cells on Inputs are editable assumptions.",
        "Green cells are modeled outputs.",
        "Monthly_Model contains the full 10-year monthly build with formulas.",
        "Hardcore Mode redeploys all available cash immediately and disables just-in-time capital calling.",
    ]
    for idx, text in enumerate(help_rows, start=6):
        s.inline(idx, 3, text, style=10)
    return s


def build_monthly_sheet() -> Sheet:
    s = Sheet("Monthly_Model")
    s.freeze = (2, 7)
    widths = {
        1: 8, 2: 14, 3: 14, 4: 14, 5: 13, 6: 13, 7: 13, 8: 13, 9: 13, 10: 14,
        11: 14, 12: 15, 13: 12, 14: 12, 15: 12, 16: 12, 17: 12, 18: 14, 19: 14,
        20: 14, 21: 13, 22: 14, 23: 13, 24: 13, 25: 13, 26: 14, 27: 13, 28: 14,
        29: 13, 30: 14, 31: 14, 32: 14, 33: 14, 34: 14, 35: 13, 36: 13
    }
    for idx, width in widths.items():
        s.set_col(idx, width)

    s.merge("A1:AJ1")
    s.inline(1, 1, "10-Year Monthly Projection", style=1)
    s.merge("A2:AJ2")
    s.inline(2, 1, "Formulas trace the current /model logic. Edit Inputs and Excel will recalculate.", style=10)

    headers = [
        "Month", "Label", "Opening Cash", "Opening NAV", "Carry Interest", "Carry Principal",
        "Active Eq Open", "Active Debt Open", "Carry Debt Cost", "Pre-Deploy Cash", "Remaining Callable",
        "Deployable Eq Cap", "Loan Size", "Base Deals", "Pipeline Scale", "Ramp", "Scaled Deals",
        "Desired Orig Vol", "Desired Eq Deploy", "Actual Eq Deploy", "LP Call", "Actual Orig Vol",
        "Debt Deploy", "Immediate Interest", "Immediate Debt Cost", "Ending Cash", "Ending NAV",
        "Target NAV", "NAV / Share", "Active Eq Close", "Active Debt Close", "Loans Outstanding",
        "New Loans / Mo", "Cumulative LP Called", "IRR To Date", "LP Flow Helper"
    ]
    header_row = 6
    for i, label in enumerate(headers, start=1):
        s.inline(header_row, i, label, style=2)
    s.auto_filter = "A6:AJ127"

    # Start row
    r = 7
    s.number(r, 1, 0, style=13)
    s.inline(r, 2, "Start", style=10)
    s.formula_cell(r, 3, "Inputs!B22", style=11)
    s.formula_cell(r, 4, "Inputs!B22", style=11)
    for c in range(5, 26):
        s.number(r, c, 0, style=11 if c in (5, 6, 7, 8, 9, 10, 11, 12) else 13)
    s.formula_cell(r, 26, "C7", style=11)
    s.formula_cell(r, 27, "D7", style=11)
    s.formula_cell(r, 28, "Inputs!B22", style=11)
    s.formula_cell(r, 29, "IF(Inputs!B21>0,AA7/Inputs!B21,0)", style=9)
    s.number(r, 30, 0, style=11)
    s.number(r, 31, 0, style=11)
    s.number(r, 32, 0, style=11)
    s.formula_cell(r, 33, "0", style=13)
    s.formula_cell(r, 34, "Inputs!B22", style=11)
    s.number(r, 35, 0, style=8)
    s.number(r, 36, 0, style=11)

    for row in range(8, 128):
        prev = row - 1
        s.formula_cell(row, 1, f"A{prev}+1", style=13)
        s.inline(row, 2, f"Month {row - 7}", style=10)
        s.formula_cell(row, 3, f"Z{prev}", style=11)
        s.formula_cell(row, 4, f"AA{prev}", style=11)
        s.formula_cell(
            row,
            5,
            f'IF(A{row}<=12,0,INDEX($V$8:$V$127,A{row}-12)*Inputs!B13*MAX(0,Inputs!B10-12)/12)',
            style=11,
        )
        s.formula_cell(
            row,
            6,
            f'IF(A{row}<=Inputs!B10,0,INDEX($T$8:$T$127,A{row}-Inputs!B10))',
            style=11,
        )
        s.formula_cell(row, 7, f'AD{prev}-F{row}', style=11)
        s.formula_cell(
            row,
            8,
            f'AE{prev}-IF(A{row}<=Inputs!B10,0,INDEX($W$8:$W$127,A{row}-Inputs!B10))',
            style=11,
        )
        s.formula_cell(row, 9, f'H{row}*Inputs!B14/12', style=11)
        s.formula_cell(row, 10, f'C{row}+E{row}+F{row}-I{row}', style=11)
        s.formula_cell(row, 11, f'IF(Inputs!B19=1,MAX(0,Inputs!B5*1000000000-AH{prev}),0)', style=11)
        s.formula_cell(row, 12, f'MAX(0,J{row}+K{row})', style=11)
        s.formula_cell(row, 13, 'Inputs!B8*1000000', style=11)
        s.formula_cell(row, 14, 'Inputs!B9', style=13)
        s.formula_cell(
            row,
            15,
            f'MAX(1,SQRT(L{row}/MAX(M{row}*MAX(N{row},0.01)/(1+Inputs!B11),1)))',
            style=13,
        )
        s.formula_cell(row, 16, f'MIN(1,A{row}/12)', style=13)
        s.formula_cell(
            row,
            17,
            f'IF(Inputs!B7=1,MAX(N{row},L{row}*(1+Inputs!B11)/MAX(M{row},1)),N{row}+(N{row}*O{row}-N{row})*P{row})',
            style=13,
        )
        s.formula_cell(row, 18, f'IF(Inputs!B7=1,L{row}*(1+Inputs!B11),M{row}*Q{row})', style=11)
        s.formula_cell(row, 19, f'R{row}/(1+Inputs!B11)', style=11)
        s.formula_cell(row, 20, f'IF(Inputs!B7=1,L{row},MIN(S{row},L{row}))', style=11)
        s.formula_cell(row, 21, f'IF(Inputs!B19=1,MAX(0,T{row}-J{row}),0)', style=11)
        s.formula_cell(row, 22, f'T{row}*(1+Inputs!B11)', style=11)
        s.formula_cell(row, 23, f'V{row}-T{row}', style=11)
        s.formula_cell(row, 24, f'V{row}*Inputs!B13*MIN(12,Inputs!B10)/12', style=11)
        s.formula_cell(row, 25, f'W{row}*Inputs!B14/12', style=11)
        s.formula_cell(row, 26, f'J{row}+U{row}-T{row}+X{row}-Y{row}', style=11)
        s.formula_cell(row, 27, f'D{row}+E{row}-I{row}+U{row}+X{row}-Y{row}', style=11)
        s.formula_cell(
            row,
            28,
            f'IF(U{row}>0,AB{prev}*(1+Inputs!B15/12)+U{row},AB{prev}*(1+Inputs!B15/12))',
            style=11,
        )
        s.formula_cell(row, 29, f'IF(Inputs!B21>0,AA{row}/Inputs!B21,0)', style=9)
        s.formula_cell(row, 30, f'G{row}+T{row}', style=11)
        s.formula_cell(row, 31, f'H{row}+W{row}', style=11)
        s.formula_cell(row, 32, f'AD{row}+AE{row}', style=11)
        s.formula_cell(row, 33, f'IF(M{row}>0,V{row}/M{row},0)', style=13)
        s.formula_cell(row, 34, f'AH{prev}+U{row}', style=11)
        if row == 8:
            s.number(row, 35, 0, style=8)
        else:
            s.formula_cell(
                row,
                35,
                f'IFERROR((1+IRR(VSTACK($AJ$8:INDEX($AJ:$AJ,ROW()-1),-U{row}+AA{row})))^12-1,0)',
                style=8,
            )
        s.formula_cell(row, 36, f'-U{row}', style=11)
    return s


def build_notes_sheet() -> Sheet:
    s = Sheet("Notes")
    s.set_col(1, 28)
    s.set_col(2, 90)
    s.merge("A1:B1")
    s.inline(1, 1, "Model Notes", style=1)
    s.merge("A2:B2")
    s.inline(2, 1, "Contact Reif Tauati · 4176197004 · reif@thegoodproject.net", style=10)
    rows = [
        ("What is modeled?", "This workbook mirrors the deterministic monthly Fund One model from /model over 120 months."),
        ("Capital calls", "If Capital Calls On = 1 and Hardcore Mode = 0, LP capital is called only when needed. If Hardcore Mode = 1, the workbook assumes the full fund is funded upfront and redeployed immediately as cash returns."),
        ("Borrower Rate vs Fund Take", "Borrower Rate is what the developer pays. Fund Take is the retained APY inside the fund after origination partners are paid."),
        ("Debt / Equity", "A value of 0.25 means each $1.00 of LP equity supports $1.25 of loans through $0.25 of debt."),
        ("How origination scales", "Desired origination volume is driven by pipeline capacity and deployable capital. In normal mode the model ramps scaling over 12 months. Hardcore Mode removes that gentler ramp and pushes available cash out immediately."),
        ("IRR", "Projected IRR is solved from LP cash calls and terminal NAV. The Monthly_Model sheet also includes an IRR To Date column."),
    ]
    row = 4
    for label, text in rows:
        s.inline(row, 1, label, style=3)
        s.inline(row, 2, text, style=10)
        row += 1
    return s


def workbook_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <fileVersion appName="xl"/>
 <workbookPr defaultThemeVersion="124226"/>
 <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="22000" windowHeight="12400"/></bookViews>
 <sheets>
  <sheet name="Inputs" sheetId="1" r:id="rId1"/>
  <sheet name="Summary" sheetId="2" r:id="rId2"/>
  <sheet name="Monthly_Model" sheetId="3" r:id="rId3"/>
  <sheet name="Notes" sheetId="4" r:id="rId4"/>
 </sheets>
 <calcPr calcId="191029" calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/>
</workbook>
"""


def workbook_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet4.xml"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def core_xml() -> str:
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>TGP Fund One Model</dc:title>
  <dc:creator>Reif Tauati</dc:creator>
  <cp:lastModifiedBy>OpenAI Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>
"""


def app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Excel</Application>
</Properties>
"""


def build_workbook() -> None:
    sheets = [
        build_inputs_sheet(),
        build_summary_sheet(),
        build_monthly_sheet(),
        build_notes_sheet(),
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml())
        zf.writestr("_rels/.rels", root_rels_xml())
        zf.writestr("docProps/core.xml", core_xml())
        zf.writestr("docProps/app.xml", app_xml())
        zf.writestr("xl/workbook.xml", workbook_xml())
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml())
        zf.writestr("xl/styles.xml", STYLES_XML)
        for i, sheet in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", sheet.build_xml(i))


if __name__ == "__main__":
    build_workbook()
    print(os.fspath(OUT))
