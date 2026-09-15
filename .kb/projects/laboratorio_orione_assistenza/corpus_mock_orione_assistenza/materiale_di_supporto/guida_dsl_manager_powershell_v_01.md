# Guida DSL Manager in PowerShell - Orione Assistenza v 01

Questa guida accompagna una sessione nuova dall'inventario delle fonti al DSL e
al grafo temporale. PowerShell prepara il laboratorio e legge gli output; ogni
operazione applicativa e' affidata a `python -m dsl_mngr`. Non sostituire una
funzione disponibile nella CLI con query SQLite, SQL, import di moduli interni o
scritture manuali nel workspace.

## 1. Modello mentale e confini

Il `corpus` e' la copia di lavoro delle fonti. Lo `scan` registra revisioni ma
non produce verita'. La pipeline normalizza, crea chunk o frammenti, propone
candidati, applica solo l'allowlist conservativa e materializza fatti e
relazioni confermati. Un import AI crea candidati `pending`: una persona deve
confermarli, rifiutarli o correggerli. Il DSL e il GEXF sono fotografie
riproducibili dello stato governato.

La shell e' ammessa soltanto per risolvere l'interprete, creare una directory
temporanea, copiare byte per byte le fonti, calcolare hash, leggere JSON/XML,
provare HTTP in loopback e tenere un diario. Configurazione review,
propagazione temporale e diagnostica partial sono esposte dai leaf pubblici
Slice 31; la shell non importa servizi core e non seleziona worker.

Exit code comuni: `0` successo; `2` errore di uso o fallimento operativo;
`3` input semantico rifiutato; `4` conflitto/precondizione; `6` partial
controllato.
Conservare sempre stdout, stderr, exit code, ID e percorso del report.

## 2. Preparazione sicura

Scopo: individuare la root senza codificarla, usare Python 3.12 configurato e
creare una sessione esterna al repository. Prerequisiti: partire da una copia
integra di questo progetto.

```powershell
$cursor = Get-Item -LiteralPath $PWD
while ($null -ne $cursor -and -not (
  (Test-Path -LiteralPath (Join-Path $cursor.FullName 'AGENTS.md')) -and
  (Test-Path -LiteralPath (Join-Path $cursor.FullName 'pyproject.toml')) -and
  (Test-Path -LiteralPath (Join-Path $cursor.FullName '.codex\config.toml'))
)) { $cursor = $cursor.Parent }
if ($null -eq $cursor) { throw 'Root del progetto non trovata' }
$repo = $cursor.FullName
$config = Get-Content -LiteralPath (Join-Path $repo '.codex\config.toml') -Raw
$python_rel = [regex]::Match($config, 'PROJECT_PYTHON\s*=\s*"([^"]+)"').Groups[1].Value
$project_python = (Resolve-Path (Join-Path $repo $python_rel)).Path
& $project_python --version
if ($LASTEXITCODE -ne 0) { throw 'Interprete non utilizzabile' }

$lab = Join-Path $repo '.kb\projects\laboratorio_orione_assistenza\corpus_mock_orione_assistenza'
$session_root = Join-Path ([IO.Path]::GetTempPath()) ('orione_assistenza_' + [guid]::NewGuid().ToString('N'))
$workspace = Join-Path $session_root 'workspace'
$source_copy = Join-Path $session_root 'input_active'
New-Item -ItemType Directory -Path $source_copy | Out-Null
Copy-Item -Path (Join-Path $lab 'corpus\active\*') -Destination $source_copy -Recurse
```

Cambia soltanto il temporaneo. Atteso: Python `3.12.x`; directory nuova. Se
`PROJECT_PYTHON` manca, fermarsi e correggere la configurazione del progetto,
non ripiegare su `python`. Se la destinazione esiste, crearne un'altra: non
cancellarla e non sovrascriverla.

## 3. Init, database, copia e checksum

Scopo: creare un workspace supportato e copiarvi soltanto le quindici fonti
attive. `init` crea struttura/config; `db init` applica le migrazioni pubbliche.

```powershell
& $project_python -m dsl_mngr init $workspace
if ($LASTEXITCODE -ne 0) { throw 'init fallito' }
& $project_python -m dsl_mngr db init $workspace
if ($LASTEXITCODE -ne 0) { throw 'db init fallito' }

$working_corpus = Join-Path $workspace 'corpus\active'
Copy-Item -Path (Join-Path $source_copy '*') -Destination $working_corpus -Recurse
$before = Get-ChildItem -LiteralPath $source_copy -Recurse -File | ForEach-Object {
  [pscustomobject]@{ path=$_.FullName.Substring($source_copy.Length + 1); sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash }
}
$after = Get-ChildItem -LiteralPath $working_corpus -Recurse -File | ForEach-Object {
  [pscustomobject]@{ path=$_.FullName.Substring($working_corpus.Length + 1); sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash }
}
if ((Compare-Object $before $after -Property path,sha256)) { throw 'Checksum discordante: non eseguire scan' }
```

Atteso: exit `0`, 12 migrazioni al primo `db init`, nessuna differenza hash.
Errore comune: usare `$input`, variabile automatica PowerShell, per l'elenco
hash; usare invece `$before` e `$after`. Se `init` segnala un workspace gia'
presente, selezionare una directory nuova o riprendere deliberatamente la sua
`session_state.json`.

## 4. Due scan e allowlist conservativa

Scopo: registrare una sola revisione per fonte e verificare l'idempotenza. La
configurazione review va governata nel solo workspace mediante il profilo
built-in `conservative/1`: tabelle, colonne, FK risolte, form e
operazioni XML, code unit e dipendenze PL/SQL, eventi log nominati, workbook,
sheet, regioni, tabelle e named range Excel. Non auto-confermare view non
supportate, relazioni interpretative, SLA narrativi o temporalita'.

```powershell
& $project_python -m dsl_mngr config review show $workspace
& $project_python -m dsl_mngr config review profiles $workspace
$profile_json = & $project_python -m dsl_mngr config review apply-profile $workspace --profile 'conservative/1'
if ($LASTEXITCODE -ne 0) { throw 'profilo review non applicato' }
$profile = $profile_json | ConvertFrom-Json
if (@($profile.effective_policies).Count -ne 13) { throw 'profilo conservativo inatteso' }
& $project_python -m dsl_mngr config validate $workspace --profile 'conservative/1'
if ($LASTEXITCODE -ne 0) { throw 'configurazione review non valida' }
& $project_python -m dsl_mngr corpus scan $workspace
$scan_1_exit = $LASTEXITCODE
& $project_python -m dsl_mngr corpus scan $workspace
$scan_2_exit = $LASTEXITCODE
if ($scan_1_exit -ne 0 -or $scan_2_exit -ne 0) { throw 'scan fallito' }
```

Atteso: profilo di 13 policy e validazione exit `0`; primo scan `Added: 15`;
secondo `Unchanged: 15`, exit `0`. Non modificare il YAML a mano. Per proteggere
un aggiornamento concorrente passare il `config_hash` di `show` a
`apply-profile --expect-config-hash`. Se il secondo scan produce `Modified`, ricopiare
dalla fonte canonica, confrontare gli hash e ripartire con un workspace nuovo.

## 5. Consolidamento deterministico e checkpoint

Scopo: esercitare tutti i parser e riconciliare il registro effettivo.

```powershell
$batch_output = & $project_python -m dsl_mngr batch consolidate $workspace --reconcile 2>&1
$batch_exit = $LASTEXITCODE
$batch_output | ForEach-Object { $_ }
$run_id = [regex]::Match(($batch_output -join "`n"), 'RUN_\d{6}').Value
if (-not $run_id) { throw 'RUN non ricavato: conservare output e fermarsi' }
& $project_python -m dsl_mngr run status $workspace $run_id
```

Atteso sul corpus integro: exit `0`; 15 revisioni, 25 operazioni di parse, 117
candidati, 86 auto-confermati, 31 candidati temporali pending, 78 fatti e 8
relazioni al primo passaggio. I conteggi sono diagnostici della fixture v 01,
non una ragione per cambiare gli expected dopo il fatto. Ispezionare
`artifacts/runs/$run_id/batch_report.json`, `normalized/`, `chunks/` e
`fragments/`: devono comparire DDL, PL/SQL, Forms XML, log, Markdown, TXT, HTML,
DOCX, PDF, PPTX, XLSX e XLSM. La macro deve risultare presente e hashata, mai
eseguita; l'external link `.invalid` inventariato, mai dereferenziato.

Se lo stato e' `failed` e il report dichiara `retryable`, il solo recupero
applicativo e':

```powershell
& $project_python -m dsl_mngr batch consolidate $workspace --reconcile --resume $run_id
```

Il resume crea una nuova run con `retry_of` e puo' ripetere tutta la fase
fallita. Non lanciarlo in ciclo. Per Docling mostrare il tempo trascorso: il
default corrente e' 300 s e l'hard maximum 600 s. Offrire attesa, ispezione di
`.worker_stdout.tmp`/`.worker_stderr.tmp` o un solo resume; non aumentare il
timeout automaticamente. Per un lock Windows transitorio attendere il rilascio
del worker, verificare `run status`, poi fare un unico retry.

## 6. Piani di evidenza AI

Scopo: separare estrazione tecnica da interpretazione di dominio e capire cosa
entra nel package.

```powershell
$technical = & $project_python -m dsl_mngr ai evidence plan $workspace --policy technical_extraction 2>&1
if ($LASTEXITCODE -ne 0) { throw 'piano tecnico fallito' }
$aisel_technical = [regex]::Match(($technical -join "`n"),'AISEL_\d{6}').Value
$domain = & $project_python -m dsl_mngr ai evidence plan $workspace --policy domain_interpretation 2>&1
if ($LASTEXITCODE -ne 0) { throw 'piano interpretativo fallito' }
$aisel_domain = [regex]::Match(($domain -join "`n"),'AISEL_\d{6}').Value
$tech_included = & $project_python -m dsl_mngr ai evidence list $workspace --plan $aisel_technical --outcome included 2>&1
$tech_included | ForEach-Object { $_ }
$tech_excluded = & $project_python -m dsl_mngr ai evidence list $workspace --plan $aisel_technical --outcome excluded 2>&1
$tech_excluded | ForEach-Object { $_ }
$technical_evidence_id = [regex]::Match(($tech_included -join "`n"),'(?:CHK|FRAG)_\d{6}').Value
if (-not $technical_evidence_id) { throw 'Nessuna evidenza inclusa da spiegare' }
& $project_python -m dsl_mngr ai evidence explain $workspace $technical_evidence_id --plan $aisel_technical
$excluded_evidence_id = [regex]::Match(($tech_excluded -join "`n"),'(?:CHK|FRAG)_\d{6}').Value
if (-not $excluded_evidence_id) { throw 'Nessuna evidenza esclusa da spiegare' }
& $project_python -m dsl_mngr ai evidence explain $workspace $excluded_evidence_id --plan $aisel_technical
$domain_included = & $project_python -m dsl_mngr ai evidence list $workspace --plan $aisel_domain --outcome included 2>&1
$domain_evidence_id = [regex]::Match(($domain_included -join "`n"),'(?:CHK|FRAG)_\d{6}').Value
& $project_python -m dsl_mngr ai evidence explain $workspace $domain_evidence_id --plan $aisel_domain
```

Atteso v 01: piano tecnico 11 evidenze incluse su 89; interpretativo 89 su 89.
`list` ed `explain` sono read-only. Creare il package soltanto dal piano
interpretativo appena letto:

```powershell
$package_output = & $project_python -m dsl_mngr ai package $workspace --selection-plan $aisel_domain 2>&1
if ($LASTEXITCODE -ne 0) { throw 'package fallito o piano stale' }
$aipkg = [regex]::Match(($package_output -join "`n"),'AIPKG_\d{6}').Value
$package_dir = Join-Path $workspace "ai\outbox\$aipkg"
Get-ChildItem -LiteralPath $package_dir -File | ForEach-Object {
  "`n===== $($_.Name) ====="; Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
}
```

Leggere integralmente istruzioni, schema, template, contenuto e manifest.
Un piano e' immutabile ma diventa stale se cambia lo stato rilevante delle
evidenze: in quel caso `ai package --selection-plan` termina con exit `4` e va
creato un nuovo piano. Una modifica solo descrittiva della policy non e' una
prova di staleness; non accettare silenziosamente un vero cambio di revisione.

## 7. Handoff AI autentico o replay controllato

Scopo: produrre JSONL ancorato solo a chunk/frammenti inclusi. Nel percorso
autentico, l'AI esterna deve assimilare soltanto il package e copiare
`evidence_text` letterale. Sono ammessi `fact`, `relation`, `mapping`,
`conflict`, `question`, con asserti explicit, observed, inferred e ambiguous.
`temporal_interval` non appartiene allo schema AI.

Salvare la risposta ricevuta in `ai/inbox` senza mutarne il contenuto; quindi:

```powershell
$response_path = (Resolve-Path (Read-Host 'Percorso JSONL della risposta')).Path
$inbox_path = Join-Path $workspace ("ai\inbox\${aipkg}_candidates.jsonl")
if (Test-Path -LiteralPath $inbox_path) { throw 'Inbox gia presente: non sovrascrivere' }
Copy-Item -LiteralPath $response_path -Destination $inbox_path
& $project_python -m dsl_mngr ai inbox scan $workspace
& $project_python -m dsl_mngr ai import $workspace --package $aipkg
```

Prima del replay controllato verificare che hash/package ed evidenze del JSONL
coincidano col package corrente. Se non coincidono, non adattare gli ID:
generare un nuovo handoff. Il file fornito e' una risposta congelata; package,
inbox, import, review e merge restano reali, la chiamata al modello no.

Atteso: l'import accetta 13 record nella sessione canonica pulita e li lascia
pending. Un candidato importato non e' una verita'. Risposta assente: mettere
la sessione in pausa e conservarne lo stato. JSONL invalido: usare report ed
exit code; correggere la risposta fuori dal workspace e rieseguire inbox scan,
mai inserire righe nel database.

## 8. Review umana e merge

Scopo: esercitare show, conferma, rifiuto, correzione, idempotenza e lineage.

```powershell
$pending_json = & $project_python -m dsl_mngr candidates review list $workspace
$pending = $pending_json | ConvertFrom-Json
$pending.candidates | Format-Table candidate_record_id,record_type,assertion_type,confidence

# Scegliere gli ID dalle righe realmente mostrate.
$candidate_id = Read-Host 'ID candidato da ispezionare'
& $project_python -m dsl_mngr candidates review show $workspace $candidate_id
$decision = Read-Host 'Azione: confirm, reject, correct oppure pending'
```

Esempi di azione, da eseguire solo dopo aver valorizzato `$candidate_id` dalla
lista reale:

```powershell
& $project_python -m dsl_mngr candidates review confirm $workspace $candidate_id --reason 'Evidenza letterale verificata' --actor-id human_orione --idempotency-key ("orione-confirm-" + $candidate_id + '-v1')
& $project_python -m dsl_mngr candidates review reject $workspace $candidate_id --reason 'Regola storica superata' --actor-id human_orione --idempotency-key ("orione-reject-" + $candidate_id + '-v1')
```

Per `correct`, costruire un JSON completo partendo dal payload mostrato,
ridurre l'asserto forte SLA a una formulazione sostenuta dall'evidenza e
passare gli ID di evidenza reali con `--evidence-ref`. Il parent deve diventare
`superseded` e il replacement `confirmed`. Ripetere la stessa richiesta con la
stessa idempotency key deve produrre replay, non una seconda decisione.

```powershell
$payload_path = (Resolve-Path (Read-Host 'JSON UTF-8 del payload corretto')).Path
$corrected_payload = Get-Content -LiteralPath $payload_path -Raw -Encoding UTF8
$evidence_refs = (Read-Host 'Evidence ID reali separati da virgola').Split(',').Trim()
$correct_args = @('-m','dsl_mngr','candidates','review','correct',$workspace,$candidate_id,'--reason','Asserto limitato al target P1','--payload',$corrected_payload,'--actor-id','human_orione','--idempotency-key',("orione-correct-" + $candidate_id + '-v1'))
foreach ($evidence_ref in $evidence_refs) { $correct_args += @('--evidence-ref',$evidence_ref) }
& $project_python @correct_args
```

Lasciare pending il contratto esterno ambiguo; confermare i due record checklist
indipendenti, rifiutare l'autoassegnazione storica e conservare l'orphan
intenzionale. `mapping`, `conflict` e `question` sono governati ma non tutti
diventano fatti/relazioni: gli skip sono attesi. Estrarre i `CBATCH_*` reali
dall'import/correzione e fonderli:

```powershell
$merge_args = @('-m','dsl_mngr','facts','merge-batch',$workspace)
foreach ($batch_id in $candidate_batches) { $merge_args += @('--batch',$batch_id) }
& $project_python @merge_args
& $project_python -m dsl_mngr facts reconcile $workspace
```

Se non vi sono candidati pending, non inventarne: verificare package, import e
filtri. Atteso: fatto checklist con almeno due supporti senza duplicazione;
parent corretto superseded; replacement confirmed; almeno un rifiuto.

## 9. Review e promozione della temporalita'

Scopo: distinguere validita' della fonte dalla validita' dell'asserto. Dalla
lista pending confermare gli `effective_from: 2026-03-01` concordanti nelle due
fonti, rifiutare `first_seen_at`, mtime/ctime e metadata OOXML incoerenti,
lasciare pending date conflittuali. Correggere le due evidenze HTML esplicite in
un intervallo sorgente chiuso 2023-01-01/2025-02-28. Gli intervalli della
`source_revision` non si propagano da soli.

Individuare con i comandi pubblici e gli output di merge due fatti nodo e la
relazione arco. Poi invocare il leaf pubblico con gli ID reali:

```powershell
$promotion_json = & $project_python -m dsl_mngr temporal propagate $workspace --source-revision-id $rev_id --target-subject-type fact --target-subject-id $fact_id --source-subject ("source_revision:" + $rev_id) --policy explicit_copy
if ($LASTEXITCODE -ne 0) { throw 'Promozione fallita: leggere il JSON' }
$promotion = $promotion_json | ConvertFrom-Json
$promotion.candidate_record_ids
```

Interfaccia completa:

```text
dsl-manager temporal propagate WORKSPACE --source-revision-id REV_ID --target-subject-type {fact,relation} --target-subject-id TARGET_ID --source-subject TYPE:ID [--source-subject TYPE:ID ...] --policy {explicit_copy,intersection,aggregation,conflict}
```

Ripetere `explicit_copy` verso due fatti e verso la relazione. Usare poi
`aggregation` su intervalli disgiunti verso un fatto distinto, oppure
`intersection` su vincoli indipendenti. L'output deve riportare policy, target,
sorgenti, ID dei candidati o conflict ID ed exit semantico. Mostrare ogni
candidato, confermarlo o rifiutarlo tramite review, quindi fondere i suoi batch.
Un intervallo semanticamente gia' materializzato viene riusato e puo' ricevere
un secondo supporto confermato: non duplicare l'intervallo e non cambiare
bersaglio per aggirare il riuso.

Per ottenere spell reali servono almeno due intervalli sul medesimo fatto e
sulla relazione: copiare sia lo storico chiuso sia il corrente aperto. Verificare
che gli intervalli della relazione siano contenuti nei bounds dei fatti di
dominio estremi. Il modello GEXF corrente collega la relazione a nodi entita',
mentre gli intervalli dei fatti sono su nodi fact: il validatore semantico
ufficiale resta autoritativo e questa differenza e' una limitazione pubblica.

## 10. DSL, diff e GEXF

```powershell
$v1 = & $project_python -m dsl_mngr dsl render $workspace --schema-version 1 --output-dir exports/orione_v1 2>&1
$dsl_v1 = [regex]::Match(($v1 -join "`n"),'DSL_\d{6}').Value
$v2a = & $project_python -m dsl_mngr dsl render $workspace --schema-version 2 --output-dir exports/orione_v2_a 2>&1
$dsl_v2a = [regex]::Match(($v2a -join "`n"),'DSL_\d{6}').Value
$v2b = & $project_python -m dsl_mngr dsl render $workspace --schema-version 2 --output-dir exports/orione_v2_b 2>&1
$dsl_v2b = [regex]::Match(($v2b -join "`n"),'DSL_\d{6}').Value
& $project_python -m dsl_mngr dsl diff $workspace --from $dsl_v1 --to $dsl_v2a --cross-schema
& $project_python -m dsl_mngr graph export $workspace --snapshot-id $dsl_v1
& $project_python -m dsl_mngr graph export $workspace --snapshot-id $dsl_v1 --strict-orphans
$strict_orphan_exit = $LASTEXITCODE
& $project_python -m dsl_mngr graph export $workspace --snapshot-id $dsl_v2a --dynamic --timeformat date --temporal-output-mode strict
```

Atteso: schema 2 con `intervals` non vuote; JSON/YAML/Markdown dei due render
v2 byte-identici; diff cross-schema exit `0`; statico exit `0` con un orphan;
`--strict-orphans` exit `2` intenzionale; dinamico exit `0`, XSD e validazione
semantica completati. Leggere il GEXF con XML namespace e mostrare almeno due
`<spell>` sul nodo fact e due sull'arco relation, con 2023-01-01/2025-02-28 e
2026-03-01/aperto. Zero spell non e' un successo.

## 11. Log e UI locale

```powershell
& $project_python -m dsl_mngr log table $workspace --format html --output (Join-Path $workspace 'exports\events.html')
& $project_python -m dsl_mngr log csv $workspace --output (Join-Path $workspace 'exports\events.csv')
```

Per la UI, scegliere una porta libera in loopback, avviare solo il comando
pubblico con `Start-Process -WindowStyle Hidden -PassThru`, conservare il PID e
chiuderlo in `finally`. Verificare GET 200 per `/`, `/runs`, `/runs/$run_id`,
`/logs`, `/rejected-candidates`, `/conflicts`, `/snapshots`, `/diff`; POST `/`
deve essere 405. Se la porta e' occupata sceglierne un'altra prima dell'avvio;
non terminare processi estranei.

```powershell
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start(); $port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port; $listener.Stop()
$ui_stdout = Join-Path $workspace 'exports\ui_stdout.log'
$ui_stderr = Join-Path $workspace 'exports\ui_stderr.log'
$ui_args = @('-m','dsl_mngr','ui','serve',('"' + $workspace + '"'),'--host','127.0.0.1','--port',[string]$port)
$ui_process = $null
try {
  $ui_process = Start-Process -FilePath $project_python -ArgumentList $ui_args -WindowStyle Hidden -PassThru -RedirectStandardOutput $ui_stdout -RedirectStandardError $ui_stderr
  $base_uri = "http://127.0.0.1:$port"
  foreach ($attempt in 1..40) {
    try { if ((Invoke-WebRequest "$base_uri/" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}
    Start-Sleep -Milliseconds 250
  }
  foreach ($route in @('/','/runs',"/runs/$run_id",'/logs','/rejected-candidates','/conflicts','/snapshots','/diff')) {
    $response = Invoke-WebRequest ($base_uri + $route) -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -ne 200) { throw "GET non valido: $route" }
  }
  try { $post_code = (Invoke-WebRequest "$base_uri/" -Method Post -UseBasicParsing).StatusCode }
  catch { $post_code = [int]$_.Exception.Response.StatusCode.value__ }
  if ($post_code -ne 405) { throw "POST inatteso: $post_code" }
}
finally {
  if ($null -ne $ui_process -and -not $ui_process.HasExited) {
    Stop-Process -Id $ui_process.Id -Force
    $ui_process.WaitForExit()
  }
}
```

## 12. Chiusura e diagnosi

Rieseguire `corpus scan`: tutte le 15 fonti devono essere `Unchanged` e gli hash
devono coincidere con `checksums.json`. Non promuovere mtime/ctime. Conservare
workspace temporaneo, report, HTML/CSV e diario. Non copiare nel progetto il
database o gli export della sessione.

Le fixture workbook controllate vanno provate in un workspace temporaneo
separato: il malformed deve fallire con exit pipeline `2`, worker security `3`
e `ooxml_security_violation`. Il contratto partial si prova invece sulla
revisione registrata di una fonte ammessa, senza iniettare worker o path:

```powershell
$partial_json = & $project_python -m dsl_mngr diagnostics normalization run $workspace --revision $rev_id --scenario 'controlled_partial_success/1'
$partial_exit = $LASTEXITCODE
$partial = $partial_json | ConvertFrom-Json
if ($partial_exit -ne 6 -or $partial.status -ne 'partial' -or -not $partial.controlled_simulation -or $partial.worker_exit_code -ne 6) {
  throw 'Contratto partial controllato non soddisfatto'
}
$partial.artifact_paths
```

Gli artefatti devono restare sotto
`artifacts/runs/<RUN_ID>/diagnostics/normalization/` e lo stato di produzione
(normalizzati, chunk, candidati, fatti e relazioni) non deve cambiare. Le
fixture controllate non sono fonti operative.
