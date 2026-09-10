# Guida completa allo scenario Aurora con DSL Manager — Prompt dei comandi (CMD) — versione 02

Questa guida accompagna una persona che non ha mai usato DSL Manager dalla
preparazione dell'ambiente fino alla produzione e alla verifica di snapshot DSL
e grafi GEXF. I comandi sono pensati per `cmd.exe` su Windows, aperto nella root
del repository `dsl_manager-v1`.

La guida riguarda il corpus dimostrativo Aurora Prestiti. Non è una procedura
generica per approvare automaticamente dati di produzione.

## 1. Risultato finale e modello mentale

DSL Manager non trasforma direttamente un documento in una verità di dominio.
Il flusso è governato:

```text
file del corpus
  -> sorgente e revisione identificata da hash
  -> testo normalizzato o frammenti strutturali
  -> derivazione deterministica oppure package AI opzionale
  -> candidati pending, anche quando provengono da AI
  -> decisione automatica autorizzata oppure review umana
  -> merge di fatti e relazioni confermati
  -> snapshot DSL
  -> diff e grafi GEXF
```

Al termine saprai:

- creare un workspace separato dal corpus originale;
- verificare che i byte copiati siano quelli attesi;
- configurare consapevolmente le policy automatiche previste dallo scenario;
- eseguire una sola elaborazione completa e riprenderla senza duplicazioni;
- distinguere testo Docling, manifest Excel, frammenti e fatti approvati;
- creare e ispezionare un package AI, importare una risposta controllata e
  mantenerla dentro lo stesso confine di review degli altri candidati;
- leggere gli ID prodotti dal programma senza riutilizzare i segnaposto;
- revisionare soltanto i candidati che richiedono davvero giudizio umano;
- eseguire merge, reconcile, render DSL, diff ed export GEXF;
- diagnosticare gli esiti più comuni senza cancellare dati alla cieca.

## 2. Come leggere i blocchi CMD

I comandi sono mostrati per una sessione interattiva di `cmd.exe`.

- Le variabili si leggono con `%NOME%`.
- `set "NOME=valore"` evita spazi indesiderati alla fine del valore.
- Il carattere `^` continua un comando sulla riga successiva. Non lasciare spazi
  dopo `^`.
- Nei comandi `for` interattivi si usa `%F`; dentro un file `.bat` devi scrivere
  `%%F`.
- `%ERRORLEVEL%` va letto subito dopo il comando che vuoi controllare.
- Questa guida usa occasionalmente `powershell -NoProfile` soltanto come parser
  JSON, perché CMD non possiede un parser JSON nativo.

## 3. Vocabolario minimo

| Termine | Significato |
|---|---|
| repository | directory del codice `dsl_manager-v1` |
| corpus | insieme dei file originali da analizzare |
| workspace | directory operativa separata contenente configurazione, database e artefatti |
| source | identità logica di un file, per esempio `SRC_000006` |
| revision | versione immutabile dei byte di una source, per esempio `REV_000006` |
| fragment o chunk | evidenza localizzabile estratta da una revisione |
| candidate | proposta prodotta da una regola; non è ancora approvata |
| `candidate_id` | identità semantica deterministica della proposta |
| `candidate_record_id` | record persistito da revisionare, con forma `CREC_...` |
| candidate batch | gruppo di candidati, con forma `CBATCH_...` |
| AI package | cartella di handoff in `ai\outbox\AIPKG_...` contenente evidenze e contratti per uno strumento esterno |
| AI inbox | directory `ai\inbox` dalla quale DSL Manager importa il JSONL restituito |
| stale | package non più allineato alla revisione corrente di almeno una fonte |
| review | decisione `confirmed`, `rejected` o `superseded` |
| pending | candidato privo di una decisione corrente; non è mergeabile |
| merge | materializzazione dei candidati confermati in fatti o relazioni |
| reconcile | riallineamento dopo una correzione di evidenza già materializzata |
| snapshot DSL | fotografia immutabile del registro consolidato, con ID `DSL_...` |
| run | esecuzione auditabile, con ID `RUN_...` |

Gli ID presenti negli esempi sono segnaposto. Devi sempre usare gli ID stampati
dal tuo workspace.

## 4. Sicurezza e confini dello scenario

Lo scenario è locale e usa dati fittizi:

- non chiama automaticamente servizi AI; nel percorso controllato la risposta
  esterna è simulata da una fixture deterministica;
- non richiede accesso alla rete durante l'elaborazione;
- non dereferenzia gli external link Excel;
- non esegue macro VBA;
- non ricalcola formule Excel;
- non usa i timestamp del filesystem come verità temporale;
- non considera automaticamente autorevoli nomi file, metadata, testo Docling o
  formule.

Il file `.xlsm` viene letto direttamente. Non viene convertito in `.xlsx`. Il
VBA viene soltanto rilevato e sottoposto a hash.

DSL Manager prepara il materiale per un eventuale modello esterno, ma non lo
invia. Usare una AI reale sarebbe un'operazione separata, soggetta alle regole
aziendali su rete, riservatezza, logging e costi.

Non riutilizzare un workspace già popolato per seguire questa guida dall'inizio.
Una nuova esecuzione completa sullo stesso workspace può creare nuovi record e
batch per candidati semanticamente uguali. Se possiedi già un workspace, dagli
un nome diverso e conservalo come audit storico.

## 5. Prerequisiti

Servono:

- Windows con il Prompt dei comandi;
- repository aperto nella sua directory root;
- Python 3.12 nell'ambiente virtuale `.venv`;
- corpus Aurora già presente nella knowledge base del repository;
- spazio sufficiente per modelli e artefatti Docling;
- file Excel chiusi durante i controlli degli hash, per evitare lock di lettura.

Controlla la directory corrente:

```bat
if not exist "pyproject.toml" echo ERRORE: aprire cmd.exe nella root di dsl_manager-v1
if not exist ".codex\config.toml" echo ERRORE: manca .codex\config.toml
```

Se compare un errore, cambia directory prima di continuare.

In questo progetto l'unico interprete locale ammesso è quello dichiarato come
`PROJECT_PYTHON` in `.codex\config.toml`. La configurazione corrente punta a
`.venv\Scripts\python.exe`.

## 6. Impostare i percorsi

```bat
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
set "AURORA=%ROOT%\.kb\projects\corpus aurora\corpus_mock_aurora_prestiti"
set "SOURCE=%AURORA%\corpus\active"
set "SUPPORT=%AURORA%\materiale_di_supporto"
set "WS=%ROOT%\.workspaces\laboratorio_aurora_v_02_cmd"
```

Visualizzali:

```bat
echo Repository: %ROOT%
echo Python: %PY%
echo Corpus: %SOURCE%
echo Supporto: %SUPPORT%
echo Workspace: %WS%
```

Questa guida richiede un workspace nuovo:

```bat
if exist "%WS%" echo ERRORE: il workspace esiste gia'. Scegliere un nuovo nome e non cancellarlo automaticamente.
```

Se il workspace esiste, fermati e modifica la variabile `WS`, per esempio
aggiungendo una data o un numero.

Verifica Python e installa il progetto in modalità editable:

```bat
"%PY%" --version
"%PY%" -m pip install -e ".[dev]"
"%PY%" -m dsl_mngr --version
"%PY%" -m dsl_mngr --help
```

La versione Python deve appartenere alla serie 3.12. Non usare il Python
globale e non impostare `PYTHONPATH`.

## 7. Creare workspace e database

```bat
"%PY%" -m dsl_mngr init "%WS%"
if errorlevel 1 echo ERRORE: inizializzazione workspace fallita

"%PY%" -m dsl_mngr db init "%WS%"
if errorlevel 1 echo ERRORE: inizializzazione database fallita
```

`init` crea directory e configurazioni. `db init` crea `workspace.sqlite` e
applica le migrazioni. Non modificare direttamente il database.

Controlla i file principali:

```bat
dir "%WS%\configs\project.yaml"
dir "%WS%\workspace.sqlite"
dir "%WS%\corpus\active"
```

## 8. Configurare le review automatiche prima del batch

### 8.1 Perché questo passaggio è indispensabile

Un workspace nuovo contiene per scelta prudenziale:

```yaml
review:
  default_actor_id:
  automatic_policies: []
```

Con la lista vuota ogni candidato resta pending. Non è un errore del programma,
ma nello scenario Aurora produrrebbe una coda molto grande da revisionare a
mano. Il test Aurora autorizza esplicitamente tutte le policy che i contratti
delle regole dichiarano auto-reviewable. Le relazioni Excel esplicite e i
candidati temporali restano invece fuori dall'automazione.

Questa allowlist è adatta alle fixture controllate Aurora. In un progetto reale
deve essere approvata dai responsabili del dominio e della governance.

### 8.2 Allowlist usata dallo scenario Aurora

Apri la configurazione:

```bat
notepad "%WS%\configs\project.yaml"
```

Sostituisci soltanto `automatic_policies: []` con il blocco seguente, mantenendo
esattamente l'indentazione YAML:

```yaml
  automatic_policies:
    - explicit_db_code_unit_only/1
    - explicit_ddl_column_only/1
    - explicit_ddl_table_only/1
    - explicit_excel_named_range_only/1
    - explicit_excel_region_only/1
    - explicit_excel_sheet_only/1
    - explicit_excel_table_only/1
    - explicit_excel_workbook_only/1
    - explicit_resolved_ddl_fk_only/1
    - explicit_xml_form_structure_only/1
    - explicit_xml_operation_only/1
    - named_explicit_log_policy_required/1
    - observed_db_code_dependency_only/1
```

Non aggiungere `explicit_excel_reference_pending/1`: la regola
`excel_explicit_reference/1` non consente review automatica. Non esiste una
policy generale per promuovere automaticamente le date estratte.

Controlla il file salvato:

```bat
type "%WS%\configs\project.yaml"
```

I nomi e le versioni delle policy devono coincidere esattamente. Una versione
inesistente, per esempio `/999`, non viene applicata.

## 9. Copiare esclusivamente le 18 fonti operative

Le directory `fixture_controllate` e gli altri file di supporto non devono
entrare in `corpus\active`.

```bat
xcopy "%SOURCE%" "%WS%\corpus\active\" /E /I /Y
```

Conta i file. Questo comando è scritto per il prompt interattivo:

```bat
for /f %N in ('dir /s /b /a-d "%WS%\corpus\active" ^| find /c /v ""') do set "SOURCE_COUNT=%N"
echo File operativi copiati: %SOURCE_COUNT%
```

Il valore deve essere `18`. In un file `.bat` devi scrivere `%%N` invece di
`%N`.

Visualizza l'inventario copiato:

```bat
dir /s /b /a-d "%WS%\corpus\active"
```

## 10. Verificare i checksum originali e delle copie

### 10.1 Verifica canonica dei file originali

Il test checksum legge `checksums.json` e controlla le 18 fonti e le tre fixture
controllate:

```bat
"%PY%" -m pytest -q tests\test_slice_28_aurora_e2e.py -k checksum
```

Il test usa i file originali nella knowledge base; non verifica da solo la copia
nel workspace.

### 10.2 Verifica completa delle copie

CMD non ha un parser JSON nativo. Il comando seguente usa PowerShell soltanto
per leggere il manifest e confrontare gli SHA-256 delle 18 copie:

```bat
powershell -NoProfile -Command "function Get-Sha256([string]$Path){$sha=[Security.Cryptography.SHA256]::Create(); try{$bytes=[IO.File]::ReadAllBytes($Path); return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()} finally{$sha.Dispose()}}; $m=Get-Content -Raw -LiteralPath (Join-Path $env:SUPPORT 'checksums.json')|ConvertFrom-Json; foreach($p in $m.files.PSObject.Properties){$r=$p.Name; if($r.StartsWith('corpus/active/')){$a=Get-Sha256 (Join-Path $env:WS $r); if($a -ne $p.Value.sha256){throw ('Checksum copia non valido: '+$r)}}}; 'Checksum copie operative: OK'"
```

Controlli puntuali leggibili anche con `certutil`:

```bat
certutil -hashfile "%WS%\corpus\active\documenti\nuovi_utili\matrice_stati_2025.xlsx" SHA256
certutil -hashfile "%WS%\corpus\active\documenti\nuovi_utili\calcolo_rate_macro_2025.xlsm" SHA256
```

Hash attesi:

```text
matrice_stati_2025.xlsx
8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081

calcolo_rate_macro_2025.xlsm
17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4
```

Se un hash non coincide, fermati. Non eseguire lo scan su byte diversi e non
correggere il manifest degli hash per adattarlo a una copia inattesa.

## 11. Registrare il corpus con due scan

Il primo scan registra le sorgenti. Il secondo dimostra che ripetere lo scan
sugli stessi byte è idempotente.

```bat
"%PY%" -m dsl_mngr corpus scan "%WS%"
if errorlevel 1 echo ERRORE: primo scan fallito

"%PY%" -m dsl_mngr corpus scan "%WS%"
if errorlevel 1 echo ERRORE: secondo scan fallito
```

Attese:

- primo scan: 18 sorgenti aggiunte;
- secondo scan: 18 sorgenti `Unchanged`;
- nessuna nuova revisione al secondo scan.

Una modifica reale dei byte crea una nuova `REV_...`; non sovrascrive la
revisione precedente.

## 12. Eseguire il batch consolidato una sola volta

### 12.1 Che cosa fa

`batch consolidate` orchestra cinque fasi:

```text
parse -> derive -> review -> merge -> reconcile
```

- `parse` normalizza documenti e workbook e crea frammenti strutturati;
- `derive` applica regole deterministiche e crea candidate batch;
- `review` applica soltanto le policy presenti nell'allowlist;
- `merge` materializza i candidati confermati e salta i pending in modalità non
  strict;
- `reconcile` viene eseguito soltanto se richiesto e se il merge lo consente.

### 12.2 Avvio e salvataggio dell'output

La normalizzazione Docling può durare diversi minuti. Non chiudere la console e
non lanciare un secondo batch mentre il primo è attivo.

```bat
set "BATCH_OUTPUT=%WS%\batch_consolidate_output.json"
"%PY%" -m dsl_mngr batch consolidate "%WS%" > "%BATCH_OUTPUT%"
set "BATCH_EXIT=%ERRORLEVEL%"
type "%BATCH_OUTPUT%"
echo Exit code: %BATCH_EXIT%
```

Il comando salva inoltre gli artefatti canonici sotto:

```text
<workspace>\artifacts\runs\<RUN_ID>\
```

Fra questi trovi normalmente `batch_report.json`, `batch_checkpoint.json`,
`input.json`, `output.json`, `process_report.json`, configurazione risolta e log.
`batch_consolidate_output.json` è soltanto una copia comoda dell'output terminale.

Per stampare i campi principali del JSON:

```bat
powershell -NoProfile -Command "$b=Get-Content -Raw -LiteralPath $env:BATCH_OUTPUT|ConvertFrom-Json;$b|Select-Object run_id,status,reason,exit_code,retryable|Format-List;$b.counters|Format-List;$b.phases|Select-Object name,status,attempts|Format-Table"
```

### 12.3 Interpretare l'esito

Con le policy Aurora configurate correttamente ci si aspetta:

- almeno un candidato auto-confermato;
- candidati sensibili ancora pending;
- fatti e relazioni confermati materializzati;
- pending saltati in modo dichiarato dal merge non strict.

Controlla in particolare:

```text
auto_confirmed
review_pending
merged_candidates
skipped_pending
facts_created / facts_existing
relations_created / relations_existing
```

Exit code `0` indica completamento. Exit code `4` con reason
`no_merge_eligible_candidates` è tipico quando nessuna policy è stata applicata
e nessun candidato è stato confermato. Non significa che i candidati siano
persi.

### 12.4 Riprendere, non rilanciare

Leggi `run_id` dentro `%BATCH_OUTPUT%` e assegnalo:

```bat
set "FAILED_RUN=RUN_000001"
```

Sostituisci il segnaposto. Dopo aver corretto la causa:

```bat
"%PY%" -m dsl_mngr batch consolidate "%WS%" --resume %FAILED_RUN%
```

`--resume` riusa i checkpoint completati e ricalcola solo le fasi necessarie.
Le policy correnti vengono rilette. Non usare un nuovo
`batch consolidate "%WS%"` per sbloccare la stessa elaborazione: una nuova run
completa può creare nuovi `CBATCH_...` e `CREC_...` per gli stessi
`candidate_id`.

Per controllare una run:

```bat
"%PY%" -m dsl_mngr run status "%WS%" %FAILED_RUN%
```

## 13. Trovare gli ID di sorgente e revisione

In un workspace Aurora nuovo, con soltanto le 18 fonti previste, gli ID attesi
sono:

```bat
set "MATRIX_DIR=%WS%\normalized\SRC_000006\REV_000006"
set "MACRO_DIR=%WS%\normalized\SRC_000003\REV_000003"
```

Non fidarti soltanto dei numeri: verifica l'identità tramite `input_path`:

```bat
findstr /i /c:"matrice_stati_2025.xlsx" "%MATRIX_DIR%\docling_report.json"
findstr /i /c:"calcolo_rate_macro_2025.xlsm" "%MACRO_DIR%\docling_report.json"
```

Se una directory non esiste o non contiene il nome giusto, trova i report. I
comandi seguenti sono per una sessione interattiva; in un `.bat` usa `%%F`:

```bat
for /r "%WS%\normalized" %F in (docling_report.json) do @findstr /i /m /c:"matrice_stati_2025.xlsx" "%F"
for /r "%WS%\normalized" %F in (docling_report.json) do @findstr /i /m /c:"calcolo_rate_macro_2025.xlsm" "%F"
```

Imposta `MATRIX_DIR` e `MACRO_DIR` con le directory stampate. Il campo
`input.input_path` del report è la verifica autorevole dell'associazione.

## 14. Capire gli artefatti di normalizzazione

Per ciascun workbook valido la directory `normalized\<SRC>\<REV>\` contiene:

```text
normalized.json
normalized.md
docling_report.json
ooxml_preflight_report.json
source_hash.txt
workbook_manifest.json
workbook_fragments.jsonl
workbook_report.json
```

Ruoli:

| File | Uso corretto |
|---|---|
| `normalized.json`, `normalized.md` | vista leggibile prodotta da Docling |
| `docling_report.json` | identità input, versione worker, stato e percorsi output |
| `ooxml_preflight_report.json` | esito dei controlli di sicurezza e budget |
| `workbook_manifest.json` | struttura tecnica autorevole osservata nel workbook |
| `workbook_fragments.jsonl` | una riga JSON per regione Excel rilevata |
| `workbook_report.json` | esito, contatori, hash e garanzie operative |

Il manifest è autorevole per la struttura osservata, non per il significato di
dominio. Una formula conservata correttamente dimostra che la formula esiste nel
file; non dimostra che rappresenti una regola aziendale valida.
Il testo Docling e le formule non sono automaticamente verità di dominio.

Per creare copie formattate più facili da leggere:

```bat
powershell -NoProfile -Command "Get-Content -Raw -LiteralPath (Join-Path $env:MATRIX_DIR 'workbook_manifest.json')|ConvertFrom-Json|ConvertTo-Json -Depth 30|Set-Content -Encoding utf8 -LiteralPath (Join-Path $env:WS 'matrice_manifest_pretty.json')"
powershell -NoProfile -Command "Get-Content -Raw -LiteralPath (Join-Path $env:MACRO_DIR 'workbook_report.json')|ConvertFrom-Json|ConvertTo-Json -Depth 20|Set-Content -Encoding utf8 -LiteralPath (Join-Path $env:WS 'macro_report_pretty.json')"
```

Queste copie servono soltanto alla lettura e non sostituiscono gli artefatti
canonici.

## 15. Verificare `matrice_stati_2025.xlsx`

Stampa un riepilogo strutturale usando PowerShell come parser JSON:

```bat
powershell -NoProfile -Command "$m=Get-Content -Raw -LiteralPath (Join-Path $env:MATRIX_DIR 'workbook_manifest.json') | ConvertFrom-Json; $regions=($m.sheets | ForEach-Object {$_.regions.Count} | Measure-Object -Sum).Sum; $types=@($m.sheets.cells.type | Sort-Object -Unique); [pscustomobject]@{Sheets=$m.sheets.Count; Names=($m.sheets.name -join ' | '); Visibility=($m.sheets.visibility -join ' | '); Regions=$regions; Cells=$m.sheets.cells.Count; Merged=($m.sheets.merged_ranges -join ' | '); NamedRanges=($m.named_ranges.name -join ' | '); CellTypes=($types -join ' | '); ExternalDisposition=$m.external_links[0].disposition} | Format-List; $m.sheets.cells | Where-Object {$null -ne $_.formula} | Select-Object coordinate,formula,cached_value,type | Format-Table"
```

Devi osservare:

| Controllo | Valore atteso |
|---|---|
| fogli | 3: `Résumé`, `隐 藏`, `非常` |
| visibilità | `visible`, `hidden`, `very_hidden` |
| regioni | 5, distribuite 2 + 2 + 1 |
| celle | 21 |
| tipi distinti | `string`, `number`, `bool`, `date`, `error`, `blank` |
| formula con cache | `D2`, `B2+C2`, cache `3.5` |
| formula senza cache | `E2`, `B2*C2`, cache `null` |
| formula di errore | `F2`, `1/0`, cache `#DIV/0!` |
| merged range | `A3:B3` |
| named range | `MainBlock`, `LocalPair` |
| external link | `not_dereferenced` |

`very_hidden` è il valore serializzato che corrisponde allo stato Excel
`veryHidden`.

I named range attesi sono:

- `MainBlock` -> `'Résumé'!$A$1:$F$3`, scope workbook;
- `LocalPair` -> `'Résumé'!$H$10:$I$10`, scope foglio `Résumé`.

## 16. Verificare sicurezza e macro di `calcolo_rate_macro_2025.xlsm`

```bat
powershell -NoProfile -Command "$m=Get-Content -Raw -LiteralPath (Join-Path $env:MACRO_DIR 'workbook_manifest.json') | ConvertFrom-Json; $r=Get-Content -Raw -LiteralPath (Join-Path $env:MACRO_DIR 'workbook_report.json') | ConvertFrom-Json; [pscustomobject]@{MacroPresent=$m.macros.present; MacroPart=$m.macros.part_name; MacroHash=$m.macros.content_hash; ManifestExecuted=$m.macros.executed; ReportMacrosExecuted=$r.macros_executed; NetworkAccessed=$r.network_accessed; StructuralSource=$r.structural_source} | Format-List; if(-not $m.macros.present -or $m.macros.part_name -ne 'xl/vbaProject.bin' -or $m.macros.executed -ne $false -or $r.macros_executed -ne $false -or $r.network_accessed -ne $false){throw 'Controllo XLSM fallito'}"
```

La presenza di `xl/vbaProject.bin` dimostra che il file è realmente
macro-enabled. `executed: false` significa che DSL Manager non ha eseguito VBA.
Il report deve dichiarare anche `network_accessed: false` e
`structural_source: workbook_manifest.json`.

## 17. Test controllati: cosa verificano e cosa non verificano

```bat
"%PY%" -m pytest -q tests\test_slice_28_aurora_e2e.py
```

Il test verifica checksum, scenario E2E, malformed, partial, budget, handoff AI
controllato e assenza di rete in workspace temporanei. Non sostituisce il
controllo degli artefatti del tuo `%WS%`.

Le fixture:

- `workbook_malformed_controllato.xlsx` deve essere rifiutata in preflight con
  reason `ooxml_security_violation`;
- `workbook_partial_controllato.xlsx` è un package valido usato per iniettare
  nel test un `partial_success`, con status `partial` ed exit code `6`;
- `ai_response_aurora_controllata.jsonl` simula due record restituiti da una AI
  esterna e permette di provare package, inbox, import, review e merge;
- nessuna delle tre va copiata in `corpus\active`.

## 18. Percorso AI controllato, governato e offline

### 18.1 Che cosa è reale e che cosa è simulato

Questo laboratorio è un ramo aggiuntivo del percorso già eseguito:

```text
frammenti DDL già registrati
  -> package reale creato da DSL Manager
  -> risposta esterna simulata dalla fixture controllata
  -> inbox e import reali
  -> due candidati pending reali
  -> review umana simulata con actor esplicito
  -> merge reale del solo candidato confermato
```

La fixture sostituisce esclusivamente la chiamata a un modello. Non sostituisce
nessuna funzione di DSL Manager. Serve a rendere il test ripetibile, gratuito e
senza rete. In un utilizzo reale devi considerare l'output del modello non
fidato fino a validazione e review.

Il package standard consente `candidate_fact`, `candidate_relation`,
`candidate_mapping`, `candidate_conflict` e `candidate_question`. Non consente
attualmente `temporal_interval`.

### 18.2 Individuare la revisione DDL

Il dump DDL non produce un `docling_report.json`: usa il suo `ddl_report.json`,
creato dal batch nella directory `fragments`. I comandi `for` seguenti sono per
una sessione interattiva; in un file `.bat` devi raddoppiare `%F` e `%I`:

```bat
set "DDL_REPORT="
set /a DDL_MATCH_COUNT=0
for /r "%WS%\fragments" %F in (*ddl_report.json) do @findstr /i /m /c:"corpus/active/database/dump_oracle_ddl.sql" "%F" >nul && (set /a DDL_MATCH_COUNT+=1 >nul & set "DDL_REPORT=%F")
echo Report DDL trovati: %DDL_MATCH_COUNT%
if not "%DDL_MATCH_COUNT%"=="1" echo ERRORE: revisione DDL non individuata in modo univoco. Fermarsi.
if not defined DDL_REPORT echo ERRORE: ddl_report.json non trovato. Fermarsi.
```

Se è comparso un errore, non proseguire. Altrimenti leggi e verifica il report,
poi ricava l'ID senza scriverlo a mano:

```bat
powershell -NoProfile -Command "$r=Get-Content -Raw -LiteralPath $env:DDL_REPORT|ConvertFrom-Json; if($r.input.input_path -ne 'corpus/active/database/dump_oracle_ddl.sql'){throw 'input_path DDL inatteso'}; [pscustomobject]@{InputPath=$r.input.input_path;SourceId=$r.input.source_id;RevisionId=$r.input.source_revision_id;Fragments=$r.fragment_count;Report=$env:DDL_REPORT}|Format-List"
for /f "usebackq delims=" %I in (`powershell -NoProfile -Command "(Get-Content -Raw -LiteralPath $env:DDL_REPORT|ConvertFrom-Json).input.source_revision_id"`) do set "DDL_REV=%I"
echo Revisione DDL: %DDL_REV%
```

Nel workspace pulito di questa guida deve risultare `REV_000001` e il report
deve indicare 38 frammenti. La risposta controllata è deliberatamente ancorata
a `REV_000001`, `FRAG_000001` e `FRAG_000009`. Non adattare quegli ID a intuito:
fra poco controllerai che il package contenga esattamente quelle evidenze. Se
la precondizione non è rispettata, usa un workspace nuovo oppure produci un vero
output AI basato sugli ID presenti nel suo package.

### 18.3 Creare il package

Esegui il comando una volta sola e salva l'output:

```bat
set "AI_PACKAGE_OUTPUT=%WS%\ai_package_output.txt"
"%PY%" -m dsl_mngr ai package "%WS%" --revision %DDL_REV% --profile ai_package.default > "%AI_PACKAGE_OUTPUT%"
set "AI_PACKAGE_EXIT=%ERRORLEVEL%"
type "%AI_PACKAGE_OUTPUT%"
echo Exit code package AI: %AI_PACKAGE_EXIT%
if not "%AI_PACKAGE_EXIT%"=="0" echo ERRORE: creazione AI package fallita. Fermarsi.
```

L'output contiene `Run:`, `Package:`, `Status:`, `Sources:`, `Chunks:`,
`Fragments:`, `Outbox:` e `Manifest:`. Se l'exit code è zero, estrai l'ID
stampato senza presumere che sia `AIPKG_000001`:

```bat
set "AIPKG="
for /f "tokens=2" %I in ('findstr /b /c:"Package:" "%AI_PACKAGE_OUTPUT%"') do set "AIPKG=%I"
if not defined AIPKG echo ERRORE: ID package non trovato. Fermarsi.
set "AI_PACKAGE_DIR=%WS%\ai\outbox\%AIPKG%"
echo Package AI: %AIPKG%
echo Directory: %AI_PACKAGE_DIR%
```

In un file `.bat`, anche qui devi usare `%%I`. Creare un altro package non
aggiorna il precedente: produce un nuovo `AIPKG_...`. Non ripetere il comando
per correggere un output esterno.

### 18.4 Ispezionare e verificare il package

Devono esistere sei file:

```bat
for %F in (candidate_schema.json content.md instructions.md output_template.jsonl package_manifest.json source_manifest.json) do @if not exist "%AI_PACKAGE_DIR%\%F" echo ERRORE: file AI package mancante: %F
dir /b "%AI_PACKAGE_DIR%"
```

In un file `.bat` usa `%%F`. Il controllo seguente fallisce se stato, conteggi,
revisione o frammenti non sono quelli richiesti dalla fixture:

```bat
powershell -NoProfile -Command "$p=Get-Content -Raw -LiteralPath (Join-Path $env:AI_PACKAGE_DIR 'package_manifest.json')|ConvertFrom-Json; $s=Get-Content -Raw -LiteralPath (Join-Path $env:AI_PACKAGE_DIR 'source_manifest.json')|ConvertFrom-Json; $c=Get-Content -Raw -LiteralPath (Join-Path $env:AI_PACKAGE_DIR 'candidate_schema.json')|ConvertFrom-Json; if($p.status -ne 'waiting_for_ai_candidates'){throw ('Stato package inatteso: '+$p.status)}; if($p.stale_check.is_stale -ne $false){throw 'Package stale appena creato'}; if($s.counts.source_revisions -ne 1 -or $s.counts.chunks -ne 0 -or $s.counts.fragments -ne 38){throw 'Conteggi package DDL inattesi'}; if($env:DDL_REV -ne 'REV_000001' -or $s.source_revisions[0].source_revision_id -ne $env:DDL_REV){throw 'La fixture richiede REV_000001 nello stesso package'}; $ids=@($s.fragments.fragment_id); foreach($id in @('FRAG_000001','FRAG_000009')){if($id -notin $ids){throw ('Evidenza assente: '+$id)}}; [pscustomobject]@{Status=$p.status;Stale=$p.stale_check.is_stale;Revisions=$s.counts.source_revisions;Chunks=$s.counts.chunks;Fragments=$s.counts.fragments}|Format-List; 'Record type ammessi:'; $c.allowed_record_types"
if errorlevel 1 echo ERRORE: verifica del package fallita. Fermarsi.
```

Leggi sempre istruzioni e contenuto consegnabile:

```bat
type "%AI_PACKAGE_DIR%\instructions.md"
more < "%AI_PACKAGE_DIR%\content.md"
type "%AI_PACKAGE_DIR%\output_template.jsonl"
```

`output_template.jsonl` mostra la forma dei record, ma contiene segnaposti
intenzionalmente invalidi: non va copiato invariato nell'inbox.

### 18.5 Dove entrerebbe una AI reale

Solo a questo punto, in un processo aziendalmente autorizzato, si potrebbe dare
la cartella del package a uno strumento esterno. Lo strumento deve:

1. trattare il package come sola lettura;
2. usare soltanto le evidenze in `content.md`;
3. rispettare `candidate_schema.json` e `instructions.md`;
4. copiare esattamente revision, chunk o fragment ID;
5. produrre un oggetto JSON completo per riga;
6. non modificare database, registry, snapshot o file del progetto.

DSL Manager non esegue questo invio. Prima di usare un servizio reale devi
valutare riservatezza, autorizzazioni, localizzazione dei dati, logging e costi.
Il laboratorio resta invece interamente offline.

### 18.6 Simulare la risposta esterna con la fixture controllata

La fixture contiene un fatto tecnico esplicito e una domanda ambigua. Copiala
con il nome che DSL Manager associa al package:

```bat
set "AI_FIXTURE=%SUPPORT%\fixture_controllate\ai_response_aurora_controllata.jsonl"
set "AI_CANDIDATE_FILE=%WS%\ai\inbox\%AIPKG%_candidates.jsonl"
if not exist "%AI_FIXTURE%" echo ERRORE: fixture AI controllata mancante. Fermarsi.
copy /y "%AI_FIXTURE%" "%AI_CANDIDATE_FILE%"
powershell -NoProfile -Command "function Get-Sha256([string]$Path){$sha=[Security.Cryptography.SHA256]::Create(); try{$bytes=[IO.File]::ReadAllBytes($Path); return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','')} finally{$sha.Dispose()}}; $a=Get-Sha256 $env:AI_FIXTURE; $b=Get-Sha256 $env:AI_CANDIDATE_FILE; if($a -ne $b){throw 'Checksum copia AI non valido'}; 'Checksum copia AI: OK'"
type "%AI_CANDIDATE_FILE%"
```

Non modificare la fixture canonica. La copia nell'inbox è un output simulato e
non deve mai essere collocata in `corpus\active`.

### 18.7 Scansionare l'inbox e importare

Salva anche l'esito della scansione, perché il comando normalmente stampa
soltanto sul terminale:

```bat
set "AI_INBOX_SCAN_OUTPUT=%WS%\ai_inbox_scan_output.txt"
"%PY%" -m dsl_mngr ai inbox scan "%WS%" > "%AI_INBOX_SCAN_OUTPUT%"
set "AI_INBOX_EXIT=%ERRORLEVEL%"
type "%AI_INBOX_SCAN_OUTPUT%"
echo Exit code scansione inbox: %AI_INBOX_EXIT%
if not "%AI_INBOX_EXIT%"=="0" echo ERRORE: scansione AI inbox fallita. Fermarsi.
```

La riga deve mostrare `%AIPKG%`, il file candidato, `exists`, `not stale` e
reason `-`. Se mostra `stale`, non importare: la revisione corrente non coincide
più con quella consegnata al modello.

Importa una sola volta e conserva l'output:

```bat
set "AI_IMPORT_OUTPUT=%WS%\ai_import_output.txt"
"%PY%" -m dsl_mngr ai import "%WS%" --package %AIPKG% > "%AI_IMPORT_OUTPUT%"
set "AI_IMPORT_EXIT=%ERRORLEVEL%"
type "%AI_IMPORT_OUTPUT%"
echo Exit code import AI: %AI_IMPORT_EXIT%
if not "%AI_IMPORT_EXIT%"=="0" echo ERRORE: import AI fallito. Fermarsi.

set "AI_BATCH="
for /f "tokens=2" %I in ('findstr /b /c:"Batch:" "%AI_IMPORT_OUTPUT%"') do set "AI_BATCH=%I"
if not defined AI_BATCH echo ERRORE: batch AI non trovato. Fermarsi.
echo Batch AI: %AI_BATCH%
```

In un file `.bat` usa `%%I`. L'attesa è `Total: 2`, `Accepted: 2`,
`Rejected: 0` e `Stale allowed: false`. Qui `Accepted` significa soltanto che
schema, revisione, fragment ID ed evidence text sono validi. Non significa
`confirmed`.

`--allow-stale` esiste come eccezione auditabile, ma questo laboratorio non lo
usa. Non applicarlo per far passare un package obsoleto senza una decisione
esplicita di governance.

### 18.8 Verificare e decidere i due candidati AI

L'import crea due candidati pending: non crea fatti e non prende decisioni.
Salva la lista corrente e isola soltanto i due `candidate_id` controllati:

```bat
set "AI_PENDING_FILE=%WS%\ai_pending_candidates.json"
"%PY%" -m dsl_mngr candidates review list "%WS%" --outcome pending > "%AI_PENDING_FILE%"
if errorlevel 1 echo ERRORE: lettura pending dopo import AI fallita. Fermarsi.

set "AI_IDS_FILE=%WS%\ai_candidate_ids.txt"
powershell -NoProfile -Command "$r=Get-Content -Raw -LiteralPath $env:AI_PENDING_FILE|ConvertFrom-Json; $f=@($r.candidates).Where({$_.candidate_id -eq 'CAND_AURORA_AI_DDL_TABLE_001'}); $q=@($r.candidates).Where({$_.candidate_id -eq 'CAND_AURORA_AI_DDL_QUESTION_001'}); if($f.Count -ne 1 -or $q.Count -ne 1){throw ('Attesi due candidati AI univoci; fatto='+$f.Count+' domanda='+$q.Count)}; @(('AI_FACT_CREC='+$f[0].candidate_record_id),('AI_QUESTION_CREC='+$q[0].candidate_record_id))|Set-Content -Encoding ascii -LiteralPath $env:AI_IDS_FILE; @($f[0],$q[0])|Select-Object candidate_record_id,batch_id,candidate_id,record_type,outcome|Format-Table -AutoSize"
if errorlevel 1 echo ERRORE: candidati AI non individuati in modo univoco. Fermarsi.
type "%AI_IDS_FILE%"
for /f "usebackq tokens=1,* delims==" %I in ("%AI_IDS_FILE%") do set "%I=%J"
echo Candidate record fatto: %AI_FACT_CREC%
echo Candidate record domanda: %AI_QUESTION_CREC%
```

In un file `.bat` l'ultimo `for` usa `%%I` e `%%J`. Usa i `CREC_...` appena
trovati, non quelli di un altro workspace:

```bat
"%PY%" -m dsl_mngr candidates review show "%WS%" %AI_FACT_CREC%
"%PY%" -m dsl_mngr candidates review show "%WS%" %AI_QUESTION_CREC%
```

Entrambi devono essere pending. Nel laboratorio si conferma il fatto tecnico,
che coincide con la struttura DDL, e si rifiuta la domanda perché il vincolo
tecnico non basta a dimostrare una regola di dominio:

```bat
"%PY%" -m dsl_mngr candidates review confirm "%WS%" %AI_FACT_CREC% ^
  --actor-id aurora-ai-reviewer ^
  --reason "Fatto tecnico verificato sul frammento DDL"
if errorlevel 1 echo ERRORE: conferma del candidato AI fallita. Fermarsi.

"%PY%" -m dsl_mngr candidates review reject "%WS%" %AI_QUESTION_CREC% ^
  --actor-id aurora-ai-reviewer ^
  --reason "La fonte tecnica non dimostra una regola di dominio"
if errorlevel 1 echo ERRORE: rifiuto della domanda AI fallito. Fermarsi.
```

Infine esegui il merge del solo batch stampato da `ai import` e conserva il
report:

```bat
set "AI_MERGE_OUTPUT=%WS%\ai_merge_output.txt"
"%PY%" -m dsl_mngr facts merge "%WS%" --batch %AI_BATCH% > "%AI_MERGE_OUTPUT%"
set "AI_MERGE_EXIT=%ERRORLEVEL%"
type "%AI_MERGE_OUTPUT%"
echo Exit code merge AI: %AI_MERGE_EXIT%
```

La domanda rifiutata viene conteggiata in `Skipped rejected`. Il fatto può
risultare in `Facts created` in uno scenario AI isolato oppure in
`Facts existing` se il precedente percorso deterministico aveva già
materializzato lo stesso fatto. In entrambi i casi l'evidenza AI confermata è
governata e non nasce alcun fatto dalla domanda.

Per più revisioni puoi ripetere `--revision` con `ai package`, oppure usare
`ai package-batch`, che crea un package distinto per ogni revisione. Non farlo
nel laboratorio controllato: la fixture presente riguarda soltanto il DDL.

## 19. Capire e salvare la lista dei candidati

### 19.1 Il comando non crea un file

```bat
"%PY%" -m dsl_mngr candidates review list "%WS%" --outcome pending
```

Il comando legge il database e stampa JSON sul terminale. Non crea una run e
non pubblica un artefatto: il payload contiene `artifact_paths: []`,
`run_id: null` e `mutations: false`. I candidati restano comunque persistiti in
`workspace.sqlite`.

Per salvare una fotografia:

```bat
set "PENDING_FILE=%WS%\pending_candidates.json"
"%PY%" -m dsl_mngr candidates review list "%WS%" --outcome pending > "%PENDING_FILE%"
set "LIST_EXIT=%ERRORLEVEL%"
echo Exit code lista: %LIST_EXIT%
```

Mostra una tabella leggibile:

```bat
powershell -NoProfile -Command "$r=Get-Content -Raw -LiteralPath $env:PENDING_FILE|ConvertFrom-Json;'Pending: '+$r.count;$r.candidates|Select-Object candidate_record_id,batch_id,candidate_id,record_type,assertion_type,confidence|Format-Table -AutoSize"
```

### 19.2 Cosa significano i tre ID

Per una riga della lista:

- usa `candidate_record_id`, per esempio `CREC_...`, con `review show`,
  `confirm`, `reject` o `correct`;
- usa `batch_id`, per esempio `CBATCH_...`, con `facts merge`;
- usa `candidate_id` per riconoscere la stessa proposta semantica fra esecuzioni.

Non passare un `candidate_id` deterministico al posto di un `CREC_...`.

### 19.3 La lista non obbliga a revisionare tutto

Ogni candidato che vuoi rendere effettivo deve essere confermato, manualmente o
da una policy autorizzata. Non devi però decidere ogni pending per poter
continuare in modalità non strict: i pending restano visibili e il merge li
salta.

Nel percorso Aurora corretto, le policy della sezione 8 riducono la coda
manuale. Devono restare manuali soprattutto:

- riferimenti Excel espliciti;
- proposte temporali;
- evidenze ambigue o discordanti;
- qualsiasi proposta per cui il revisore non possa verificare fonte e locator.

La CLI non offre una conferma manuale massiva: è una scelta di governance. Non
automatizzare un ciclo di `confirm` per aggirarla.

### 19.4 Raggruppare e rilevare duplicazioni

```bat
powershell -NoProfile -Command "$r=Get-Content -Raw -LiteralPath $env:PENDING_FILE|ConvertFrom-Json;$r.candidates|Group-Object record_type|Sort-Object Count -Descending|Select-Object Count,Name|Format-Table; 'Duplicati candidate_id:'; $r.candidates|Group-Object candidate_id|Where-Object Count -gt 1|Select-Object Count,Name|Format-Table"
```

In un percorso pulito non dovresti trovare la stessa identità deterministica
ripetuta in più candidate record dello stesso ciclo. Se trovi molte
duplicazioni, fermati: probabilmente `batch consolidate` è stato avviato più
volte come nuova run. Non revisionare entrambe le copie. Conserva il workspace
per audit e riparti con un nuovo nome, oppure analizza i batch prima di agire.

## 20. Ispezionare un candidato correttamente

Scegli una riga dalla tabella e copia i due ID della stessa riga:

```bat
set "CREC=CREC_000001"
set "CBATCH=CBATCH_000001"
```

Sostituisci entrambi i segnaposto. Mostra il dettaglio e salvalo:

```bat
set "SHOW_FILE=%WS%\candidate_%CREC%.json"
"%PY%" -m dsl_mngr candidates review show "%WS%" %CREC% > "%SHOW_FILE%"
set "SHOW_EXIT=%ERRORLEVEL%"
type "%SHOW_FILE%"
echo Exit code show: %SHOW_EXIT%
```

Prima della decisione controlla:

1. `candidate.candidate_record_id` e `candidate.batch_id`;
2. `candidate.record_type` e `candidate.assertion_type`;
3. il payload semantico proposto;
4. `evidence_text`, senza estrapolarlo dal contesto;
5. `source_revision_id`;
6. `chunk_id` o `fragment_id`;
7. locator, foglio/cella, path o righe sorgenti;
8. confidence e warning;
9. lineage e decisioni precedenti;
10. coerenza con il file originale e non soltanto con il testo normalizzato.

`Accepted` in un report di import significa soltanto valido rispetto allo
schema. Non significa `confirmed`.

## 21. Confermare, rifiutare o correggere

### 21.1 Confermare

```bat
"%PY%" -m dsl_mngr candidates review confirm "%WS%" %CREC% ^
  --actor-id aurora-reviewer ^
  --reason "Evidenza e locator verificati sulla fonte"
```

### 21.2 Rifiutare

```bat
"%PY%" -m dsl_mngr candidates review reject "%WS%" %CREC% ^
  --actor-id aurora-reviewer ^
  --reason "Evidenza insufficiente o significato non dimostrato"
```

La reason è obbligatoria per `reject` e `correct`; è consigliata anche per
`confirm`.

### 21.3 Correggere

La correzione non modifica il candidato originale. Crea una nuova foglia già
confermata, collega la lineage e rende l'originale superseded.

1. copia il solo oggetto `candidate.payload` mostrato dal comando `show`;
2. modifica esclusivamente i campi errati;
3. salva JSON valido sotto `<workspace>\corrections\`;
4. conserva o dichiara evidence refs coerenti.

Puoi estrarre il payload senza copiarlo a mano:

```bat
set "CORRECTIONS=%WS%\corrections"
if not exist "%CORRECTIONS%" mkdir "%CORRECTIONS%"
set "CORRECTED_PAYLOAD=%CORRECTIONS%\candidate_corretto.json"
powershell -NoProfile -Command "$d=Get-Content -Raw -LiteralPath $env:SHOW_FILE | ConvertFrom-Json; $d.candidate.payload | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 -LiteralPath $env:CORRECTED_PAYLOAD"
notepad "%CORRECTED_PAYLOAD%"
```

Il file deve contenere direttamente il payload completo, con le modifiche
necessarie: non deve contenere il wrapper `candidate`, le decisioni o l'intero
output di `review show`. Salva e chiudi l'editor prima di proseguire.

Esempio:

```bat
"%PY%" -m dsl_mngr candidates review correct "%WS%" %CREC% ^
  --actor-id aurora-reviewer ^
  --reason "Corretto il valore confrontandolo con la fonte" ^
  --payload "corrections\candidate_corretto.json"
```

### 21.4 Retry e concorrenza

```bat
"%PY%" -m dsl_mngr candidates review confirm "%WS%" %CREC% ^
  --actor-id aurora-reviewer ^
  --reason "Evidenza verificata" ^
  --idempotency-key "aurora-%CREC%-confirm-v1"
```

Un replay identico riusa la decisione. La stessa chiave con payload diverso
produce `idempotency_payload_conflict`. `--expected-head-decision-id` protegge
da una decisione concorrente quando conosci la testa corrente `RDEC_...`.

## 22. Eseguire il merge dei batch revisionati

Dopo aver confermato uno o più candidati, usa il `batch_id` associato nella
lista:

```bat
"%PY%" -m dsl_mngr facts merge "%WS%" --batch %CBATCH%
```

In modalità predefinita:

- le foglie confirmed vengono materializzate;
- pending, rejected, superseded e non-leaf vengono saltati e contati;
- ripetere il merge dello stesso contenuto è idempotente sugli identity hash.

Per richiedere che ogni candidato del batch sia eleggibile:

```bat
"%PY%" -m dsl_mngr facts merge "%WS%" --batch %CBATCH% --strict-review
```

Con `--strict-review`, anche un solo pending rende atomico il fallimento del
batch. Non usare questa opzione pensando che confermi i pending: non lo fa.

Per più batch già revisionati:

```bat
"%PY%" -m dsl_mngr facts merge-batch "%WS%" ^
  --batch CBATCH_000001 ^
  --batch CBATCH_000002
```

Sostituisci gli ID. `no_merge_eligible_candidates` con exit code `4` significa
che nel batch non esistono foglie confirmed materializzabili.

Puoi salvare liste separate per outcome:

```bat
"%PY%" -m dsl_mngr candidates review list "%WS%" --outcome pending > "%WS%\pending_candidates.json"
"%PY%" -m dsl_mngr candidates review list "%WS%" --outcome confirmed > "%WS%\confirmed_candidates.json"
"%PY%" -m dsl_mngr candidates review list "%WS%" --outcome rejected > "%WS%\rejected_candidates.json"
"%PY%" -m dsl_mngr candidates review list "%WS%" --outcome superseded > "%WS%\superseded_candidates.json"
```

## 23. Temporalità e conflitti Aurora

L'estrazione temporale è integrata nel batch; non esiste un comando leaf
`temporal` autonomo.

Nel corpus:

- due dichiarazioni indipendenti indicano `2025-11-18` e risultano concordanti;
- il manuale storico contiene `2012-06-01`;
- attribuire il valore storico e quello corrente allo stesso fatto crea una
  discordanza;
- nomi file e metadata sono soltanto evidenze grezze.

Un assessment `concordant` aumenta la qualità dell'evidenza, ma non conferma da
solo il candidato `temporal_interval`. Il conflitto storico/corrente deve restare
aperto finché manca una decisione motivata e non deve creare un falso intervallo
effettivo.

## 24. Reconcile dopo una correzione

Se correggi o sostituisci un candidato già materializzato può aprirsi una
richiesta di riconciliazione:

```bat
"%PY%" -m dsl_mngr facts reconcile "%WS%"
```

Oppure una richiesta specifica:

```bat
"%PY%" -m dsl_mngr facts reconcile "%WS%" ^
  --reconciliation-id RECON_000001 ^
  --strict
```

Sostituisci l'ID. Con una riconciliazione aperta, render, diff ed export sono
bloccati per default. La storia non viene cancellata: vengono riallineati i
supporti effettivi.

## 25. Creare snapshot DSL senza indovinare gli ID

### 25.1 Schema 1

```bat
set "DSL1_OUTPUT=%WS%\dsl_schema_01_output.txt"
"%PY%" -m dsl_mngr dsl render "%WS%" --schema-version 1 > "%DSL1_OUTPUT%"
type "%DSL1_OUTPUT%"
for /f "tokens=2" %I in ('findstr /b /c:"Snapshot:" "%DSL1_OUTPUT%"') do set "DSL1=%I"
echo Snapshot schema 1: %DSL1%
```

### 25.2 Schema 2

```bat
set "DSL2_OUTPUT=%WS%\dsl_schema_02_output.txt"
"%PY%" -m dsl_mngr dsl render "%WS%" --schema-version 2 > "%DSL2_OUTPUT%"
type "%DSL2_OUTPUT%"
for /f "tokens=2" %I in ('findstr /b /c:"Snapshot:" "%DSL2_OUTPUT%"') do set "DSL2=%I"
echo Snapshot schema 2: %DSL2%
```

Nei due comandi `for`, usa `%%I` se li copi in un file `.bat`.

Schema 1 è il profilo legacy/statico. Schema 2 legge le viste effettive e
include la temporalità governata. Uno snapshot è immutabile: decisioni successive
non modificano quello già creato; devi renderizzare un nuovo snapshot.

Se esiste una riconciliazione aperta e accetti consapevolmente una vista
incompleta, solo schema 2 permette:

```bat
"%PY%" -m dsl_mngr dsl render "%WS%" --schema-version 2 --allow-incomplete
```

`--allow-incomplete` omette oggetti non effettivi con warning. Non approva
pending. Schema 1 rifiuta questa opzione.

## 26. Confrontare gli snapshot

Per confrontare schema 1 e schema 2 devi dichiararlo esplicitamente:

```bat
"%PY%" -m dsl_mngr dsl diff "%WS%" --from %DSL1% --to %DSL2% --cross-schema
```

Il report separa cambiamenti `structural`, `governance` e `temporal`. Senza
`--cross-schema`, il confronto richiede snapshot dello stesso schema. Gli
artefatti vengono scritti per default in `exports\dsl_diff\`.

## 27. Esportare grafi GEXF

### 27.1 Grafo statico da schema 1

```bat
"%PY%" -m dsl_mngr graph export "%WS%" --snapshot-id %DSL1%
```

### 27.2 Grafo dinamico da schema 2

```bat
"%PY%" -m dsl_mngr graph export "%WS%" ^
  --snapshot-id %DSL2% ^
  --dynamic ^
  --timeformat date ^
  --temporal-output-mode strict
```

Il grafo dinamico usa GEXF 1.3 ed è validato offline sia contro gli XSD
vendorizzati sia con controlli semantici. La sola XSD non basta.

Se intervalli con profili incompatibili sono previsti e documentati:

```bat
"%PY%" -m dsl_mngr graph export "%WS%" --snapshot-id %DSL2% --dynamic --timeformat date --temporal-output-mode omit --allow-incomplete
"%PY%" -m dsl_mngr graph export "%WS%" --snapshot-id %DSL2% --dynamic --temporal-output-mode separate
```

- `strict` fallisce su profili incompatibili;
- `omit` omette con warning e richiede incomplete esplicito quando necessario;
- `separate` pubblica file distinti per profilo;
- le modalità temporali valgono soltanto con `--dynamic`;
- l'export dinamico richiede uno snapshot schema 2;
- l'export statico richiede schema 1.

Verifica nel `.graph_report.json` almeno validità XSD, validità semantica,
`timeformat`, numero di nodi, archi, orphan e warning.

## 28. Consultare run, log e UI locale

```bat
"%PY%" -m dsl_mngr run status "%WS%" RUN_000001
"%PY%" -m dsl_mngr log table "%WS%"
"%PY%" -m dsl_mngr log csv "%WS%" --output "run_log.csv"
```

Sostituisci il run ID. La UI è locale e read-only:

```bat
"%PY%" -m dsl_mngr ui serve "%WS%" --host 127.0.0.1 --port 8765
```

Apri `http://127.0.0.1:8765/` e usa `Ctrl+C` per arrestare il server. La UI
permette di consultare workspace, run, log, candidati rifiutati, conflitti,
snapshot e diff; non esegue review.

## 29. Exit code e diagnosi rapida

| Exit | Significato pratico |
|---:|---|
| 0 | comando completato, eventualmente con skip dichiarati |
| 2 | errore di uso, configurazione o applicazione |
| 3 | input o profilo semantico rifiutato |
| 4 | conflitto, precondizione, niente di mergeabile o reconcile richiesto |
| 5 | errore operativo o timeout worker |
| 6 | normalizzazione partial accettata e dichiarata |

Reason utili:

| Reason | Azione |
|---|---|
| `no_merge_eligible_candidates` | controlla policy e decisioni; non rilanciare un batch nuovo |
| `merge_review_precondition_failed` | con strict esiste almeno un record non eleggibile |
| `review_actor_required` | passa `--actor-id` o configura un default stabile |
| `review_head_conflict` | rileggi il candidato e la testa corrente |
| `idempotency_payload_conflict` | non riusare la stessa chiave per richieste diverse |
| `reconciliation_required` | esegui e verifica `facts reconcile` |
| `ooxml_security_violation` | input OOXML rifiutato; non aggirare il preflight |
| `ooxml_budget_exceeded` | input oltre i limiti configurati |
| `temporal_profile_incompatible` | scegli strict, omit o separate consapevolmente |
| `gexf_xsd_invalid` | grafo non conforme allo schema |
| `gexf_semantic_invalid` | grafo formalmente leggibile ma semanticamente incoerente |

### Tutti i candidati risultano pending

```bat
type "%WS%\configs\project.yaml"
```

Se `automatic_policies` è vuoto, aggiungi l'allowlist Aurora e riprendi il
`RUN_...` bloccato con `--resume`. Non avviare una nuova run completa.

### La lista contiene centinaia di duplicati

Raggruppa per `candidate_id` come nella sezione 19. Se ogni identità compare in
più batch, hai eseguito più consolidamenti nuovi. Non esiste un comando di
pulizia selettiva documentato per cancellare quei record. La soluzione sicura
per il laboratorio è conservare il workspace e crearne uno nuovo con nome
diverso.

### Il terminale sembra fermo durante Docling

Attendi e controlla processi e log. Non avviare in parallelo un altro batch sullo
stesso workspace. I timeout sono governati dal profilo worker.

### Un editor mostra contenuto di un altro JSON

Verifica il path completo della scheda, chiudi e riapri il file e controlla
`input.input_path`, `source_id` e `source_revision_id` nel
`docling_report.json`. Un editor può mantenere una vista non aggiornata.

## 30. Checklist finale del laboratorio

- [ ] È stato usato un workspace nuovo e separato.
- [ ] Python è 3.12 ed è quello di `.venv`.
- [ ] Sono state copiate soltanto 18 fonti operative.
- [ ] Tutti i checksum originali e delle copie coincidono.
- [ ] Il secondo scan riporta 18 sorgenti invariate.
- [ ] Le policy Aurora sono state configurate prima del batch.
- [ ] `batch consolidate` è stato lanciato una volta sola oppure ripreso con
  `--resume`.
- [ ] Il report contiene candidati auto-confermati e pending dichiarati.
- [ ] La matrice Excel ha 3 fogli, 5 regioni, 21 celle e 6 tipi.
- [ ] Formula/cache, merged range, named range ed external link coincidono.
- [ ] Il file XLSM contiene VBA ma dichiara macro e rete non eseguite.
- [ ] Nessun testo Docling o formula è stato assunto come verità di dominio.
- [ ] Il package AI DDL è `waiting_for_ai_candidates`, non stale e contiene
  una revisione, zero chunk e 38 frammenti.
- [ ] La fixture AI è stata copiata soltanto in `ai\inbox`, mai nel corpus.
- [ ] L'import AI ha creato due pending senza fatti né decisioni automatiche.
- [ ] Il fatto tecnico è stato confermato, la domanda ambigua rifiutata e il
  merge ha saltato il record rifiutato.
- [ ] Nessuna AI reale e nessun accesso di rete sono stati usati nel percorso
  controllato.
- [ ] Gli ID `CREC`, `CBATCH`, `RUN` e `DSL` sono quelli del workspace.
- [ ] Ogni decisione umana è motivata da evidence, locator e fonte.
- [ ] I pending non sono stati trattati come mergeabili.
- [ ] Eventuali correzioni hanno creato una nuova foglia e sono state
  riconciliate.
- [ ] DSL schema 1 e schema 2 non sono stati confusi.
- [ ] Il diff cross-schema usa `--cross-schema`.
- [ ] Il GEXF dinamico ha superato XSD e validazione semantica offline.

## 31. Riferimenti

- [LEGGIMI del corpus Aurora](../LEGGIMI_PRIMA.md)
- [Checklist dei risultati attesi](checklist_risultati_attesi.md)
- [Matrice fixture-requisiti](matrice_fixture_attesi.md)
- [Limitazioni intenzionali](limitazioni_intenzionali.md)
- [Manuale utente di DSL Manager](../../../../documenti/manuali/manuale_utente_dsl_manager.md)
- [Contratti dei manifest](../../../../documenti/documenti%20tecnici/contratti_manifest_dsl_manager.md)
- [Analisi tecnica](../../../../documenti/documenti%20tecnici/analisi_tecnica_dsl_manager.md)

Questa è la guida operativa corrente. La versione 01 precedente è conservata
separatamente soltanto per tracciabilità storica.
