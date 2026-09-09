from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import xlsxwriter


SHEET_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--macro-source", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _build_structural_workbook(args.output_dir / "structural_workbook.xlsx")
    shutil.copyfile(args.macro_source, args.output_dir / "macro_workbook.xlsm")
    return 0


def _build_structural_workbook(output: Path) -> None:
    workbook = xlsxwriter.Workbook(output)
    workbook.set_properties(
        {
            "title": "Slice 24 structural workbook",
            "author": "dsl_manager fixture",
            "created": datetime(2000, 1, 1),
        }
    )
    workbook.set_calc_mode("manual")
    visible = workbook.add_worksheet("Résumé")
    hidden = workbook.add_worksheet("隐 藏")
    very_hidden = workbook.add_worksheet("非常")
    hidden.hide()
    very_hidden.very_hidden()

    date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
    blank_format = workbook.add_format({"bg_color": "#FFFFFF"})
    visible.write_row("A1", ["Label", "Left", "Right", "Cached", "No cache", "Error"])
    visible.write("A2", "α")
    visible.write_number("B2", 1)
    visible.write_number("C2", 2.5)
    visible.write_formula("D2", "=B2+C2", None, 3.5)
    visible.write_formula("E2", "=B2*C2", None, 2.5)
    visible.write_formula("F2", "=1/0", None, "#DIV/0!")
    visible.merge_range("A3:B3", "merged")
    visible.write_boolean("C3", True)
    visible.write_datetime("D3", datetime(2024, 2, 29), date_format)
    visible.write_blank("F3", None, blank_format)
    visible.write_formula(
        "H10",
        "='https://example.invalid/[external.xlsx]Sheet1'!$A$1",
        None,
        41,
    )
    visible.write("I10", "separate")

    hidden.write("A1", "hidden")
    hidden.write_number("C3", -7)
    very_hidden.write("B2", "very hidden")

    workbook.define_name("MainBlock", "='Résumé'!$A$1:$F$3")
    workbook.define_name("'Résumé'!LocalPair", "='Résumé'!$H$10:$I$10")
    workbook.close()
    _rewrite_package(output, sheet_part="xl/worksheets/sheet1.xml", coordinate="E2")


def _rewrite_package(output: Path, *, sheet_part: str, coordinate: str) -> None:
    with zipfile.ZipFile(output, "r") as package:
        records = [(info, package.read(info)) for info in package.infolist()]
    rewritten: list[tuple[zipfile.ZipInfo, bytes]] = []
    for info, data in records:
        if info.filename == sheet_part:
            root = ElementTree.fromstring(data)
            for cell in root.iter(f"{{{SHEET_NAMESPACE}}}c"):
                if cell.attrib.get("r") == coordinate:
                    for child in list(cell):
                        if child.tag == f"{{{SHEET_NAMESPACE}}}v":
                            cell.remove(child)
            data = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
        elif info.filename == "[Content_Types].xml":
            data = data.replace(
                b"</Types>",
                (
                    b'<Override PartName="/xl/externalLinks/externalLink1.xml" '
                    b'ContentType="application/vnd.openxmlformats-officedocument.'
                    b'spreadsheetml.externalLink+xml"/></Types>'
                ),
            )
        elif info.filename == "xl/_rels/workbook.xml.rels":
            data = data.replace(
                b"</Relationships>",
                (
                    b'<Relationship Id="rId7" Type="http://schemas.openxmlformats.org/'
                    b'officeDocument/2006/relationships/externalLink" '
                    b'Target="externalLinks/externalLink1.xml"/></Relationships>'
                ),
            )
        rewritten.append((info, data))
    rewritten.extend(_external_link_parts())
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w") as package:
            for info, data in rewritten:
                package.writestr(info, data)
        temporary_path.replace(output)
    finally:
        temporary_path.unlink(missing_ok=True)


def _external_link_parts() -> list[tuple[zipfile.ZipInfo, bytes]]:
    link = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        b'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        b'<externalBook r:id="rId1"><sheetNames><sheetName val="Sheet1"/></sheetNames>'
        b'<sheetDataSet><sheetData sheetId="0"><row r="1"><cell r="A1" t="n">'
        b'<v>41</v></cell></row></sheetData></sheetDataSet></externalBook></externalLink>'
    )
    relationships = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
        b'officeDocument/2006/relationships/externalLinkPath" '
        b'Target="https://example.invalid/external.xlsx" TargetMode="External"/>'
        b'</Relationships>'
    )
    return [
        (_zip_info("xl/externalLinks/externalLink1.xml"), link),
        (
            _zip_info("xl/externalLinks/_rels/externalLink1.xml.rels"),
            relationships,
        ),
    ]


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


if __name__ == "__main__":
    raise SystemExit(main())
