from __future__ import annotations

import hashlib
import io
import json
import shutil
import socket
import sqlite3
import warnings
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from dsl_mngr.cli.app import main
from dsl_mngr.core.config import DEFAULT_CONFIG, EXCEL_HARD_MAXIMA, ProjectConfigError, load_config
from dsl_mngr.core.batch import _actions_for_revision
from dsl_mngr.core.docling_adapter import (
    DoclingNormalizationResult,
    normalize_excel_stream_with_docling,
    resolve_docling_options,
)
from dsl_mngr.core.migrations import migrate_workspace_database
from dsl_mngr.core.ooxml_preflight import (
    ExcelLimits,
    OoxmlPreflightError,
    XLSM_WORKBOOK_CONTENT_TYPE,
    XLSX_WORKBOOK_CONTENT_TYPE,
    acquire_source_once,
    enforce_output_budget,
    preflight_ooxml,
)
from dsl_mngr.core.runs import start_run
from dsl_mngr.core.worker_runner import memory_limit_mode, run_worker
from dsl_mngr.core.workspace import initialize_workspace
from dsl_mngr.workers import normalize_docling


FIXTURES = Path(__file__).parent / "fixtures" / "slice_23"
REAL_XLSX = FIXTURES / "real_workbook.xlsx"
REAL_XLSM = FIXTURES / "real_macro_workbook.xlsm"
CHECKSUMS = json.loads((FIXTURES / "checksums.json").read_text(encoding="utf-8"))
DEFAULT_LIMITS = ExcelLimits.from_config(DEFAULT_CONFIG["excel"])


def test_slice_23_real_xlsx_docling(tmp_path, capsys):
    workspace, revision_id = _registered_workspace(tmp_path, capsys, REAL_XLSX)

    assert main(["corpus", "normalize", str(workspace), "--revision", revision_id]) == 0
    capsys.readouterr()
    output_dir = workspace / "normalized" / "SRC_000001" / revision_id
    first_outputs = {
        name: (output_dir / name).read_bytes()
        for name in ("normalized.json", "normalized.md", "ooxml_preflight_report.json")
    }
    report = _read_json(output_dir / "ooxml_preflight_report.json")
    assert report["input"]["docling_input_format"] == "xlsx"
    assert report["input"]["extension"] == ".xlsx"
    assert report["input"]["source_hash"] == CHECKSUMS[REAL_XLSX.name]
    assert report["input"]["source_hash"] == report["input"]["docling_stream_hash"]
    assert report["input"]["source_open_count"] == 1
    assert report["package"]["workbook_content_type"] == XLSX_WORKBOOK_CONTENT_TYPE
    assert report["docling"] == {
        "conversion_status": "success",
        "input_format": "xlsx",
        "version": "2.97.0",
    }
    assert report["network_accessed"] is False
    assert report["external_targets_dereferenced"] is False
    _assert_catalog(report["catalog"], status="completed", reason="success", exit_code=0)
    assert "Ada" in (output_dir / "normalized.md").read_text(encoding="utf-8")

    process_report = _read_json(
        workspace / "artifacts" / "runs" / "RUN_000001" / "process_report.json"
    )
    resources = process_report["workers"][0]["resource_limits"]
    assert resources["memory_limit_mode"] == memory_limit_mode(
        DEFAULT_CONFIG["excel"]["worker_memory_bytes"]
    )
    assert resources["termination_reason"] is None

    assert main(["corpus", "normalize", str(workspace), "--revision", revision_id]) == 0
    capsys.readouterr()
    second_outputs = {name: (output_dir / name).read_bytes() for name in first_outputs}
    assert second_outputs == first_outputs


def test_slice_23_real_xlsm_docling(tmp_path, capsys):
    workspace, revision_id = _registered_workspace(tmp_path, capsys, REAL_XLSM)

    assert main(["corpus", "normalize", str(workspace), "--revision", revision_id]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    output_dir = workspace / "normalized" / "SRC_000001" / revision_id
    report = _read_json(output_dir / "ooxml_preflight_report.json")
    assert report["input"]["extension"] == ".xlsm"
    assert report["input"]["source_hash"] == CHECKSUMS[REAL_XLSM.name]
    assert report["input"]["source_hash"] == report["input"]["docling_stream_hash"]
    assert report["package"]["workbook_content_type"] == XLSM_WORKBOOK_CONTENT_TYPE
    assert report["docling"]["input_format"] == "xlsx"
    assert report["docling"]["version"] == "2.97.0"
    assert report["macros_executed"] is False
    assert "Ada" in (output_dir / "normalized.md").read_text(encoding="utf-8")


def test_slice_23_single_byte_sequence(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    source = workspace / "corpus" / "active" / REAL_XLSX.name
    source.parent.mkdir(parents=True)
    shutil.copyfile(REAL_XLSX, source)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    opened = 0
    original_open = Path.open

    def counting_open(path: Path, *args, **kwargs):
        nonlocal opened
        mode = args[0] if args else kwargs.get("mode", "r")
        if path.resolve() == source.resolve() and "r" in mode:
            opened += 1
        return original_open(path, *args, **kwargs)

    def fake_docling(stream, *, original_name, docling_options):
        assert original_name == REAL_XLSX.name
        assert hashlib.sha256(stream.getbuffer()).hexdigest() == source_hash
        return _fake_normalization("success")

    monkeypatch.setattr(Path, "open", counting_open)
    monkeypatch.setattr(normalize_docling, "normalize_excel_stream_with_docling", fake_docling)
    output = normalize_docling.normalize(
        _worker_payload(source_hash),
        workspace_dir=workspace,
    )

    assert opened == 1
    assert output["source_hash"] == source_hash
    report = _read_json(workspace / output["ooxml_preflight_report_path"])
    assert report["input"]["source_hash"] == source_hash
    assert report["input"]["docling_stream_hash"] == source_hash
    assert report["input"]["source_open_count"] == 1

    with pytest.raises(OoxmlPreflightError) as mismatch:
        acquire_source_once(
            source,
            expected_hash="0" * 64,
            max_file_bytes=len(REAL_XLSX.read_bytes()),
        )
    assert mismatch.value.reason == "source_revision_changed"
    assert mismatch.value.status == "failed"
    assert mismatch.value.exit_code == 4
    assert mismatch.value.source_hash == source_hash


def test_slice_23_ooxml_attacks():
    base_entries = _entries(REAL_XLSX.read_bytes())
    workbook = _entry_bytes(base_entries, "xl/workbook.xml")
    workbook_rels = _entry_bytes(base_entries, "xl/_rels/workbook.xml.rels")
    content_types = _entry_bytes(base_entries, "[Content_Types].xml")
    vml_content_types = _insert_xml(
        content_types,
        '<Default Extension="vml" ContentType="application/vnd.openxmlformats-officedocument.vmlDrawing"/>',
        "Types",
    )
    vml_attack_entries = [
        (
            name,
            vml_content_types if name == "[Content_Types].xml" else data,
        )
        for name, data in base_entries
    ]

    attacks = {
        "traversal": _zip([*base_entries, ("../escape.xml", b"<x/>")]),
        "absolute": _zip([*base_entries, ("/absolute.xml", b"<x/>")]),
        "drive": _zip([*base_entries, ("C:/escape.xml", b"<x/>")]),
        "percent_traversal": _zip([*base_entries, ("%2e%2e/escape.xml", b"<x/>")]),
        "percent_collision": _zip(
            [*base_entries, ("xl/%77orkbook.xml", workbook)]
        ),
        "double_separator": _zip([*base_entries, ("xl//escape.xml", b"<x/>")]),
        "duplicate": _zip([*base_entries, ("xl/workbook.xml", workbook)]),
        "case_fold": _zip([*base_entries, ("XL/workbook.xml", workbook)]),
        "dtd": _replace_entry(
            base_entries,
            "xl/workbook.xml",
            b'<!DOCTYPE workbook [<!ENTITY xxe SYSTEM "file:///forbidden">]>' + workbook,
        ),
        "vml_dtd": _zip(
            [
                *vml_attack_entries,
                (
                    "xl/drawings/attack.vml",
                    b'<!DOCTYPE xml [<!ENTITY xxe SYSTEM "file:///forbidden">]><xml/>',
                ),
            ]
        ),
        "duplicate_relationship": _replace_entry(
            base_entries,
            "xl/_rels/workbook.xml.rels",
            _insert_xml(
                workbook_rels,
                '<Relationship Id="rId1" Type="urn:duplicate" Target="worksheets/sheet1.xml"/>',
                "Relationships",
            ),
        ),
        "invalid_internal_target": _replace_entry(
            base_entries,
            "xl/_rels/workbook.xml.rels",
            workbook_rels.replace(b"worksheets/sheet1.xml", b"../../escape.xml", 1),
        ),
        "invalid_external_target": _replace_entry(
            base_entries,
            "xl/_rels/workbook.xml.rels",
            _insert_xml(
                workbook_rels,
                '<Relationship Id="rIdExternal" Type="urn:external" Target="file:///secret" TargetMode="External"/>',
                "Relationships",
            ),
        ),
        "malformed_external_target": _replace_entry(
            base_entries,
            "xl/_rels/workbook.xml.rels",
            _insert_xml(
                workbook_rels,
                '<Relationship Id="rIdMalformed" Type="urn:external" Target="https://[invalid" TargetMode="External"/>',
                "Relationships",
            ),
        ),
        "duplicate_default": _replace_entry(
            base_entries,
            "[Content_Types].xml",
            _insert_xml(
                content_types,
                '<Default Extension="xml" ContentType="application/xml"/>',
                "Types",
            ),
        ),
        "duplicate_override": _replace_entry(
            base_entries,
            "[Content_Types].xml",
            _insert_xml(
                content_types,
                f'<Override PartName="/xl/workbook.xml" ContentType="{XLSX_WORKBOOK_CONTENT_TYPE}"/>',
                "Types",
            ),
        ),
        "missing_content_types": _zip(
            [(name, data) for name, data in base_entries if name != "[Content_Types].xml"]
        ),
        "missing_root_relationships": _zip(
            [(name, data) for name, data in base_entries if name != "_rels/.rels"]
        ),
        "missing_workbook": _zip(
            [(name, data) for name, data in base_entries if name != "xl/workbook.xml"]
        ),
        "missing_workbook_relationships": _zip(
            [
                (name, data)
                for name, data in base_entries
                if name != "xl/_rels/workbook.xml.rels"
            ]
        ),
        "invalid_central_directory": REAL_XLSX.read_bytes()[:-32],
    }

    for attack_name, data in attacks.items():
        with pytest.raises(OoxmlPreflightError) as rejected:
            _preflight(data, REAL_XLSX.name)
        expected_reason = (
            "ooxml_external_target_invalid"
            if attack_name in {"invalid_external_target", "malformed_external_target"}
            else "ooxml_security_violation"
        )
        assert rejected.value.reason == expected_reason, attack_name
        assert rejected.value.exit_code == 3, attack_name


def test_slice_23_extension_content_type_must_match():
    with pytest.raises(OoxmlPreflightError, match="content type") as xlsx_as_xlsm:
        _preflight(REAL_XLSX.read_bytes(), "renamed.xlsm")
    assert xlsx_as_xlsm.value.reason == "ooxml_security_violation"

    with pytest.raises(OoxmlPreflightError, match="content type") as xlsm_as_xlsx:
        _preflight(REAL_XLSM.read_bytes(), "renamed.xlsx")
    assert xlsm_as_xlsx.value.reason == "ooxml_security_violation"


def test_slice_23_cli_catalog_failures(tmp_path, capsys):
    changed_workspace, revision_id = _registered_workspace(
        tmp_path / "changed", capsys, REAL_XLSX
    )
    changed_source = changed_workspace / "corpus" / "active" / REAL_XLSX.name
    changed_source.write_bytes(changed_source.read_bytes() + b"changed")
    assert (
        main(
            [
                "corpus",
                "normalize",
                str(changed_workspace),
                "--revision",
                revision_id,
            ]
        )
        == 4
    )
    captured = capsys.readouterr()
    assert "exit_code=4" in captured.err
    changed_output = changed_workspace / "normalized" / "SRC_000001" / revision_id
    changed_report = _read_json(changed_output / "ooxml_preflight_report.json")
    assert changed_report["catalog"]["reason"] == "source_revision_changed"
    _assert_catalog(
        changed_report["catalog"],
        status="failed",
        reason="source_revision_changed",
        exit_code=4,
    )
    assert changed_report["status"] == "failed"
    assert not (changed_output / "normalized.json").exists()

    malicious_workspace = tmp_path / "malicious" / "workspace"
    assert main(["init", str(malicious_workspace)]) == 0
    assert main(["db", "init", str(malicious_workspace)]) == 0
    malicious = malicious_workspace / "corpus" / "active" / "attack.xlsx"
    malicious.write_bytes(
        _zip([*_entries(REAL_XLSX.read_bytes()), ("../escape.xml", b"<x/>")])
    )
    assert main(["corpus", "scan", str(malicious_workspace)]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "corpus",
                "normalize",
                str(malicious_workspace),
                "--revision",
                "REV_000001",
            ]
        )
        == 3
    )
    captured = capsys.readouterr()
    assert "exit_code=3" in captured.err
    rejected_report = _read_json(
        malicious_workspace
        / "normalized"
        / "SRC_000001"
        / "REV_000001"
        / "ooxml_preflight_report.json"
    )
    assert rejected_report["catalog"]["reason"] == "ooxml_security_violation"
    _assert_catalog(
        rejected_report["catalog"],
        status="rejected",
        reason="ooxml_security_violation",
        exit_code=3,
    )
    assert rejected_report["status"] == "rejected"


def test_slice_23_limits_at_boundary_and_over(tmp_path):
    stored = _zip(_entries(REAL_XLSX.read_bytes()), compression=zipfile.ZIP_STORED)
    entries = _entries(stored)
    declared_total = sum(len(data) for _, data in entries)
    max_xml = max(
        len(data)
        for name, data in entries
        if name == "[Content_Types].xml" or name.endswith((".xml", ".rels"))
    )
    baseline = _preflight(
        stored,
        REAL_XLSX.name,
        limits=replace(
            DEFAULT_LIMITS,
            max_zip_entries=len(entries),
            max_uncompressed_bytes=declared_total,
            max_compression_ratio=1,
            max_xml_part_bytes=max_xml,
            max_relationships=7,
            max_sheets=1,
        ),
    )
    assert baseline.zip_entries == len(entries)
    assert baseline.uncompressed_bytes == declared_total
    assert baseline.relationships == 7
    assert baseline.sheets == 1

    over_cases = (
        replace(DEFAULT_LIMITS, max_zip_entries=len(entries) - 1),
        replace(DEFAULT_LIMITS, max_uncompressed_bytes=declared_total - 1),
        replace(DEFAULT_LIMITS, max_compression_ratio=1),
        replace(DEFAULT_LIMITS, max_xml_part_bytes=max_xml - 1),
        replace(DEFAULT_LIMITS, max_relationships=6),
        replace(DEFAULT_LIMITS, max_sheets=0),
    )
    for index, limits in enumerate(over_cases):
        data = REAL_XLSX.read_bytes() if index == 2 else stored
        with pytest.raises(OoxmlPreflightError) as exceeded:
            _preflight(data, REAL_XLSX.name, limits=limits)
        assert exceeded.value.reason == "ooxml_budget_exceeded"

    source = tmp_path / REAL_XLSX.name
    shutil.copyfile(REAL_XLSX, source)
    source_hash = CHECKSUMS[REAL_XLSX.name]
    assert acquire_source_once(
        source, expected_hash=source_hash, max_file_bytes=source.stat().st_size
    ).sha256 == source_hash
    with pytest.raises(OoxmlPreflightError) as file_over:
        acquire_source_once(
            source,
            expected_hash=source_hash,
            max_file_bytes=source.stat().st_size - 1,
        )
    assert file_over.value.reason == "ooxml_budget_exceeded"

    serialized = {"a": "12", "b": "345"}
    assert enforce_output_budget(serialized, 5) == 5
    with pytest.raises(OoxmlPreflightError) as output_over:
        enforce_output_budget(serialized, 4)
    assert output_over.value.reason == "ooxml_budget_exceeded"


def test_slice_23_streaming_limit_uses_actual_bytes(monkeypatch):
    data = REAL_XLSM.read_bytes()
    declared_total = sum(info.file_size for info in zipfile.ZipFile(io.BytesIO(data)).infolist())
    original_open = zipfile.ZipFile.open

    def longer_stream(package, member, *args, **kwargs):
        opened = original_open(package, member, *args, **kwargs)
        name = member.filename if isinstance(member, zipfile.ZipInfo) else str(member)
        if name != "xl/vbaProject.bin":
            return opened
        with opened:
            return io.BytesIO(opened.read() + b"unexpected")

    monkeypatch.setattr(zipfile.ZipFile, "open", longer_stream)
    with pytest.raises(OoxmlPreflightError) as exceeded:
        _preflight(
            data,
            REAL_XLSM.name,
            limits=replace(DEFAULT_LIMITS, max_uncompressed_bytes=declared_total),
        )
    assert exceeded.value.reason == "ooxml_budget_exceeded"


def test_slice_23_real_external_link_is_never_dereferenced(monkeypatch):
    entries = _entries(REAL_XLSX.read_bytes())
    rels = _entry_bytes(entries, "xl/_rels/workbook.xml.rels")
    package = _replace_entry(
        entries,
        "xl/_rels/workbook.xml.rels",
        _insert_xml(
            rels,
            '<Relationship Id="rIdExternal" Type="urn:external" Target="https://127.0.0.1:9/unreachable" TargetMode="External"/>',
            "Relationships",
        ),
    )

    def network_forbidden(*args, **kwargs):
        raise AssertionError("network dereference attempted")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    result = _preflight(package, REAL_XLSX.name)
    assert result.external_relationships == 1
    assert result.report()["external_targets_dereferenced"] is False
    normalized = normalize_excel_stream_with_docling(
        io.BytesIO(package),
        original_name=REAL_XLSX.name,
        docling_options={"input_formats": "xlsx,xlsm"},
    )
    assert normalized.conversion_status == "success"
    assert "Ada" in normalized.markdown


def test_slice_23_worker_timeout_output_and_memory_modes(tmp_path):
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace)
    migrate_workspace_database(workspace)

    timeout_worker = _worker_script(tmp_path / "timeout_worker.py", "import time; time.sleep(5)")
    timeout_run = start_run(workspace, run_type="normalize")
    timeout_result = run_worker(
        workspace,
        run_id=timeout_run.record.run_id,
        worker_name="timeout_worker",
        worker_path=timeout_worker,
        timeout_seconds=0.1,
        max_output_bytes=1024,
    )
    assert timeout_result.status == "failed"
    assert timeout_result.exit_code == 5
    assert "timed out" in str(timeout_result.error)
    assert _worker_resources(timeout_run.artifacts.process_report_path)["termination_reason"] == "timeout"
    assert _worker_resources(timeout_run.artifacts.process_report_path)["catalog"]["reason"] == (
        "normalization_operational_failure"
    )

    output_worker = _worker_script(
        tmp_path / "output_worker.py",
        "import time; print('x' * 100000, flush=True); time.sleep(5)",
    )
    output_run = start_run(workspace, run_type="normalize")
    output_result = run_worker(
        workspace,
        run_id=output_run.record.run_id,
        worker_name="output_worker",
        worker_path=output_worker,
        timeout_seconds=5,
        max_output_bytes=128,
    )
    assert output_result.status == "failed"
    assert output_result.exit_code == 5
    assert "output exceeded" in str(output_result.error)
    assert _worker_resources(output_run.artifacts.process_report_path)["termination_reason"] == "output_limit"

    memory_worker = _worker_script(
        tmp_path / "memory_worker.py",
        "import time; payload=bytearray(20_000_000); time.sleep(5)",
    )
    memory_run = start_run(workspace, run_type="normalize")
    memory_result = run_worker(
        workspace,
        run_id=memory_run.record.run_id,
        worker_name="memory_worker",
        worker_path=memory_worker,
        timeout_seconds=5,
        max_output_bytes=1024,
        memory_limit_bytes=1_000_000,
    )
    resources = _worker_resources(memory_run.artifacts.process_report_path)
    assert memory_result.status == "failed"
    assert resources["memory_limit_mode"] == memory_limit_mode(1_000_000)
    if resources["memory_limit_mode"] == "monitored":
        assert resources["termination_reason"] == "memory_limit"
        assert "monitored+kill" in str(memory_result.error)
    else:
        assert memory_result.exit_code != 0


def test_slice_23_partial_is_distinct_and_atomic(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    source = workspace / "corpus" / "active" / REAL_XLSX.name
    source.parent.mkdir(parents=True)
    shutil.copyfile(REAL_XLSX, source)
    source_hash = CHECKSUMS[REAL_XLSX.name]
    monkeypatch.setattr(
        normalize_docling,
        "normalize_excel_stream_with_docling",
        lambda *args, **kwargs: _fake_normalization("partial_success"),
    )

    output = normalize_docling.normalize(_worker_payload(source_hash), workspace_dir=workspace)
    assert output["status"] == "partial"
    assert output["exit_code"] == 6
    output_dir = workspace / "normalized" / "SRC_000001" / "REV_000001"
    report = _read_json(output_dir / "docling_report.json")
    assert report["status"] == "partial"
    assert report["catalog"]["reason"] == "normalization_partial"
    assert report["catalog"]["exit_code"] == 6
    assert not list(output_dir.glob(".normalize_*"))

    initialize_workspace(workspace)
    migrate_workspace_database(workspace)
    partial_worker = _worker_script(
        tmp_path / "partial_worker.py",
        """import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
Path(args.output).write_text(
    json.dumps({
        "run_id": payload["run_id"],
        "status": "partial",
        "worker_name": payload["worker_name"],
    }) + "\\n",
    encoding="utf-8",
)
raise SystemExit(6)""",
    )
    partial_run = start_run(workspace, run_type="normalize")
    partial_result = run_worker(
        workspace,
        run_id=partial_run.record.run_id,
        worker_name="partial_worker",
        worker_path=partial_worker,
        accepted_exit_codes=(0, 6),
    )
    assert partial_result.status == "partial"
    assert partial_result.exit_code == 6
    assert _read_json(partial_run.artifacts.process_report_path)["status"] == "partial"


def test_slice_23_configuration_and_legacy_routes(tmp_path):
    initialize_workspace(tmp_path / "workspace")
    config = load_config(tmp_path / "workspace")
    assert config["excel"] == DEFAULT_CONFIG["excel"]
    profile = (tmp_path / "workspace" / "configs" / "workers" / "docling.no_images.yaml").read_text(
        encoding="utf-8"
    )
    assert "xlsx,xlsm" in profile
    assert resolve_docling_options({"input_formats": "pdf,docx,pptx,html,md,txt"})[
        "input_formats"
    ] == ["PDF", "DOCX", "PPTX", "HTML", "MD"]
    assert _actions_for_revision(
        tmp_path, {"source_type": "unknown", "file_path": "book.xlsx"}
    ) == ["normalize", "chunk"]
    assert _actions_for_revision(
        tmp_path, {"source_type": "unknown", "file_path": "book.xlsm"}
    ) == ["normalize", "chunk"]
    assert _actions_for_revision(
        tmp_path, {"source_type": "legacy_document", "file_path": "manual.md"}
    ) == ["normalize", "chunk"]

    project = tmp_path / "workspace" / "configs" / "project.yaml"
    project.write_text(
        project.read_text(encoding="utf-8").replace(
            "  max_zip_entries: 20000",
            f"  max_zip_entries: {EXCEL_HARD_MAXIMA['max_zip_entries'] + 1}",
        ),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ProjectConfigError, match="hard maximum"):
        load_config(tmp_path / "workspace")


def _registered_workspace(tmp_path: Path, capsys, fixture: Path) -> tuple[Path, str]:
    workspace = tmp_path / "workspace"
    assert main(["init", str(workspace)]) == 0
    assert main(["db", "init", str(workspace)]) == 0
    shutil.copyfile(fixture, workspace / "corpus" / "active" / fixture.name)
    assert main(["corpus", "scan", str(workspace)]) == 0
    capsys.readouterr()
    with sqlite3.connect(workspace / "workspace.sqlite") as connection:
        revision_id = connection.execute(
            "SELECT source_revision_id FROM source_revisions"
        ).fetchone()[0]
    return workspace, str(revision_id)


def _preflight(
    data: bytes,
    name: str,
    *,
    limits: ExcelLimits = DEFAULT_LIMITS,
):
    return preflight_ooxml(
        io.BytesIO(data),
        original_name=name,
        source_hash=hashlib.sha256(data).hexdigest(),
        limits=limits,
    )


def _entries(data: bytes) -> list[tuple[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        return [(info.filename, package.read(info)) for info in package.infolist()]


def _entry_bytes(entries: list[tuple[str, bytes]], name: str) -> bytes:
    return next(data for entry_name, data in entries if entry_name == name)


def _zip(
    entries: list[tuple[str, bytes]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(output, "w", compression=compression) as package:
            for name, data in entries:
                package.writestr(name, data)
    return output.getvalue()


def _replace_entry(entries: list[tuple[str, bytes]], name: str, replacement: bytes) -> bytes:
    return _zip(
        [
            (entry_name, replacement if entry_name == name else data)
            for entry_name, data in entries
        ]
    )


def _insert_xml(data: bytes, element: str, closing_name: str) -> bytes:
    marker = f"</{closing_name}>".encode()
    return data.replace(marker, element.encode() + marker, 1)


def _fake_normalization(status: str) -> DoclingNormalizationResult:
    return DoclingNormalizationResult(
        markdown="# Customers\n\nAda\n",
        document={"name": "real_workbook", "schema_name": "DoclingDocument"},
        docling_version="2.97.0",
        resolved_options={"input_formats": ["XLSX"]},
        conversion_status=status,
    )


def _worker_payload(source_hash: str) -> dict[str, object]:
    return {
        "run_id": "RUN_000001",
        "source_id": "SRC_000001",
        "source_revision_id": "REV_000001",
        "input_path": f"corpus/active/{REAL_XLSX.name}",
        "output_dir": "normalized/SRC_000001/REV_000001",
        "profile": "docling.no_images",
        "worker_config": {"name": "normalize_docling", "version": "1.0"},
        "docling_options": {"input_formats": "xlsx,xlsm"},
        "expected_source_hash": source_hash,
        "excel_limits": dict(DEFAULT_CONFIG["excel"]),
        "memory_limit_mode": memory_limit_mode(DEFAULT_CONFIG["excel"]["worker_memory_bytes"]),
    }


def _worker_script(path: Path, body: str) -> Path:
    path.write_text(body + "\n", encoding="utf-8", newline="\n")
    return path


def _worker_resources(report_path: Path) -> dict[str, object]:
    return _read_json(report_path)["workers"][0]["resource_limits"]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_catalog(
    catalog: dict,
    *,
    status: str,
    reason: str,
    exit_code: int,
) -> None:
    assert {
        "artifact_paths",
        "catalog_version",
        "condition",
        "counters",
        "exit_code",
        "mutations",
        "outcome",
        "reason",
        "retryable",
        "run_id",
        "severity",
        "status",
        "subject_ids",
    } <= set(catalog)
    assert catalog["catalog_version"] == 1
    assert catalog["status"] == status
    assert catalog["reason"] == reason
    assert catalog["exit_code"] == exit_code
