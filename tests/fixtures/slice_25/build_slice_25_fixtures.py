from __future__ import annotations

import argparse
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import xlsxwriter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _build_candidate_workbook(args.output_dir / "candidate_workbook.xlsx")
    return 0


def _build_candidate_workbook(output: Path) -> None:
    workbook = xlsxwriter.Workbook(output)
    workbook.set_properties(
        {
            "author": "dsl_manager fixture",
            "created": datetime(2000, 1, 1),
            "title": "Slice 25 deterministic candidates",
        }
    )
    workbook.set_calc_mode("manual")
    main = workbook.add_worksheet("Main")
    hidden = workbook.add_worksheet("Hidden")
    very_hidden = workbook.add_worksheet("VeryHidden")
    hidden.hide()
    very_hidden.very_hidden()

    main.add_table(
        "A1:B3",
        {
            "name": "Orders",
            "columns": [{"header": "Code"}, {"header": "Amount"}],
            "data": [["A", 10], ["B", 20]],
        },
    )
    main.write_row("E1", ["Code", "Amount"])
    main.write_row("E2", ["A", 10])
    main.write_row("E3", ["B", 20])
    main.write_formula("H1", "=SUM(Orders[Amount])", None, 30)
    main.write_formula("H3", "=SUM(LocalBlock)", None, 30)
    main.write_formula("H5", "='Hidden'!$A$1", None, 7)
    main.write_formula(
        "H7",
        "='https://example.invalid/[external.xlsx]Sheet1'!$A$1",
        None,
        41,
    )
    hidden.write_number("A1", 7)
    very_hidden.write("B2", "very hidden evidence")

    workbook.define_name("GlobalBlock", "=Main!$A$1:$B$3")
    workbook.define_name("LocalBlock", "=Main!$A$2:$B$3")
    workbook.define_name("Main!LocalBlock", "=Main!$E$2:$F$3")
    workbook.close()
    _add_external_link(output)


def _add_external_link(output: Path) -> None:
    with zipfile.ZipFile(output, "r") as package:
        records = [(info, package.read(info)) for info in package.infolist()]
    rewritten: list[tuple[zipfile.ZipInfo, bytes]] = []
    for info, data in records:
        if info.filename == "[Content_Types].xml":
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
                    b'<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/'
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
        b'</externalBook></externalLink>'
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
        (_zip_info("xl/externalLinks/_rels/externalLink1.xml.rels"), relationships),
    ]


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


if __name__ == "__main__":
    raise SystemExit(main())
