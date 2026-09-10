# Guida completa allo scenario Aurora con DSL Manager — PowerShell — versione 02

Questa guida accompagna una persona che non ha mai usato DSL Manager dalla
preparazione dell'ambiente fino alla produzione e alla verifica di snapshot DSL
e grafi GEXF. I comandi sono pensati per PowerShell su Windows, eseguito dalla
root del repository `dsl_manager-v1`.

La guida riguarda il corpus dimostrativo Aurora Prestiti. Non è una procedura
generica per approvare automaticamente dati di produzione.

## 1. Risultato finale e modello mentale

DSL Manager non trasforma direttamente un documento in una verità di dominio.
Il flusso è governato:

```text
file del corpus
  -> sorgente e revisione identificata da hash
  -> testo normalizzato o frammenti strutturali
  -> candidati pending
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
- leggere gli ID prodotti dal programma senza riutilizzare i segnaposto;
- revisionare soltanto i candidati che richiedono davvero giudizio umano;
- eseguire merge, reconcile, render DSL, diff ed export GEXF;
- diagnosticare gli esiti più comuni senza cancellare dati alla cieca.

## 2. Vocabolario minimo

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
| review | decisione `confirmed`, `rejected` o `superseded` |
| pending | candidato privo di una decisione corrente; non è mergeabile |
| merge | materializzazione dei candidati confermati in fatti o relazioni |
| reconcile | riallineamento dopo una correzione di evidenza già materializzata |
| snapshot DSL | fotografia immutabile del registro consolidato, con ID `DSL_...` |
| run | esecuzione auditabile, con ID `RUN_...` |

Gli ID presenti negli esempi sono segnaposto. Devi sempre usare gli ID stampati
dal tuo workspace.

## 3. Sicurezza e confini dello scenario

Lo scenario è locale e usa dati fittizi:

- non chiama servizi AI;
- non richiede accesso alla rete durante l'elaborazione;
- non dereferenzia gli external link Excel;
- non esegue macro VBA;
- non ricalcola formule Excel;
- non usa i timestamp del filesystem come verità temporale;
- non considera automaticamente autorevoli nomi file, metadata, testo Docling o
  formule.

Il file `.xlsm` viene letto direttamente. Non viene convertito in `.xlsx`. Il
VBA viene soltanto rilevato e sottoposto a hash.

Non riutilizzare un workspace già popolato per seguire questa guida dall'inizio.
Una nuova esecuzione completa su uno stesso workspace può creare nuovi record e
batch per candidati semanticamente uguali. Se possiedi già un workspace, dagli
un nome diverso e conservalo come audit storico.

## 4. Prerequisiti

Servono:

- Windows con PowerShell;
- repository aperto nella sua directory root;
- Python 3.12 nell'ambiente virtuale `.venv`;
- corpus Aurora già presente nella knowledge base del repository;
- spazio sufficiente per modelli e artefatti Docling;
- file Excel chiusi durante i controlli degli hash, per evitare lock di lettura.

Verifica di essere nella root corretta:

```powershell
if (-not (Test-Path -LiteralPath ".\pyproject.toml")) {
    throw "Aprire PowerShell nella root di dsl_manager-v1."
}
if (-not (Test-Path -LiteralPath ".\.codex\config.toml")) {
    throw "Manca .codex/config.toml."
}
```

In questo progetto l'unico interprete locale ammesso è quello dichiarato come
`PROJECT_PYTHON` in `.codex/config.toml`. La configurazione corrente punta a
`.venv\Scripts\python.exe`.

## 5. Impostare i percorsi

Esegui questo blocco una volta nella sessione PowerShell:

```powershell
$ROOT = (Resolve-Path ".").Path
$PY = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$AURORA = (Resolve-Path ".\.kb\projects\corpus aurora\corpus_mock_aurora_prestiti").Path
$SOURCE = Join-Path $AURORA "corpus\active"
$SUPPORT = Join-Path $AURORA "materiale_di_supporto"
$WS = Join-Path $ROOT ".workspaces\laboratorio_aurora_v_02"
```

Controlla i valori:

```powershell
[pscustomobject]@{
    Repository = $ROOT
    Python = $PY
    Corpus = $SOURCE
    Supporto = $SUPPORT
    Workspace = $WS
} | Format-List
```

Questa guida richiede un workspace nuovo. Il controllo seguente evita di
sovrapporsi accidentalmente a una precedente esecuzione:

```powershell
if (Test-Path -LiteralPath $WS) {
    throw "Il workspace esiste già. Scegliere un nuovo nome in `$WS; non cancellarlo automaticamente."
}
```

Verifica Python e installa il progetto in modalità editable:

```powershell
& $PY --version
if ($LASTEXITCODE -ne 0) { throw "Python di progetto non avviabile." }

& $PY -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Installazione del progetto fallita." }

& $PY -m dsl_mngr --version
& $PY -m dsl_mngr --help
```

La versione Python deve appartenere alla serie 3.12. Non usare il Python
globale e non impostare `PYTHONPATH`.

## 6. Creare workspace e database

```powershell
& $PY -m dsl_mngr init $WS
if ($LASTEXITCODE -ne 0) { throw "Inizializzazione workspace fallita." }

& $PY -m dsl_mngr db init $WS
if ($LASTEXITCODE -ne 0) { throw "Inizializzazione database fallita." }
```

`init` crea directory e configurazioni. `db init` crea `workspace.sqlite` e
applica le migrazioni. Non modificare direttamente il database.

Controlla almeno questi elementi:

```powershell
Get-Item -LiteralPath `
    (Join-Path $WS "configs\project.yaml"), `
    (Join-Path $WS "workspace.sqlite"), `
    (Join-Path $WS "corpus\active")
```

## 7. Configurare le review automatiche prima del batch

### 7.1 Perché questo passaggio è indispensabile

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

### 7.2 Allowlist usata dallo scenario Aurora

Apri il file:

```powershell
notepad (Join-Path $WS "configs\project.yaml")
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

Controlla il blocco salvato:

```powershell
Get-Content -LiteralPath (Join-Path $WS "configs\project.yaml")
```

I nomi e le versioni delle policy devono coincidere esattamente. Una versione
inesistente, per esempio `/999`, non viene applicata.

## 8. Copiare esclusivamente le 18 fonti operative

Le directory `fixture_controllate` e gli altri file di supporto non devono
entrare in `corpus/active`.

```powershell
Get-ChildItem -LiteralPath $SOURCE |
    Copy-Item -Destination (Join-Path $WS "corpus\active") -Recurse -Force
```

Conta i file copiati:

```powershell
$COPIED_FILES = Get-ChildItem -LiteralPath (Join-Path $WS "corpus\active") -File -Recurse
$COPIED_FILES.Count
if ($COPIED_FILES.Count -ne 18) {
    throw "Attesi 18 file operativi, trovati $($COPIED_FILES.Count)."
}
```

Visualizza l'inventario relativo:

```powershell
$COPIED_FILES |
    ForEach-Object { $_.FullName.Substring($WS.Length + 1) } |
    Sort-Object
```

## 9. Verificare i checksum originali e delle copie

Il manifest `checksums.json` contiene sia le 18 fonti attive sia le due fixture
controllate. Il controllo seguente verifica tutti gli originali e, per le fonti
attive, anche la copia nel workspace:

```powershell
$CHECKSUM_PATH = Join-Path $SUPPORT "checksums.json"
$CHECKSUMS = Get-Content -Raw -LiteralPath $CHECKSUM_PATH | ConvertFrom-Json

foreach ($PROPERTY in $CHECKSUMS.files.PSObject.Properties) {
    $RELATIVE_PATH = $PROPERTY.Name
    $EXPECTED_HASH = $PROPERTY.Value.sha256
    $ORIGINAL_PATH = Join-Path $AURORA $RELATIVE_PATH
    $ORIGINAL_HASH = (Get-FileHash -Algorithm SHA256 -LiteralPath $ORIGINAL_PATH).Hash.ToLowerInvariant()

    if ($ORIGINAL_HASH -ne $EXPECTED_HASH) {
        throw "Checksum originale non valido: $RELATIVE_PATH"
    }

    if ($RELATIVE_PATH.StartsWith("corpus/active/")) {
        $WORKSPACE_PATH = Join-Path $WS $RELATIVE_PATH
        $WORKSPACE_HASH = (Get-FileHash -Algorithm SHA256 -LiteralPath $WORKSPACE_PATH).Hash.ToLowerInvariant()
        if ($WORKSPACE_HASH -ne $EXPECTED_HASH) {
            throw "Checksum copia non valido: $RELATIVE_PATH"
        }
    }
}

"Checksum originali e copie operative: OK"
```

Due valori di riferimento particolarmente importanti sono:

```text
matrice_stati_2025.xlsx
8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081

calcolo_rate_macro_2025.xlsm
17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4
```

Se un hash non coincide, fermati. Non eseguire lo scan su byte diversi e non
correggere il manifest degli hash per adattarlo a una copia inattesa.

## 10. Registrare il corpus con due scan

Il primo scan registra le sorgenti. Il secondo dimostra che ripetere lo scan
sugli stessi byte è idempotente.

```powershell
& $PY -m dsl_mngr corpus scan $WS
if ($LASTEXITCODE -ne 0) { throw "Primo scan fallito." }

& $PY -m dsl_mngr corpus scan $WS
if ($LASTEXITCODE -ne 0) { throw "Secondo scan fallito." }
```

Attese:

- primo scan: 18 sorgenti aggiunte;
- secondo scan: 18 sorgenti `Unchanged`;
- nessuna nuova revisione al secondo scan.

Una modifica reale dei byte crea una nuova `REV_...`; non sovrascrive la
revisione precedente.

## 11. Eseguire il batch consolidato una sola volta

### 11.1 Che cosa fa

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

### 11.2 Avvio e salvataggio dell'output

La normalizzazione Docling può durare diversi minuti. Non chiudere la console e
non lanciare un secondo batch mentre il primo è attivo.

```powershell
$BATCH_OUTPUT = Join-Path $WS "batch_consolidate_output.json"
$BATCH_RAW = & $PY -m dsl_mngr batch consolidate $WS | Out-String
$BATCH_EXIT = $LASTEXITCODE

$BATCH_RAW | Set-Content -Encoding utf8 -LiteralPath $BATCH_OUTPUT
$BATCH_RAW
"Exit code: $BATCH_EXIT"
```

Se l'output non è vuoto e contiene JSON valido:

```powershell
$BATCH = $BATCH_RAW | ConvertFrom-Json
$BATCH | Select-Object run_id, status, reason, exit_code, retryable
$BATCH.counters | Format-List
$BATCH.phases | Select-Object name, status, attempts
```

Il comando salva inoltre gli artefatti canonici sotto:

```text
<workspace>/artifacts/runs/<RUN_ID>/
```

Fra questi trovi normalmente `batch_report.json`, `batch_checkpoint.json`,
`input.json`, `output.json`, `process_report.json`, configurazione risolta e log.
Il file `batch_consolidate_output.json` creato sopra è soltanto una copia comoda
dell'output terminale.

### 11.3 Interpretare l'esito

Con le policy Aurora configurate correttamente ci si aspetta:

- almeno un candidato auto-confermato;
- candidati sensibili ancora pending;
- fatti e relazioni confermati materializzati;
- pending saltati in modo dichiarato dal merge non strict.

Controlla in particolare i contatori:

```text
auto_confirmed
review_pending
merged_candidates
skipped_pending
facts_created / facts_existing
relations_created / relations_existing
```

Un exit code `0` indica completamento. Un exit code `4` con reason
`no_merge_eligible_candidates` è tipico quando nessuna policy è stata applicata
e nessun candidato è stato confermato. Non significa che i candidati siano
persi.

### 11.4 Riprendere, non rilanciare

Se il processo viene interrotto o resta bloccato per policy mancanti:

1. conserva il `run_id` del batch;
2. correggi la causa, per esempio `configs/project.yaml`;
3. riprendi quella run.

```powershell
$FAILED_RUN = "RUN_000001"  # sostituire con $BATCH.run_id o con l'ID reale
& $PY -m dsl_mngr batch consolidate $WS --resume $FAILED_RUN
```

`--resume` riusa i checkpoint completati e ricalcola solo le fasi necessarie.
Le policy correnti vengono rilette. Non usare un nuovo `batch consolidate $WS`
per tentare di sbloccare la stessa elaborazione: una nuova run completa può
creare nuovi `CBATCH_...` e `CREC_...` per gli stessi `candidate_id`.

Per controllare una run:

```powershell
& $PY -m dsl_mngr run status $WS $FAILED_RUN
```

## 12. Trovare gli ID di sorgente e revisione

Non indovinare gli ID. Costruisci un indice dai `docling_report.json` prodotti:

```powershell
$SOURCE_INDEX = foreach ($REPORT_FILE in Get-ChildItem -LiteralPath (Join-Path $WS "normalized") -Filter "docling_report.json" -File -Recurse) {
    $REPORT = Get-Content -Raw -LiteralPath $REPORT_FILE.FullName | ConvertFrom-Json
    [pscustomobject]@{
        SourceId = $REPORT.input.source_id
        RevisionId = $REPORT.input.source_revision_id
        InputPath = $REPORT.input.input_path
        ReportPath = $REPORT_FILE.FullName
    }
}

$SOURCE_INDEX | Sort-Object InputPath | Format-Table -AutoSize
```

Individua i due workbook:

```powershell
$MATRIX_ENTRY = $SOURCE_INDEX | Where-Object InputPath -like "*matrice_stati_2025.xlsx"
$MACRO_ENTRY = $SOURCE_INDEX | Where-Object InputPath -like "*calcolo_rate_macro_2025.xlsm"

if (@($MATRIX_ENTRY).Count -ne 1) { throw "Manifest della matrice non individuato in modo univoco." }
if (@($MACRO_ENTRY).Count -ne 1) { throw "Manifest del file macro non individuato in modo univoco." }

$MATRIX_DIR = Split-Path -Parent $MATRIX_ENTRY.ReportPath
$MACRO_DIR = Split-Path -Parent $MACRO_ENTRY.ReportPath

$MATRIX_ENTRY | Format-List
$MACRO_ENTRY | Format-List
```

In un workspace Aurora pulito gli ID sono normalmente `SRC_000006 / REV_000006`
per la matrice e `SRC_000003 / REV_000003` per il file macro, ma il controllo
sull'`input_path` resta la verifica autorevole.

## 13. Capire gli artefatti di normalizzazione

Per ciascun workbook valido la directory `normalized/<SRC>/<REV>/` contiene:

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

## 14. Verificare automaticamente `matrice_stati_2025.xlsx`

```powershell
$MATRIX_MANIFEST_PATH = Join-Path $MATRIX_DIR "workbook_manifest.json"
$MATRIX_REPORT_PATH = Join-Path $MATRIX_DIR "workbook_report.json"
$MATRIX_MANIFEST = Get-Content -Raw -LiteralPath $MATRIX_MANIFEST_PATH | ConvertFrom-Json
$MATRIX_REPORT = Get-Content -Raw -LiteralPath $MATRIX_REPORT_PATH | ConvertFrom-Json

$REGION_COUNT = ($MATRIX_MANIFEST.sheets | ForEach-Object { $_.regions.Count } | Measure-Object -Sum).Sum
$CELL_TYPES = @($MATRIX_MANIFEST.sheets.cells.type | Sort-Object -Unique)
$D2 = $MATRIX_MANIFEST.sheets[0].cells | Where-Object coordinate -eq "D2"
$E2 = $MATRIX_MANIFEST.sheets[0].cells | Where-Object coordinate -eq "E2"

$CHECKS = @(
    [pscustomobject]@{ Controllo = "Tre fogli"; OK = $MATRIX_MANIFEST.sheets.Count -eq 3; Valore = ($MATRIX_MANIFEST.sheets.name -join " | ") },
    [pscustomobject]@{ Controllo = "Visibilità"; OK = ($MATRIX_MANIFEST.sheets.visibility -join ",") -eq "visible,hidden,very_hidden"; Valore = ($MATRIX_MANIFEST.sheets.visibility -join " | ") },
    [pscustomobject]@{ Controllo = "Cinque regioni"; OK = $REGION_COUNT -eq 5; Valore = [string]$REGION_COUNT },
    [pscustomobject]@{ Controllo = "Ventuno celle"; OK = $MATRIX_MANIFEST.sheets.cells.Count -eq 21; Valore = [string]$MATRIX_MANIFEST.sheets.cells.Count },
    [pscustomobject]@{ Controllo = "Formula con cache"; OK = $D2.formula -eq "B2+C2" -and $D2.cached_value -eq "3.5"; Valore = "D2 formula=$($D2.formula), cache=$($D2.cached_value)" },
    [pscustomobject]@{ Controllo = "Formula senza cache"; OK = $E2.formula -eq "B2*C2" -and $null -eq $E2.cached_value; Valore = "E2 formula=$($E2.formula), cache=null" },
    [pscustomobject]@{ Controllo = "Merged range"; OK = $MATRIX_MANIFEST.sheets[0].merged_ranges -contains "A3:B3"; Valore = ($MATRIX_MANIFEST.sheets[0].merged_ranges -join " | ") },
    [pscustomobject]@{ Controllo = "Due named range"; OK = $MATRIX_MANIFEST.named_ranges.Count -eq 2; Valore = ($MATRIX_MANIFEST.named_ranges.name -join " | ") },
    [pscustomobject]@{ Controllo = "Sei tipi cella"; OK = $CELL_TYPES.Count -eq 6; Valore = ($CELL_TYPES -join " | ") },
    [pscustomobject]@{ Controllo = "External link non aperto"; OK = $MATRIX_MANIFEST.external_links[0].disposition -eq "not_dereferenced"; Valore = $MATRIX_MANIFEST.external_links[0].disposition },
    [pscustomobject]@{ Controllo = "Fonte strutturale"; OK = $MATRIX_REPORT.structural_source -eq "workbook_manifest.json"; Valore = $MATRIX_REPORT.structural_source }
)

$CHECKS | Format-Table -Wrap -AutoSize
if ($CHECKS.OK -contains $false) { throw "Uno o più controlli della matrice sono falliti." }
```

`very_hidden` è il valore serializzato che corrisponde allo stato Excel
`veryHidden`.

Per vedere tutte le formule e distinguere formula, valore e cache:

```powershell
$MATRIX_MANIFEST.sheets.cells |
    Where-Object { $null -ne $_.formula } |
    Select-Object coordinate, formula, cached_value, value, type |
    Format-Table -AutoSize
```

I named range attesi sono:

- `MainBlock` -> `'Résumé'!$A$1:$F$3`, scope workbook;
- `LocalPair` -> `'Résumé'!$H$10:$I$10`, scope foglio `Résumé`.

## 15. Verificare sicurezza e macro di `calcolo_rate_macro_2025.xlsm`

```powershell
$MACRO_MANIFEST = Get-Content -Raw -LiteralPath (Join-Path $MACRO_DIR "workbook_manifest.json") | ConvertFrom-Json
$MACRO_REPORT = Get-Content -Raw -LiteralPath (Join-Path $MACRO_DIR "workbook_report.json") | ConvertFrom-Json

[pscustomobject]@{
    MacroPresent = $MACRO_MANIFEST.macros.present
    MacroPart = $MACRO_MANIFEST.macros.part_name
    MacroHash = $MACRO_MANIFEST.macros.content_hash
    ManifestExecuted = $MACRO_MANIFEST.macros.executed
    ReportMacrosExecuted = $MACRO_REPORT.macros_executed
    NetworkAccessed = $MACRO_REPORT.network_accessed
    StructuralSource = $MACRO_REPORT.structural_source
} | Format-List

if ($MACRO_MANIFEST.macros.present -ne $true) { throw "Macro non rilevata." }
if ($MACRO_MANIFEST.macros.part_name -ne "xl/vbaProject.bin") { throw "Parte VBA inattesa." }
if ($MACRO_MANIFEST.macros.executed -ne $false) { throw "Il manifest dichiara una macro eseguita." }
if ($MACRO_REPORT.macros_executed -ne $false) { throw "Il report dichiara una macro eseguita." }
if ($MACRO_REPORT.network_accessed -ne $false) { throw "Il report dichiara accesso rete." }
```

La presenza di `xl/vbaProject.bin` dimostra che il file è realmente
macro-enabled. `executed: false` significa che DSL Manager non ha eseguito VBA.

## 16. Test controllati: cosa verificano e cosa non verificano

Il test seguente verifica checksum, scenario E2E, malformed, partial, budget e
assenza di rete in workspace temporanei:

```powershell
& $PY -m pytest -q tests/test_slice_28_aurora_e2e.py
```

Il test non sostituisce il controllo degli artefatti del tuo `$WS`: usa
workspace temporanei e, per alcuni casi, adapter controllati.

Le fixture:

- `workbook_malformed_controllato.xlsx` deve essere rifiutata in preflight con
  reason `ooxml_security_violation`;
- `workbook_partial_controllato.xlsx` è un package valido usato per iniettare
  nel test un `partial_success`, con status `partial` ed exit code `6`;
- nessuna delle due va copiata in `corpus/active`.

## 17. Capire e salvare la lista dei candidati

### 17.1 Il comando non crea un file

```powershell
& $PY -m dsl_mngr candidates review list $WS --outcome pending
```

Il comando legge il database e stampa JSON sul terminale. Non crea una run e
non pubblica un artefatto: il payload contiene `artifact_paths: []`,
`run_id: null` e `mutations: false`. I candidati restano comunque persistiti in
`workspace.sqlite`.

Per conservare una fotografia leggibile dalla sessione:

```powershell
$PENDING_PATH = Join-Path $WS "pending_candidates.json"
$PENDING_RAW = & $PY -m dsl_mngr candidates review list $WS --outcome pending | Out-String
if ($LASTEXITCODE -ne 0) { throw "Lettura candidati pending fallita." }
$PENDING_RAW | Set-Content -Encoding utf8 -LiteralPath $PENDING_PATH
$PENDING = $PENDING_RAW | ConvertFrom-Json

"Pending: $($PENDING.count)"
$PENDING.candidates |
    Select-Object candidate_record_id, batch_id, candidate_id, record_type, assertion_type, confidence |
    Format-Table -AutoSize
```

### 17.2 Cosa significano i tre ID

Per una riga della lista:

- usa `candidate_record_id`, per esempio `CREC_...`, con `review show`,
  `confirm`, `reject` o `correct`;
- usa `batch_id`, per esempio `CBATCH_...`, con `facts merge`;
- usa `candidate_id` per riconoscere la stessa proposta semantica fra esecuzioni.

Non passare un `candidate_id` deterministico al posto di un `CREC_...`.

### 17.3 La lista non obbliga a revisionare tutto

Ogni candidato che vuoi rendere effettivo deve essere confermato, manualmente o
da una policy autorizzata. Non devi però decidere ogni pending per poter
continuare in modalità non strict: i pending restano visibili e il merge li
salta.

Nel percorso Aurora corretto, le policy della sezione 7 riducono la coda
manuale. Devono restare manuali soprattutto:

- riferimenti Excel espliciti;
- proposte temporali;
- evidenze ambigue o discordanti;
- qualsiasi proposta per cui il revisore non possa verificare fonte e locator.

La CLI non offre una conferma manuale massiva: è una scelta di governance. Non
automatizzare un ciclo di `confirm` per aggirarla.

### 17.4 Raggruppare e rilevare duplicazioni

```powershell
$PENDING.candidates | Group-Object record_type | Sort-Object Count -Descending |
    Select-Object Count, Name | Format-Table -AutoSize

$PENDING.candidates | Group-Object assertion_type | Sort-Object Count -Descending |
    Select-Object Count, Name | Format-Table -AutoSize

$DUPLICATES = $PENDING.candidates | Group-Object candidate_id | Where-Object Count -gt 1
$DUPLICATES | Select-Object Count, Name | Format-Table -AutoSize
```

In un percorso pulito non dovresti trovare la stessa identità deterministica
ripetuta in più candidate record dello stesso ciclo. Se trovi molte
duplicazioni, fermati: probabilmente `batch consolidate` è stato avviato più
volte come nuova run. Non revisionare entrambe le copie. Conserva il workspace
per audit e riparti con un nuovo nome, oppure analizza i batch prima di agire.

## 18. Ispezionare un candidato correttamente

Scegli una riga dalla lista, non il primo elemento alla cieca:

```powershell
$SELECTED = $PENDING.candidates |
    Where-Object { $_.record_type -in @("candidate_fact", "candidate_relation", "temporal_interval") } |
    Select-Object -First 1

$SELECTED | Format-List
$CREC = $SELECTED.candidate_record_id
$CBATCH = $SELECTED.batch_id
```

Mostra il dettaglio e salvalo:

```powershell
$SHOW_PATH = Join-Path $WS ("candidate_{0}.json" -f $CREC.ToLowerInvariant())
$SHOW_RAW = & $PY -m dsl_mngr candidates review show $WS $CREC | Out-String
if ($LASTEXITCODE -ne 0) { throw "Candidate show fallito." }
$SHOW_RAW | Set-Content -Encoding utf8 -LiteralPath $SHOW_PATH
$DETAIL = $SHOW_RAW | ConvertFrom-Json
$DETAIL | ConvertTo-Json -Depth 20
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

## 19. Confermare, rifiutare o correggere

### 19.1 Confermare

```powershell
& $PY -m dsl_mngr candidates review confirm $WS $CREC `
    --actor-id aurora-reviewer `
    --reason "Evidenza e locator verificati sulla fonte"
```

### 19.2 Rifiutare

```powershell
& $PY -m dsl_mngr candidates review reject $WS $CREC `
    --actor-id aurora-reviewer `
    --reason "Evidenza insufficiente o significato non dimostrato"
```

La reason è obbligatoria per `reject` e `correct`; è consigliata anche per
`confirm`.

### 19.3 Correggere

La correzione non modifica il candidato originale. Crea una nuova foglia già
confermata, collega la lineage e rende l'originale superseded.

1. copia il solo oggetto `candidate.payload` mostrato dal comando `show`;
2. modifica esclusivamente i campi errati;
3. salva JSON valido sotto `<workspace>/corrections/`;
4. conserva o dichiara evidence refs coerenti.

Puoi estrarre il payload senza copiarlo a mano:

```powershell
$CORRECTIONS = Join-Path $WS "corrections"
New-Item -ItemType Directory -Force -Path $CORRECTIONS | Out-Null
$CORRECTED_PAYLOAD = Join-Path $CORRECTIONS "candidate_corretto.json"
$DETAIL.candidate.payload |
    ConvertTo-Json -Depth 20 |
    Set-Content -Encoding utf8 -LiteralPath $CORRECTED_PAYLOAD
notepad $CORRECTED_PAYLOAD
```

Il file deve contenere direttamente il payload completo, con le modifiche
necessarie: non deve contenere il wrapper `candidate`, le decisioni o l'intero
output di `review show`. Salva e chiudi l'editor prima di proseguire.

Esempio di invocazione:

```powershell
& $PY -m dsl_mngr candidates review correct $WS $CREC `
    --actor-id aurora-reviewer `
    --reason "Corretto il valore confrontandolo con la fonte" `
    --payload "corrections/candidate_corretto.json"
```

### 19.4 Retry e concorrenza

Per operazioni richiamate da automazioni usa una chiave idempotente stabile:

```powershell
& $PY -m dsl_mngr candidates review confirm $WS $CREC `
    --actor-id aurora-reviewer `
    --reason "Evidenza verificata" `
    --idempotency-key "aurora-$CREC-confirm-v1"
```

Un replay identico riusa la decisione. La stessa chiave con payload diverso
produce `idempotency_payload_conflict`. `--expected-head-decision-id` protegge
da una decisione concorrente quando conosci la testa corrente `RDEC_...`.

## 20. Eseguire il merge dei batch revisionati

Dopo aver confermato uno o più candidati, usa il `batch_id` associato nella
lista:

```powershell
& $PY -m dsl_mngr facts merge $WS --batch $CBATCH
```

In modalità predefinita:

- le foglie confirmed vengono materializzate;
- pending, rejected, superseded e non-leaf vengono saltati e contati;
- ripetere il merge dello stesso contenuto è idempotente sugli identity hash.

Per richiedere che ogni candidato del batch sia eleggibile:

```powershell
& $PY -m dsl_mngr facts merge $WS --batch $CBATCH --strict-review
```

Con `--strict-review`, anche un solo pending rende atomico il fallimento del
batch. Non usare questa opzione pensando che confermi i pending: non lo fa.

Per più batch già revisionati:

```powershell
& $PY -m dsl_mngr facts merge-batch $WS `
    --batch "CBATCH_000001" `
    --batch "CBATCH_000002"
```

Sostituisci gli ID. `no_merge_eligible_candidates` con exit code `4` significa
che nel batch non esistono foglie confirmed materializzabili.

Puoi controllare le code per outcome:

```powershell
& $PY -m dsl_mngr candidates review list $WS --outcome pending
& $PY -m dsl_mngr candidates review list $WS --outcome confirmed
& $PY -m dsl_mngr candidates review list $WS --outcome rejected
& $PY -m dsl_mngr candidates review list $WS --outcome superseded
```

## 21. Temporalità e conflitti Aurora

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

## 22. Reconcile dopo una correzione

Se correggi o sostituisci un candidato già materializzato può aprirsi una
richiesta di riconciliazione. Controlla i report della correzione e poi:

```powershell
& $PY -m dsl_mngr facts reconcile $WS
```

Oppure una richiesta specifica:

```powershell
& $PY -m dsl_mngr facts reconcile $WS `
    --reconciliation-id "RECON_000001" `
    --strict
```

Con una riconciliazione aperta, render, diff ed export sono bloccati per
default. La storia non viene cancellata: vengono riallineati i supporti
effettivi.

## 23. Creare snapshot DSL senza indovinare gli ID

### 23.1 Schema 1

```powershell
$DSL1_LINES = & $PY -m dsl_mngr dsl render $WS --schema-version 1
$DSL1_LINES
$DSL1 = (($DSL1_LINES | Where-Object { $_ -like "Snapshot:*" }) -split ":", 2)[1].Trim()
"Snapshot schema 1: $DSL1"
```

### 23.2 Schema 2

```powershell
$DSL2_LINES = & $PY -m dsl_mngr dsl render $WS --schema-version 2
$DSL2_LINES
$DSL2 = (($DSL2_LINES | Where-Object { $_ -like "Snapshot:*" }) -split ":", 2)[1].Trim()
"Snapshot schema 2: $DSL2"
```

Schema 1 è il profilo legacy/statico. Schema 2 legge le viste effettive e
include la temporalità governata. Uno snapshot è immutabile: decisioni successive
non modificano quello già creato; devi renderizzare un nuovo snapshot.

Se esiste una riconciliazione aperta e accetti consapevolmente una vista
incompleta, solo schema 2 permette:

```powershell
& $PY -m dsl_mngr dsl render $WS --schema-version 2 --allow-incomplete
```

`--allow-incomplete` omette oggetti non effettivi con warning. Non approva
pending. Schema 1 rifiuta questa opzione.

## 24. Confrontare gli snapshot

Per confrontare schema 1 e schema 2 devi dichiararlo esplicitamente:

```powershell
& $PY -m dsl_mngr dsl diff $WS --from $DSL1 --to $DSL2 --cross-schema
```

Il report separa cambiamenti:

- `structural`;
- `governance`;
- `temporal`.

Senza `--cross-schema`, il confronto richiede snapshot dello stesso schema.
Gli artefatti vengono scritti per default in `exports/dsl_diff/`.

## 25. Esportare grafi GEXF

### 25.1 Grafo statico da schema 1

```powershell
& $PY -m dsl_mngr graph export $WS --snapshot-id $DSL1
```

### 25.2 Grafo dinamico da schema 2

```powershell
& $PY -m dsl_mngr graph export $WS `
    --snapshot-id $DSL2 `
    --dynamic `
    --timeformat date `
    --temporal-output-mode strict
```

Il grafo dinamico usa GEXF 1.3 ed è validato offline sia contro gli XSD
vendorizzati sia con controlli semantici. La sola XSD non basta.

Se intervalli con profili incompatibili sono previsti e documentati:

```powershell
& $PY -m dsl_mngr graph export $WS --snapshot-id $DSL2 --dynamic `
    --timeformat date --temporal-output-mode omit --allow-incomplete

& $PY -m dsl_mngr graph export $WS --snapshot-id $DSL2 --dynamic `
    --temporal-output-mode separate
```

- `strict` fallisce su profili incompatibili;
- `omit` omette con warning e richiede incomplete esplicito quando necessario;
- `separate` pubblica file distinti per profilo;
- le modalità temporali valgono soltanto con `--dynamic`;
- l'export dinamico richiede uno snapshot schema 2;
- l'export statico richiede schema 1.

Verifica nel `.graph_report.json` almeno validità XSD, validità semantica,
`timeformat`, numero di nodi, archi, orphan e warning.

## 26. Consultare run, log e UI locale

```powershell
& $PY -m dsl_mngr run status $WS "RUN_000001"
& $PY -m dsl_mngr log table $WS
& $PY -m dsl_mngr log csv $WS --output "run_log.csv"
```

Sostituisci il run ID. La UI è locale e read-only:

```powershell
& $PY -m dsl_mngr ui serve $WS --host 127.0.0.1 --port 8765
```

Apri `http://127.0.0.1:8765/` e usa `Ctrl+C` per arrestare il server. La UI
permette di consultare workspace, run, log, candidati rifiutati, conflitti,
snapshot e diff; non esegue review.

## 27. Exit code e diagnosi rapida

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

Controlla:

```powershell
(Get-Content -Raw -LiteralPath (Join-Path $WS "configs\project.yaml"))
```

Se `automatic_policies` è vuoto, aggiungi l'allowlist Aurora e riprendi il
`RUN_...` bloccato con `--resume`. Non avviare una nuova run completa.

### La lista contiene centinaia di duplicati

Raggruppa per `candidate_id` come nella sezione 17. Se ogni identità compare in
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

## 28. Checklist finale del laboratorio

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
- [ ] Gli ID `CREC`, `CBATCH`, `RUN` e `DSL` sono quelli del workspace.
- [ ] Ogni decisione umana è motivata da evidence, locator e fonte.
- [ ] I pending non sono stati trattati come mergeabili.
- [ ] Eventuali correzioni hanno creato una nuova foglia e sono state
  riconciliate.
- [ ] DSL schema 1 e schema 2 non sono stati confusi.
- [ ] Il diff cross-schema usa `--cross-schema`.
- [ ] Il GEXF dinamico ha superato XSD e validazione semantica offline.

## 29. Riferimenti

- [LEGGIMI del corpus Aurora](../LEGGIMI_PRIMA.md)
- [Checklist dei risultati attesi](checklist_risultati_attesi.md)
- [Matrice fixture-requisiti](matrice_fixture_attesi.md)
- [Limitazioni intenzionali](limitazioni_intenzionali.md)
- [Manuale utente di DSL Manager](../../../../documenti/manuali/manuale_utente_dsl_manager.md)
- [Contratti dei manifest](../../../../documenti/documenti%20tecnici/contratti_manifest_dsl_manager.md)
- [Analisi tecnica](../../../../documenti/documenti%20tecnici/analisi_tecnica_dsl_manager.md)

Questa è la versione 02 della guida PowerShell. La guida storica
`guida_dsl-manager-powershell.md` resta invariata perché è referenziata da altri
documenti e test.
