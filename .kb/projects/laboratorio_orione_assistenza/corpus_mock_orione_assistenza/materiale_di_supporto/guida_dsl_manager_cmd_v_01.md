# Guida DSL Manager in CMD - Orione Assistenza v 01

Questa guida copre lo stesso laboratorio della guida PowerShell usando il
prompt classico di Windows. I blocchi con `%%A` sono frammenti da salvare in un
file `.cmd`; al prompt interattivo si usa un solo `%A`. CMD prepara file
temporanei e raccoglie output, ma tutte le operazioni applicative passano da
`"%PROJECT_PYTHON%" -m dsl_mngr`. Non usare SQL, SQLite o import interni per
sostituire un comando DSL Manager.

## 1. Modello, sicurezza ed exit code

Lo scan registra revisioni; parse e derive producono evidenze e candidati; la
review umana governa; il merge materializza; render ed export fotografano lo
stato. Un import AI resta `pending`. L'intervallo della fonte non rende
automaticamente temporale un fatto o una relazione.

La shell puo' creare la sessione, copiare byte per byte, confrontare file,
estrarre ID dall'output, leggere artefatti e verificare HTTP. Configurazione
review, propagazione temporale e diagnostica partial passano dai leaf pubblici
di DSL Manager. Exit code: `0` successo; `2` uso/fallimento ordinario; `3`
input semantico rifiutato; `4` conflitto/precondizione; `6` partial controllato.

## 2. Interprete e sessione nuova

Scopo: usare Python 3.12 configurato e lavorare fuori dal repository.
Prerequisito: aprire CMD nella root del progetto, dove sono presenti
`AGENTS.md`, `pyproject.toml` e `.codex\config.toml`.

Salvare ed eseguire questo avvio come `avvia_orione.cmd` nel temporaneo, oppure
adattare `%%` a `%` per l'uso riga per riga:

```bat
@echo off
setlocal EnableExtensions EnableDelayedExpansion
for %%A in ("%CD%") do set "REPO=%%~fA"
if not exist "%REPO%\AGENTS.md" exit /b 2
if not exist "%REPO%\pyproject.toml" exit /b 2
if not exist "%REPO%\.codex\config.toml" exit /b 2
for /f "tokens=2 delims==" %%A in ('findstr /r /c:"^[ ]*PROJECT_PYTHON[ ]*=" "%REPO%\.codex\config.toml"') do set "PYREL=%%A"
set "PYREL=!PYREL:~1!"
set "PYREL=!PYREL:"=!"
for %%A in ("%REPO%\!PYREL!") do set "PROJECT_PYTHON=%%~fA"
"!PROJECT_PYTHON!" --version
if errorlevel 1 exit /b 2

set "LAB=%REPO%\.kb\projects\laboratorio_orione_assistenza\corpus_mock_orione_assistenza"
set "SESSION_ROOT=%TEMP%\orione_assistenza_%RANDOM%_%RANDOM%"
if exist "!SESSION_ROOT!" exit /b 4
set "WORKSPACE=!SESSION_ROOT!\workspace"
set "SOURCE_COPY=!SESSION_ROOT!\input_active"
mkdir "!SOURCE_COPY!"
xcopy "%LAB%\corpus\active\*" "!SOURCE_COPY!\" /E /I /H /K /Q
if errorlevel 1 exit /b 2
```

Atteso: `Python 3.12.x` e directory univoca. Se l'interprete manca, correggere
`.codex/config.toml`; non usare il Python globale. Se la directory esiste,
scegliere un nome nuovo o riprendere consapevolmente la sessione, mai
cancellarla o sovrascriverla.

## 3. Init, DB e checksum byte-identici

Scopo: creare il workspace supportato e copiarvi solo le 15 fonti attive.

```bat
"!PROJECT_PYTHON!" -m dsl_mngr init "!WORKSPACE!"
if errorlevel 1 exit /b 2
"!PROJECT_PYTHON!" -m dsl_mngr db init "!WORKSPACE!"
if errorlevel 1 exit /b 2
xcopy "!SOURCE_COPY!\*" "!WORKSPACE!\corpus\active\" /E /I /H /K /Q
if errorlevel 1 exit /b 2

for /r "!SOURCE_COPY!" %%A in (*) do (
  set "REL=%%~fA"
  set "REL=!REL:%SOURCE_COPY%\=!"
  fc /b "%%~fA" "!WORKSPACE!\corpus\active\!REL!" >nul
  if errorlevel 1 (
    echo Checksum o bytes discordanti: !REL!
    exit /b 2
  )
)
```

`init` e `db init` devono terminare `0`; al primo avvio si osservano 12
migrazioni. `fc /b` dimostra l'identita' prima dello scan; `checksums.json`
fornisce poi gli SHA-256 canonici. Quoting e delayed expansion sono
obbligatori con path contenenti spazi. Non usare nomi 8.3.

## 4. Allowlist e doppio scan

Scopo: attivare nel solo `configs\project.yaml` del workspace le regole
conservative per DDL table/column/FK risolta, form/operazioni XML, code unit e
dipendenze PL/SQL, eventi log nominati e oggetti strutturali Excel. View non
supportate, relazioni narrative, SLA e temporalita' non sono auto-review.

```bat
"!PROJECT_PYTHON!" -m dsl_mngr config review show "!WORKSPACE!"
"!PROJECT_PYTHON!" -m dsl_mngr config review profiles "!WORKSPACE!"
"!PROJECT_PYTHON!" -m dsl_mngr config review apply-profile "!WORKSPACE!" --profile conservative/1
if errorlevel 1 exit /b 2
"!PROJECT_PYTHON!" -m dsl_mngr config validate "!WORKSPACE!" --profile conservative/1
if errorlevel 1 exit /b 2
"!PROJECT_PYTHON!" -m dsl_mngr corpus scan "!WORKSPACE!"
if errorlevel 1 exit /b 2
"!PROJECT_PYTHON!" -m dsl_mngr corpus scan "!WORKSPACE!"
if errorlevel 1 exit /b 2
```

Atteso: il profilo built-in `conservative/1` espone e applica 13 policy, la
configurazione e' valida, poi `Added: 15` e `Unchanged: 15`. Non modificare il
YAML a mano. Per aggiornamenti concorrenti usare l'hash restituito da `show`
con `apply-profile --expect-config-hash HASH`. Se compare `Modified`, ricopiare
la fonte canonica, ripetere `fc /b` e usare un workspace nuovo.

## 5. Pipeline, stato e resume

```bat
"!PROJECT_PYTHON!" -m dsl_mngr batch consolidate "!WORKSPACE!" --reconcile >"!SESSION_ROOT!\batch.txt" 2>&1
set "BATCH_EXIT=!ERRORLEVEL!"
type "!SESSION_ROOT!\batch.txt"
for /f "tokens=2" %%A in ('findstr /b /c:"Run:" "!SESSION_ROOT!\batch.txt"') do set "RUN_ID=%%A"
if not defined RUN_ID exit /b 2
"!PROJECT_PYTHON!" -m dsl_mngr run status "!WORKSPACE!" "!RUN_ID!"
```

Atteso v 01: exit `0`, 25 parse su 15 revisioni, 117 candidati, 86
auto-confermati, 31 temporali pending, 78 fatti e 8 relazioni. Conservare
`batch.txt`, `RUN_ID` e `artifacts\runs\!RUN_ID!\batch_report.json`.
Ispezionare `normalized`, `chunks`, `fragments`: tutti i formati richiesti
devono avere artefatti. Il `vbaProject.bin` e' soltanto rilevato/hashato;
l'external link `.invalid` e' inventariato e mai aperto.

Solo se `run status` e il report indicano `retryable`:

```bat
"!PROJECT_PYTHON!" -m dsl_mngr batch consolidate "!WORKSPACE!" --reconcile --resume "!RUN_ID!"
```

Il comando crea una nuova run `retry_of` e puo' ripetere l'intera fase fallita.
Mai cicli infiniti. Per Docling il default verificato e' 300 s e il massimo
duro 600 s: mostrare tempo trascorso, attendere oppure ispezionare i file worker
e fare un solo resume. Un lock Windows transitorio richiede attesa e nuovo
`run status`, non processi terminati alla cieca.

## 6. Selezione AI e package

```bat
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence plan "!WORKSPACE!" --policy technical_extraction >"!SESSION_ROOT!\technical_plan.txt" 2>&1
if errorlevel 1 exit /b 2
type "!SESSION_ROOT!\technical_plan.txt"
for /f "tokens=3" %%A in ('findstr /b /c:"Selection plan:" "!SESSION_ROOT!\technical_plan.txt"') do set "AISEL_TECH=%%A"
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence plan "!WORKSPACE!" --policy domain_interpretation >"!SESSION_ROOT!\domain_plan.txt" 2>&1
if errorlevel 1 exit /b 2
type "!SESSION_ROOT!\domain_plan.txt"
for /f "tokens=3" %%A in ('findstr /b /c:"Selection plan:" "!SESSION_ROOT!\domain_plan.txt"') do set "AISEL_DOMAIN=%%A"
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence list "!WORKSPACE!" --plan "!AISEL_TECH!" --outcome included >"!SESSION_ROOT!\included.txt"
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence list "!WORKSPACE!" --plan "!AISEL_TECH!" --outcome excluded >"!SESSION_ROOT!\excluded.txt"
type "!SESSION_ROOT!\included.txt"
type "!SESSION_ROOT!\excluded.txt"
for /f "tokens=7" %%A in ('findstr /b /c:"included" "!SESSION_ROOT!\included.txt"') do if not defined EVIDENCE_ID set "EVIDENCE_ID=%%A"
for /f "tokens=7" %%A in ('findstr /b /c:"excluded" "!SESSION_ROOT!\excluded.txt"') do if not defined EXCLUDED_ID set "EXCLUDED_ID=%%A"
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence explain "!WORKSPACE!" "!EVIDENCE_ID!" --plan "!AISEL_TECH!"
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence explain "!WORKSPACE!" "!EXCLUDED_ID!" --plan "!AISEL_TECH!"
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence list "!WORKSPACE!" --plan "!AISEL_DOMAIN!" --outcome included >"!SESSION_ROOT!\domain_included.txt"
for /f "tokens=7" %%A in ('findstr /b /c:"included" "!SESSION_ROOT!\domain_included.txt"') do if not defined DOMAIN_EVIDENCE_ID set "DOMAIN_EVIDENCE_ID=%%A"
"!PROJECT_PYTHON!" -m dsl_mngr ai evidence explain "!WORKSPACE!" "!DOMAIN_EVIDENCE_ID!" --plan "!AISEL_DOMAIN!"

"!PROJECT_PYTHON!" -m dsl_mngr ai package "!WORKSPACE!" --selection-plan "!AISEL_DOMAIN!" >"!SESSION_ROOT!\package.txt" 2>&1
set "PACKAGE_EXIT=!ERRORLEVEL!"
type "!SESSION_ROOT!\package.txt"
if not "!PACKAGE_EXIT!"=="0" exit /b !PACKAGE_EXIT!
for /f "tokens=2" %%A in ('findstr /b /c:"Package:" "!SESSION_ROOT!\package.txt"') do set "AIPKG=%%A"
for %%F in (instructions.md candidate_schema.json output_template.jsonl content.md source_manifest.json selection_plan.json package_manifest.json) do (
  echo ===== %%F =====
  type "!WORKSPACE!\ai\outbox\!AIPKG!\%%F"
)
```

Atteso: tecnico 11 incluse/78 escluse; interpretativo 89 incluse; package
`waiting_for_ai_candidates`. Leggere per intero ogni file in
`ai\outbox\!AIPKG!`, inclusi istruzioni, schema, template, contenuto e manifest.
Se lo stato delle evidenze cambia, un piano vecchio deve essere rifiutato con
exit `4 selection_plan_stale`; creare un piano nuovo. Non usare `--allow-stale`
nel laboratorio.

## 7. Handoff e replay controllato

L'AI autentica usa soltanto chunk/frammenti inclusi e restituisce JSONL con
`evidence_text` letterale. Esercitare fact, relation, mapping, conflict,
question e assertion explicit, observed, inferred, ambiguous. Non inventare
`temporal_interval` nello schema AI.

Collocare la risposta in `ai\inbox` senza sovrascrivere file esistenti, poi:

```bat
set /p "AI_RESPONSE=Percorso JSONL della risposta: "
if exist "!WORKSPACE!\ai\inbox\!AIPKG!_candidates.jsonl" exit /b 4
copy /b "!AI_RESPONSE!" "!WORKSPACE!\ai\inbox\!AIPKG!_candidates.jsonl"
if errorlevel 1 exit /b 2
"!PROJECT_PYTHON!" -m dsl_mngr ai inbox scan "!WORKSPACE!"
"!PROJECT_PYTHON!" -m dsl_mngr ai import "!WORKSPACE!" --package "!AIPKG!" >"!SESSION_ROOT!\import.txt" 2>&1
set "IMPORT_EXIT=!ERRORLEVEL!"
type "!SESSION_ROOT!\import.txt"
if not "!IMPORT_EXIT!"=="0" exit /b !IMPORT_EXIT!
```

Per il replay controllato, prima confrontare package hash, evidence ID e testo
con il package corrente; se non coincidono, generare un nuovo handoff. La
chiamata al modello e' simulata, package/inbox/import/review/merge no. Atteso su
sessione canonica: 13 record accettati e ancora pending. Se manca la risposta,
salvare la sessione; se e' invalida, correggerla fuori dal workspace e rifare
inbox scan, mai il database.

## 8. Review, correzione e merge

```bat
"!PROJECT_PYTHON!" -m dsl_mngr candidates review list "!WORKSPACE!" >"!SESSION_ROOT!\pending.json"
type "!SESSION_ROOT!\pending.json"
set /p "CREC=ID CREC realmente mostrato da ispezionare: "
"!PROJECT_PYTHON!" -m dsl_mngr candidates review show "!WORKSPACE!" "!CREC!"
```

Dopo la lettura, usare una sola azione:

```bat
"!PROJECT_PYTHON!" -m dsl_mngr candidates review confirm "!WORKSPACE!" "!CREC!" --reason "Evidenza letterale verificata" --actor-id human_orione --idempotency-key "orione-confirm-!CREC!-v1"
"!PROJECT_PYTHON!" -m dsl_mngr candidates review reject "!WORKSPACE!" "!CREC!" --reason "Regola storica superata" --actor-id human_orione --idempotency-key "orione-reject-!CREC!-v1"
```

Per `correct`, partire dal payload di `show`, attenuare l'asserto SLA troppo
forte, salvare JSON UTF-8 nel temporaneo e passare `--payload` e gli
`--evidence-ref` reali. Parent atteso `superseded`, replacement `confirmed`.
La stessa idempotency key deve fare replay.

```bat
set /p "CORRECTION_FILE=JSON minificato UTF-8 del payload corretto: "
set "CORRECTED_PAYLOAD="
for /f "usebackq delims=" %%A in ("!CORRECTION_FILE!") do if not defined CORRECTED_PAYLOAD set "CORRECTED_PAYLOAD=%%A"
set /p "EVIDENCE_REF=Evidence ID reale: "
"!PROJECT_PYTHON!" -m dsl_mngr candidates review correct "!WORKSPACE!" "!CREC!" --reason "Asserto limitato al target P1" --payload "!CORRECTED_PAYLOAD!" --evidence-ref "!EVIDENCE_REF!" --actor-id human_orione --idempotency-key "orione-correct-!CREC!-v1"
```

Confermare i due supporti checklist, rifiutare l'autoassegnazione obsoleta,
lasciare pending il contratto esterno ambiguo e mantenere l'orphan intenzionale.
Recuperare ogni `CBATCH_*` dall'import/correzione, senza numeri fissi:

```bat
set "MERGE_ARGS="
for %%A in (!CANDIDATE_BATCHES!) do set "MERGE_ARGS=!MERGE_ARGS! --batch %%A"
"!PROJECT_PYTHON!" -m dsl_mngr facts merge-batch "!WORKSPACE!" !MERGE_ARGS!
"!PROJECT_PYTHON!" -m dsl_mngr facts reconcile "!WORKSPACE!"
```

Gli skip di mapping/conflict/question sono attesi. Il fatto checklist deve
avere due supporti senza duplicazione. Se non esistono pending, verificare
package e import invece di presumere ID.

## 9. Temporalita' candidate-first

Con `review list/show`, confermare gli `effective_from` espliciti e concordanti
2026-03-01; rifiutare `first_seen_at`, date da nome file, mtime/ctime e metadata
OOXML incoerenti; lasciare pending i conflitti. Correggere le due date HTML in
un intervallo chiuso di `source_revision` 2023-01-01/2025-02-28. La correzione
e la conferma usano i normali comandi review.

Acquisire dagli output reali `REV_ID`, due `FACT_ID` e `REL_ID`, poi:

```bat
"!PROJECT_PYTHON!" -m dsl_mngr temporal propagate "!WORKSPACE!" --source-revision-id "!REV_ID!" --target-subject-type fact --target-subject-id "!FACT_ID!" --source-subject "source_revision:!REV_ID!" --policy explicit_copy >"!SESSION_ROOT!\promotion.json"
set "PROMOTION_EXIT=!ERRORLEVEL!"
type "!SESSION_ROOT!\promotion.json"
if not "!PROMOTION_EXIT!"=="0" exit /b !PROMOTION_EXIT!
```

L'interfaccia stabile e':

```text
dsl-manager temporal propagate WORKSPACE --source-revision-id REV_ID --target-subject-type {fact,relation} --target-subject-id TARGET_ID --source-subject TYPE:ID [--source-subject TYPE:ID ...] --policy {explicit_copy,intersection,aggregation,conflict}
```

Ripetere `explicit_copy` verso due fatti e la relazione; esercitare inoltre una
`aggregation` disgiunta su un bersaglio distinto o una `intersection` di
vincoli indipendenti. Dal JSON leggere `candidate_record_ids`,
`candidate_batch_ids` o `conflict_id`; usare quegli ID in `review show`, poi
confermare/rifiutare e `merge-batch` i batch reali. Un intervallo semanticamente
gia' materializzato viene riusato e puo' ricevere un secondo supporto
confermato: non duplicare l'intervallo e non cambiare target per aggirare il
riuso.

Per spell reali copiare sullo stesso fatto e sulla stessa relazione sia lo
storico chiuso sia il corrente aperto. Gli intervalli dell'arco devono stare
nei bounds di dominio dei nodi; il renderer collega oggi relation a nodi entity
e fact a nodi fact, limitazione documentata validata dal controllo semantico
ufficiale.

## 10. Render, diff e grafi

```bat
"!PROJECT_PYTHON!" -m dsl_mngr dsl render "!WORKSPACE!" --schema-version 1 --output-dir exports/orione_v1 >"!SESSION_ROOT!\dsl_v1.txt" 2>&1
for /f "tokens=2" %%A in ('findstr /b /c:"Snapshot:" "!SESSION_ROOT!\dsl_v1.txt"') do set "DSL_V1=%%A"
"!PROJECT_PYTHON!" -m dsl_mngr dsl render "!WORKSPACE!" --schema-version 2 --output-dir exports/orione_v2_a >"!SESSION_ROOT!\dsl_v2a.txt" 2>&1
for /f "tokens=2" %%A in ('findstr /b /c:"Snapshot:" "!SESSION_ROOT!\dsl_v2a.txt"') do set "DSL_V2A=%%A"
"!PROJECT_PYTHON!" -m dsl_mngr dsl render "!WORKSPACE!" --schema-version 2 --output-dir exports/orione_v2_b >"!SESSION_ROOT!\dsl_v2b.txt" 2>&1
for /f "tokens=2" %%A in ('findstr /b /c:"Snapshot:" "!SESSION_ROOT!\dsl_v2b.txt"') do set "DSL_V2B=%%A"
"!PROJECT_PYTHON!" -m dsl_mngr dsl diff "!WORKSPACE!" --from "!DSL_V1!" --to "!DSL_V2A!" --cross-schema
"!PROJECT_PYTHON!" -m dsl_mngr graph export "!WORKSPACE!" --snapshot-id "!DSL_V1!"
"!PROJECT_PYTHON!" -m dsl_mngr graph export "!WORKSPACE!" --snapshot-id "!DSL_V1!" --strict-orphans
set "STRICT_EXIT=!ERRORLEVEL!"
"!PROJECT_PYTHON!" -m dsl_mngr graph export "!WORKSPACE!" --snapshot-id "!DSL_V2A!" --dynamic --timeformat date --temporal-output-mode strict
```

Atteso: `intervals` v2 non vuote; due render v2 byte-identici in JSON/YAML/MD;
diff cross-schema `0`; statico `0` con un orphan; strict orphan `2` previsto;
dinamico `0` e validato XSD/semanticamente. Nel GEXF devono esistere almeno
due `<spell>` sul nodo fact e due sull'arco relation: storico chiuso e corrente
aperto. Un file esistente con zero spell non soddisfa il laboratorio.

## 11. Log, UI e chiusura

```bat
"!PROJECT_PYTHON!" -m dsl_mngr log table "!WORKSPACE!" --format html --output "!WORKSPACE!\exports\events.html"
"!PROJECT_PYTHON!" -m dsl_mngr log csv "!WORKSPACE!" --output "!WORKSPACE!\exports\events.csv"
```

Per la UI scegliere una porta loopback libera. In un secondo CMD verificare
prima `netstat -ano | findstr /r /c:":8765 .*LISTENING"`: se produce righe,
scegliere un'altra porta. Nel primo CMD avviare in primo piano:

```bat
"!PROJECT_PYTHON!" -m dsl_mngr ui serve "!WORKSPACE!" --host 127.0.0.1 --port 8765
```

Nel secondo CMD eseguire le richieste; `curl.exe` stampa solo lo status:

```bat
for %%R in (/ /runs /runs/!RUN_ID! /logs /rejected-candidates /conflicts /snapshots /diff) do curl.exe -s -o nul -w "GET %%R = %%{http_code}\n" "http://127.0.0.1:8765%%R"
curl.exe -s -o nul -w "POST / = %%{http_code}\n" -X POST "http://127.0.0.1:8765/"
```

Atteso: otto 200 e POST 405. Tornare al primo CMD e premere `Ctrl+C`: poiche'
il server e' in primo piano, viene arrestato soltanto il processo avviato da
quel comando. Non usare `taskkill` per nome e non chiudere servizi estranei.

Ripetere `corpus scan`: 15 `Unchanged`; ripetere `fc /b` e confrontare gli
SHA-256 con `checksums.json`. Conservare sessione, report e log; non copiare nel
repository database ed export.

Provare il malformed soltanto in un secondo workspace: sono attesi pipeline
`2`, worker `3` e `ooxml_security_violation`. Per il contratto partial usare una
revisione registrata `.txt`, `.md`, `.html` o `.xlsx` senza contenuto attivo:

```bat
"!PROJECT_PYTHON!" -m dsl_mngr diagnostics normalization run "!WORKSPACE!" --revision "!REV_ID!" --scenario controlled_partial_success/1 >"!SESSION_ROOT!\diagnostic_partial.json"
set "DIAGNOSTIC_EXIT=!ERRORLEVEL!"
type "!SESSION_ROOT!\diagnostic_partial.json"
if not "!DIAGNOSTIC_EXIT!"=="6" exit /b !DIAGNOSTIC_EXIT!
```

Il JSON deve dichiarare `controlled_simulation: true`, stato `partial`, exit
worker/CLI `6` e artefatti sotto
`artifacts/runs/<RUN_ID>/diagnostics/normalization/`; non deve modificare
normalizzati, chunk, candidati, fatti o relazioni di produzione. Le fixture
controllate non sono fonti operative.
