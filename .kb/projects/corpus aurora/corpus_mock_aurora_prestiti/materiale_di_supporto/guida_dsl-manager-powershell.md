# Guida Aurora per `dsl-manager` — PowerShell

Questa guida usa la directory reale del corpus nel repository. Tutte le
operazioni sono locali: gli external link Excel non vengono aperti, le macro
non vengono eseguite e non e' prevista alcuna chiamata AI o di rete. I file
`.xlsx` e `.xlsm` sono letti direttamente: il `.xlsm` non viene convertito.

## 1. Preparare progetto, corpus e workspace

Aprire PowerShell nella root di `dsl_manager-v1`. In ambiente Windows/VS Code
usare esclusivamente l'interprete configurato per il progetto:

```powershell
$PY = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$AURORA = (Resolve-Path ".\.kb\projects\corpus aurora\corpus_mock_aurora_prestiti").Path
$SOURCE = Join-Path $AURORA "corpus\active"
$WS = Join-Path (Get-Location) "laboratorio_aurora"

& $PY --version
& $PY -m pip install -e ".[dev]"
& $PY -m dsl_mngr init $WS
& $PY -m dsl_mngr db init $WS
Get-ChildItem -LiteralPath $SOURCE | Copy-Item -Destination (Join-Path $WS "corpus\active") -Recurse -Force
```

Il workspace deve ricevere soltanto le 18 fonti sotto `corpus/active`. Le due
fixture in `materiale_di_supporto/fixture_controllate` sono casi di test e non
fonti operative.

## 2. Verificare i checksum prima dello scan

```powershell
$MANIFEST = Get-Content -Raw -LiteralPath (Join-Path $AURORA "materiale_di_supporto\checksums.json") | ConvertFrom-Json
$MANIFEST.files.PSObject.Properties | ForEach-Object {
    $REL = $_.Name
    $EXPECTED = $_.Value.sha256
    $ACTUAL = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $AURORA $REL)).Hash.ToLowerInvariant()
    if ($ACTUAL -ne $EXPECTED) { throw "Checksum non valido: $REL" }
}
```

Il workbook principale deve avere SHA-256
`8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081`;
il `.xlsm` deve avere SHA-256
`17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4`.

## 3. Registrare e consolidare

```powershell
& $PY -m dsl_mngr corpus scan $WS
& $PY -m dsl_mngr corpus scan $WS
& $PY -m dsl_mngr batch consolidate $WS
```

Il primo scan registra 18 fonti; il secondo deve riportarle `Unchanged`. Il
batch normalizza documenti e workbook, crea frammenti per DDL, XML form,
PL/SQL e log, deriva candidati deterministici, applica soltanto le review
automatiche consentite e fonde esclusivamente i candidati confermati.

La normalizzazione Docling e' isolata e puo' richiedere diversi minuti. Non
rilanciare il batch mentre i worker sono ancora attivi. In caso di interruzione
usare l'ID della run fallita:

```powershell
& $PY -m dsl_mngr batch consolidate $WS --resume RUN_000001
```

Il retry deve riusare i checkpoint completati senza duplicare candidati o
supporti.

## 4. Controllare artefatti Excel e sicurezza

Per ogni XLSX/XLSM valido cercare nella directory `normalized/<SRC>/<REV>/`:

```text
normalized.json
normalized.md
docling_report.json
ooxml_preflight_report.json
workbook_manifest.json
workbook_fragments.jsonl
workbook_report.json
```

Nel manifest di `matrice_stati_2025.xlsx` verificare tre fogli, cinque regioni,
formula/cached value, merged e named range, sei tipi cella e l'external link
con `not_dereferenced`. Nel report del `.xlsm` verificare
`macros_executed: false` e `network_accessed: false`.
Il manifest e' la vista strutturale; il testo Docling e le formule non sono
automaticamente verita' di dominio.

Il malformed e il partial sono verificati dal test mirato, che inietta
`partial_success` senza alterare i byte del workbook valido:

```powershell
& $PY -m pytest -q tests/test_slice_28_aurora_e2e.py
```

## 5. Review governata e merge

Elencare e ispezionare i candidati pending:

```powershell
& $PY -m dsl_mngr candidates review list $WS --outcome pending
& $PY -m dsl_mngr candidates review show $WS CREC_000001
```

Confermare solo dopo aver confrontato `evidence_text`, locator e fonte:

```powershell
& $PY -m dsl_mngr candidates review confirm $WS CREC_000001 --actor-id aurora-reviewer --reason "evidenza verificata"
& $PY -m dsl_mngr facts merge $WS --batch CBATCH_000001
```

Sostituire gli ID con quelli mostrati dai report. Le relazioni Excel e le date
estratte restano pending per default. In particolare, una data nel nome o nei
metadata non prova da sola la validita' di una regola.
Se si corregge un candidato gia' materializzato, la correzione crea una nuova
foglia e puo' aprire una riconciliazione:

```powershell
& $PY -m dsl_mngr candidates review correct $WS CREC_000001 --actor-id aurora-reviewer --reason "valore corretto" --payload corrections/CREC_000001.json
& $PY -m dsl_mngr facts reconcile $WS
```

Un pending non e' mergeabile; `--strict-review` rende questa precondizione un
errore atomico anziche' uno skip.

## 6. Temporalita', DSL v1/v2, diff e GEXF dinamico

Le due dichiarazioni `2025-11-18` sono concordanti; la dichiarazione storica
`2012-06-01` e quella corrente sono discordanti quando attribuite allo stesso
fatto. Il conflitto deve restare aperto e non deve generare un intervallo
efficace senza review.

Dopo le review necessarie:

```powershell
& $PY -m dsl_mngr dsl render $WS --schema-version 1
& $PY -m dsl_mngr dsl render $WS --schema-version 2
& $PY -m dsl_mngr dsl diff $WS --from DSL_000001 --to DSL_000002 --cross-schema
& $PY -m dsl_mngr graph export $WS --snapshot-id DSL_000002 --dynamic
```

Con riconciliazioni aperte, schema 1 e schema 2 sono bloccati per default. Solo
schema 2 puo' produrre una vista incompleta esplicita; i pending restano non
mergeabili e gli oggetti non effettivi vengono omessi con warning:

```powershell
& $PY -m dsl_mngr dsl render $WS --schema-version 2 --allow-incomplete
& $PY -m dsl_mngr graph export $WS --snapshot-id DSL_000002 --dynamic --allow-incomplete --temporal-output-mode omit
& $PY -m dsl_mngr graph export $WS --snapshot-id DSL_000002 --dynamic --temporal-output-mode separate
```

Schema 1 rifiuta `--allow-incomplete`; le modalita' temporali valgono solo con
`--dynamic`. `strict` fallisce su profili incompatibili, `omit` omette con
warning e `separate` pubblica file distinti.

Il diff cross-schema deve separare almeno la variazione di governance; quando
esistono intervalli confermati include anche la categoria temporale. L'export
deve produrre `.gexf` e `.graph_report.json` sotto `exports/graph/` e superare
validazione XSD GEXF 1.3 e validazione semantica.

## 7. Criteri finali

Confrontare il risultato con `checklist_risultati_attesi.md` e
`matrice_fixture_attesi.md`. Due workspace puliti con gli stessi byte e le
stesse review devono produrre gli stessi hash semantici per normalized,
manifest/fragments, candidate payload, DSL e GEXF; run ID e timestamp audit non
fanno parte del confronto.

Per i contratti completi consultare il
[manuale utente](../../../../documenti/manuali/manuale_utente_dsl_manager.md).
