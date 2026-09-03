#!/usr/bin/env python3
"""Apply the Slice 20-29 prompt-link migration to design_document_v_02.md safely.

This helper is intentionally package-only: do not commit it unless you explicitly want to.
It edits only the design file in the target repository and refuses the operation unless
its Git blob SHA matches the baseline verified on GitHub main, unless --force-baseline
is explicitly supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
import tempfile

TARGET_REL = Path('.kb/documenti/documenti di design/run 2/design_document_v_02.md')
EXPECTED_BASELINE_BLOB = '8aa78b1210216b78d97e4e2554b075a7c1b462df'

OLD_AUTOVERIFY = '- [x] Tutti i prompt sono senza placeholder di template e pronti all\'uso.'
NEW_AUTOVERIFY = ('- [x] I prompt canonici esterni delle slice 20–29 sono senza placeholder di template, '
                  'pronti all\'uso, collegati dal design e verificabili nelle rispettive directory di slicing.')

SECTION22 = '''## 22. Prompt di implementazione

I prompt di implementazione completi costituiscono parte normativa del perimetro delle rispettive slice e sono conservati nei seguenti file canonici:

''' + '\n'.join(
    f'- [Slice {n}](../../../projects/slicing/slice_{n:02d}/dsl_manager_slice_{n:02d}_prompt.md)'
    for n in range(20, 30)
) + '''

Il presente design governa requisiti funzionali, invarianti e confini. I prompt esterni ne costituiscono il contratto operativo di esecuzione; `AGENTS.md` governa ambiente, processo e convenzioni del repository.

In caso di contraddizione non risolvibile secondo queste responsabilità, non introdurre una nuova decisione progettuale silenziosa: documentare il conflitto e correggere la fonte normativa appropriata prima di proseguire.

In caso di modifica a un prompt canonico, aggiornare la tracciabilità del design senza reintrodurre copie duplicate dei prompt in questo documento.
'''


def git_blob_sha(data: bytes) -> str:
    header = f'blob {len(data)}\0'.encode('ascii')
    return hashlib.sha1(header + data).hexdigest()


def transform(data: bytes) -> bytes:
    # Decode only to perform exact UTF-8 token replacement; byte sequences not replaced
    # round-trip unchanged. The expected Git blob guard prevents applying to an unknown baseline.
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise RuntimeError(f'design is not valid UTF-8: {exc}') from exc

    for n in range(20, 30):
        old = f'(#prompt-slice-{n})'
        new = f'(../../../projects/slicing/slice_{n:02d}/dsl_manager_slice_{n:02d}_prompt.md)'
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f'expected exactly one {old!r}, found {count}')
        text = text.replace(old, new, 1)

    count = text.count(OLD_AUTOVERIFY)
    if count != 1:
        raise RuntimeError(f'expected exactly one legacy auto-verification line, found {count}')
    text = text.replace(OLD_AUTOVERIFY, NEW_AUTOVERIFY, 1)

    marker = '## 22. Prompt di implementazione\n'
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError('section 22 marker not found')
    if text.find(marker, pos + 1) >= 0:
        raise RuntimeError('section 22 marker is duplicated')
    text = text[:pos] + SECTION22

    # Postconditions.
    if '#prompt-slice-' in text:
        raise RuntimeError('old prompt anchors still present after transformation')
    if '### Prompt Slice ' in text:
        raise RuntimeError('embedded prompt blocks still present after transformation')
    for n in range(20, 30):
        link = f'../../../projects/slicing/slice_{n:02d}/dsl_manager_slice_{n:02d}_prompt.md'
        if text.count(link) != 2:
            raise RuntimeError(f'expected two links for Slice {n}, found {text.count(link)}')
    if NEW_AUTOVERIFY not in text:
        raise RuntimeError('updated auto-verification line missing')
    return text.encode('utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description='Safely update DSL Manager design v02 prompt references.')
    ap.add_argument('repo_root', nargs='?', default='.', help='dsl_manager-v1 repository root (default: current directory)')
    ap.add_argument('--check', action='store_true', help='validate and show the prospective result without writing')
    ap.add_argument('--force-baseline', action='store_true', help='allow a baseline Git blob SHA different from the verified main SHA')
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    target = root / TARGET_REL
    if not target.is_file():
        print(f'ERROR: design file not found: {target}', file=sys.stderr)
        return 2

    original = target.read_bytes()
    before_blob = git_blob_sha(original)
    if before_blob != EXPECTED_BASELINE_BLOB and not args.force_baseline:
        print('ERROR: baseline does not match the GitHub main file verified for this package.', file=sys.stderr)
        print(f'  expected Git blob: {EXPECTED_BASELINE_BLOB}', file=sys.stderr)
        print(f'  actual Git blob:   {before_blob}', file=sys.stderr)
        print('Refuse to edit. Rebase/update or inspect the differences first.', file=sys.stderr)
        return 3

    try:
        updated = transform(original)
    except RuntimeError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 4

    print(f'baseline_git_blob={before_blob}')
    print(f'output_git_blob={git_blob_sha(updated)}')
    print(f'output_sha256={hashlib.sha256(updated).hexdigest()}')
    print(f'bytes_before={len(original)} bytes_after={len(updated)}')

    if args.check:
        print('CHECK PASS: transformation is applicable; no file written.')
        return 0

    # Atomic write in the same directory; mode bits are preserved where possible.
    mode = target.stat().st_mode
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + '.', suffix='.tmp', dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(updated)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()

    print(f'UPDATED: {TARGET_REL.as_posix()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
