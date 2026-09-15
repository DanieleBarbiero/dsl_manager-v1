# Diario tecnico — percorso manuale end-to-end DSL Manager

- Data avvio: 2026-09-14 (Europe/Rome)
- Repository: `dsl_manager-v1`
- Release dichiarata: `1.1.0`
- Interprete obbligatorio: `.venv\\Scripts\\python.exe`
- Area temporanea: `C:\\Users\\DBARBI~1\\AppData\\Local\\Temp\\dsl_manager_manual_e2e_20260914`
- Materiale di input: `source_material/`
- Workspace applicativo: da creare con la CLI in `workspace/`

## Regole della sessione

1. Non usare il corpus o le fixture Aurora come input del percorso.
2. Creare un corpus originale piccolo ma sufficiente a esercitare documenti, DDL, XML Form, codice DB, log, XLSX e XLSM.
3. Usare i comandi pubblici e gli ID stampati dall'applicazione.
4. Eseguire sia la derivazione deterministica sia l'handoff AI reale: leggere il package, formulare candidati come AI esterna e importarli.
5. Non correggere codice o infrastruttura. Al primo difetto di quel livello, fermare il percorso, conservare evidenze e chiedere autorizzazione.
6. Distinguere errori d'uso aggirabili, limiti documentati e difetti bloccanti.

## Stato iniziale del repository

Il worktree era già modificato prima dell'esecuzione. Le modifiche preesistenti includono documentazione, CLI/core, test temporali e file non tracciati della Slice 30. Nessuna di queste modifiche sarà alterata dal laboratorio.

## Diario cronologico

### 1. Inventario e lettura

- Letto `AGENTS.md` fornito nel contesto e verificato `.codex/config.toml`.
- Inventariati 287 file tracciati; `.wb` esclusa come da regole del repository.
- Letti integralmente `design_document_v_01.md`, `design_document_v_02.md`, `project_summary.md`, `manuale_utente_dsl_manager.md` e l'outline sintetico.
- La lettura delle slice, dei report, della documentazione tecnica, del codice e dei test prosegue prima dell'esecuzione.
- Nota ambientale non ancora classificata come difetto: `git ls-files` quota due nomi UTF-8 in output e `desktop.ini` risulta visibile nell'inventario ma non leggibile tramite un primo `Get-Item`; nessun impatto operativo osservato.
- Letti integralmente prompt e report delle Slice 01–30. Le Slice 01–29 costituiscono la storia richiesta; la Slice 30, già presente nel worktree, è necessaria perché modifica il percorso AI effettivamente disponibile.
- Vincoli operativi ricavati: la selezione AI è route-dependent e produce un piano immutabile; il package non invoca provider; l'output AI deve rientrare come candidate batch e passare da validation/review/merge. Excel usa manifest e frammenti OOXML come fonte strutturale primaria.
- Limiti runtime già documentati, non scoperti da questa esecuzione: budget globale nodi+archi GEXF mancante e `result_catalog_v1` non uniforme. Sono fuori dal percorso critico previsto; verranno distinti da eventuali nuovi difetti osservati durante l'uso.

### 2. Preflight dell'ambiente

- Interprete usato: `.venv\\Scripts\\python.exe`, versione `Python 3.12.10`.
- Eseguito `-m pip install -e ".[dev]"`: exit code 0, `dsl_mngr 1.1.0` installato in editable mode.
- Eseguito `-m pip check`: exit code 0, `No broken requirements found`.
- Baseline mirata eseguita su Slice 15, 20, 21 e 30: `30 passed in 89.40s`, exit code 0. Nessun blocco iniziale nel package/import AI, review/merge, derivazione o selezione evidence.

### 3. Corpus originale e workspace

- Creato il corpus originale “Orione Assistenza”: 9 fonti operative (Markdown, HTML, DOCX, DDL, Oracle Form XML, PL/SQL, log, XLSX e XLSM).
- XLSX generato con due fogli, uno hidden, tabella, named range, merge e formule con cached value; XLSM generato con `xl/vbaProject.bin` inerte. I package ZIP sono stati ispezionati prima dell'uso.
- Creato il workspace con `dsl-manager init`; creato il database con `dsl-manager db init`: 11 migrazioni applicate, nessuna saltata.
- Configurata una allowlist esplicita per la sola auto-review delle strutture tecniche conservative; relazioni Excel, temporalità e interpretazioni restano manuali.
- Le 9 copie nel workspace hanno SHA-256 identici agli originali temporanei.
- Errore operativo aggirato: il primo script di confronto hash ha mescolato path Windows 8.3 e path espansi e ha calcolato relativi con una sottostringa errata (`l\\...`). Nessun file o comando DSL Manager era coinvolto. Istruzione futura: su Windows non sottrarre lunghezze tra forme short/long; ricavare il relativo da un anchor stabile o usare una sola forma canonica end-to-end.

### 4. Scan e batch consolidato — BLOCCO CODICE

- Primo `corpus scan`: 9 aggiunti; secondo scan: 9 invariati. Entrambi exit code 0.
- Avviato una sola volta `batch consolidate <workspace> --reconcile`, run `RUN_000001`.
- Esito finale: batch failed, exit processo 1; payload catalogato con `exit_code: 2`, `reason: batch_parse_failed`, `retryable: true`.
- La fase parse ha completato 13 azioni su 14. Sono passati: DB code (1 procedura, 1 trigger, 2 statement, 4 frammenti), Markdown, DOCX, HTML, XML Form (1 form, 5 campi, 9 frammenti), log (4 eventi, 1 warning), XLSX e XLSM, inclusi normalize e chunk.
- Unico errore: `parse_ddl` su `CREATE INDEX IX_INTERVENTO_STATO ON INTERVENTO(STATO);`, riga 40, con `Malformed CREATE INDEX near line 40` e worker exit 5.
- Diagnosi read-only: `_parse_qualified_identifier()` consuma già gli spazi finali e restituisce il cursore sulla `O` di `ON`; `_parse_create_index_at()` applica poi `re.match(r"\\s+ON\\b", cleaned[position:])`. La regex richiede whitespace proprio nel punto in cui il whitespace è già stato consumato, quindi la sintassi SQL standard non può superare quel ramo.
- La documentazione Slice 12 dichiara supporto minimo a `CREATE INDEX`, il profilo generato ha `parse_indexes: true`, ma la ricerca dei test non trova fixture/test con una vera istruzione `CREATE INDEX`. Classificazione: difetto runtime del parser DDL, owner storico Slice 12, non errore del corpus.
- Workaround possibile ma **non applicato**: rimuovere l'indice dal DDL oppure impostare `parse_indexes: false`; entrambi eviterebbero il ramo difettoso ma rinuncerebbero proprio alla possibilità che il collaudo deve verificare.
- Come richiesto, il percorso è sospeso prima di derive/review/merge/AI/DSL/GEXF. Nessuna correzione al repository è stata eseguita.
- Artefatti del blocco: `workspace/artifacts/runs/RUN_000001/batch_report.json` e `batch_checkpoint.json`; run status `failed`, avvio `14:41:29+02:00`, fine `14:50:03+02:00`.

### 5. Correzione autorizzata del parser DDL

- Modificato `src/dsl_mngr/core/ddl_parser.py`: dopo `_parse_qualified_identifier()` il cursore è già su `ON`, quindi il matcher ora usa `ON\\b` invece di richiedere nuovamente whitespace.
- Aggiunto `test_parse_ddl_create_index_and_unique_index` in `tests/test_slice_12_parse_ddl.py`, con verifica di nomi, tabella, colonne e flag `unique`.
- Test mirato: `6 passed in 9.51s`, exit code 0.
- `git diff --check` sui due file: exit code 0; presenti soltanto warning LF→CRLF informativi.

### 6. Gate suite completa — SECONDO BLOCCO INFRASTRUTTURA/RUNTIME

- Suite completa avviata con `.venv\\Scripts\\python.exe -m pytest`: 194 test raccolti.
- Esito: `1 failed, 193 passed in 870.05s`, exit code 1.
- Unico fallimento: `tests/test_slice_23_excel_ingest.py::test_slice_23_real_xlsx_docling`.
- Traceback: `PermissionError [WinError 32]` in `src/dsl_mngr/core/worker_runner.py`, cleanup `path.unlink()` di `artifacts/runs/RUN_000001/.worker_stdout.tmp`; il file risultava ancora usato da un altro processo.
- La nuova regressione DDL e tutti gli altri 193 test sono passati. Il fallimento non è una regressione logica della correzione DDL, ma riproduce realmente la fragilità Windows/worker già documentata nei report delle Slice 23, 28 e 30.
- Come richiesto, nessun retry isolato, workaround o fix al worker runner è stato applicato e `RUN_000001` non è stata ripresa.
- Istruzione futura: il gate completo deve restare bloccante anche quando il lock è noto; non considerare verde una suite basandosi soltanto su un rerun isolato. Il cleanup dei file worker temporanei richiede una decisione esplicita su retry/backoff e ownership degli handle.

### 7. Ripresa autorizzata

- L'utente ha autorizzato una modifica circoscritta al cleanup dei file temporanei worker, la suite completa e la successiva ripresa del laboratorio dalla stessa run.
- Perimetro dichiarato: retry/backoff limitato per un `PermissionError` transitorio durante `unlink`, test di regressione mirato, nessuna modifica ai contratti dei worker o agli artifact pubblicati.

### 8. Correzione cleanup e nuovo gate bloccante

- Implementato `_unlink_worker_temp_file`: 10 tentativi su `PermissionError`, backoff da 0,05 s fino a 0,5 s, quindi propagazione dell'errore se il lock persiste. Usato sia prima dell'avvio sia nel `finally` del worker.
- Aggiunti due test: rilascio dopo due lock transitori e fallimento fail-closed dopo il budget di retry.
- Test mirati runner + DDL: `14 passed in 13.26s`, exit code 0.
- Rilanciato isolatamente `test_slice_23_real_xlsx_docling` per verificare il caso originario. Il `WinError 32` non si è ripresentato e i file `.worker_stdout.tmp`/`.worker_stderr.tmp` sono stati rimossi.
- È emerso però un blocco distinto: worker `normalize_docling` terminato dopo `120176 ms`, `termination_reason: timeout`, `Worker timed out after 120.0 seconds`, exit code 5; test `1 failed in 122.97s`.
- Peak memory osservata `4329472`, stdout/stderr vuoti, partial artifact scartati, retryable true. La causa non è memoria/output e non riguarda il fix DDL o il cleanup.
- Artefatto diagnostico pytest: `C:/Users/dbarbiero/AppData/Local/Temp/pytest-of-dbarbiero/pytest-289/test_slice_23_real_xlsx_doclin0/workspace/artifacts/runs/RUN_000001/process_report.json`.
- Classificazione: limite infrastrutturale/configurazione Docling già osservato storicamente, ma riprodotto nel gate corrente. Nessun aumento di `excel.worker_timeout_seconds`, retry ulteriore o nuova modifica applicata senza autorizzazione.
- La suite completa non è stata rilanciata dopo questo nuovo esito e il laboratorio resta sospeso; `RUN_000001` non è stata ripresa.
- `git diff --check` sui quattro file modificati: exit code 0, soli warning LF→CRLF.

### 9. Ripresa autorizzata per il timeout Docling

- L'utente ha autorizzato l'aumento del timeout predefinito Excel/Docling da 120 a 300 secondi, con aggiornamento dei contratti/test, suite completa e ripresa successiva del laboratorio.
- Richiesto inoltre un mini report separato, da produrre dopo le esecuzioni di verifica di questo step, sul problema Windows/Docling ricorrente e su possibili soluzioni future non implementate.

### 10. Correzione timeout, gate verde e mini report

- Portato `excel.worker_timeout_seconds` da 120 a 300 nel default applicativo e nel workspace temporaneo; hard maximum lasciato a 600.
- Allineati manuale utente, analisi tecnica e design v02. Aggiunto un assert di regressione che verifica il valore nel workspace generato.
- Reinstallazione editable con `.venv\\Scripts\\python.exe -m pip install -e ".[dev]` completata; dipendenze già soddisfatte.
- Test configurazione: `1 passed in 3.97s`.
- Test reale `.xlsx`/Docling: `1 passed in 183.85s`. Ha superato i 120 s storici e concluso regolarmente entro il nuovo default.
- Suite completa con Python 3.12.10 dell'ambiente `.venv`: `196 passed in 663.23s`, exit code 0.
- Il gate comprende le regressioni DDL, cleanup Windows e timeout, oltre ai flussi reali Docling/Excel e agli end-to-end esistenti.
- Creato `mini_report_docling_windows.md`: distingue lock tardivo e durata elevata, propone telemetria per fase e presenta come ipotesi future non implementate un worker/pool pre-riscaldato oppure una gestione dell'albero processi tramite Windows Job Object.
- Il blocco è risolto. Il laboratorio può riprendere dal checkpoint di `RUN_000001`, senza rigenerare corpus o workspace.

### 11. Ripresa batch e avvio del percorso AI

- Una svista operativa ha invocato `dsl-manager runs show`; il gruppo corretto è il singolare `run` e la CLI ha restituito correttamente exit code 2. Nessuna mutazione. Istruzione futura: copiare il leaf esatto `run status` dal catalogo comandi.
- `run status RUN_000001` ha confermato lo stato `failed` e l'artifact directory originale.
- `batch consolidate <workspace> --resume RUN_000001` ha completato con exit code 0 creando `RUN_000017`, `retry_of: RUN_000001`.
- Il resume è per fase: `parse` risulta a due tentativi e ha rieseguito tutte le 14 azioni, non soltanto il DDL precedentemente fallito. Le successive fasi hanno un tentativo ciascuna.
- Risultato deterministico: 88 candidati in 46 batch; 62 auto-confermati e materializzati; 49 fatti e 13 relazioni creati; 26 candidati temporali lasciati pending; reconcile senza elementi da chiudere.
- Creato piano tecnico `AISEL_000001`: 52 evidenze esaminate, 9 incluse, 43 escluse; 41 esclusioni dovute a copertura deterministica confermata.
- Creato piano dominio `AISEL_000002`: 7 evidenze esaminate e incluse, 3.401 caratteri. Verificati `list` ed `explain` su inclusioni ed esclusioni persistite.
- Creato package `AIPKG_000001` da `AISEL_000002`: 4 revisioni, 3 chunk, 4 frammenti, stato `waiting_for_ai_candidates`.
- Letti integralmente istruzioni, schema, template, content, manifest sorgenti/package e selection plan. Prodotto manualmente, come AI esterna, `ai/inbox/AIPKG_000001_candidates.jsonl`, usando soltanto i blocchi inclusi.
- Il JSONL contiene 11 candidati e tutti i cinque record type permessi: fact, relation, mapping, conflict e question; include due supporti indipendenti per la stessa regola di checklist e tre osservazioni runtime.
- `ai inbox scan`: file presente, package non stale. `ai import`: run `RUN_000059`, batch `CBATCH_000047`, 11 accettati, 0 respinti, nessun `allow-stale`.

### 12. Review AI — TERZO BLOCCO CODICE/RUNTIME

- `candidates review list --outcome pending` ha mostrato 37 leaf: 26 temporali e gli 11 AI appena importati.
- `candidates review show` funziona per i candidati con testo rappresentabile in CP1252, ma fallisce su `CREC_000094`, il mapping `WorkOrder ↔ INTERVENTO`.
- Traceback: `UnicodeEncodeError` in `src/dsl_mngr/cli/commands/candidates.py:153`, nel `print(canonical_json_artifact_v1(payload), end="")`; il carattere U+2194 non è codificabile dallo stdout corrente.
- Diagnosi ambientale: `.venv\\Scripts\\python.exe` espone `sys.stdout.encoding == "cp1252"` e `sys.flags.utf8_mode == 0`. Il package/inbox e il database sono UTF-8; l'import è completato e il problema riguarda soltanto la serializzazione CLI sul terminale Windows.
- L'errore non è confinato semanticamente al mapping: gli stessi `print(canonical_json_artifact_v1(...))` compaiono in più leaf di review e facts, quindi qualunque contenuto Unicode fuori CP1252 può riprodurlo.
- Gli ulteriori `show` sono partiti perché erano già accodati nello stesso ciclo PowerShell; non è stata eseguita alcuna decisione di review, correzione o merge.
- Workaround disponibile ma non applicato: avviare il processo con `PYTHONIOENCODING=utf-8` o UTF-8 mode. Possibile correzione circoscritta da concordare: configurare stdout/stderr UTF-8 una volta all'ingresso CLI e aggiungere una regressione subprocess con encoding iniziale CP1252 e un payload contenente U+2194.
- Come richiesto, il laboratorio si ferma qui in attesa di autorizzazione. `CBATCH_000047` resta integro e pending; hash SHA-256 dell'inbox: `9AA3D417A6D72C157EB0B832534A4545E78F6C55CF57EFCD0D82E7143EAE1467`.

### 13. Correzione autorizzata dell'output Unicode CLI

- L'utente ha autorizzato il fix, preferendo una sostituzione del solo carattere se il rischio fosse limitato a U+2194.
- La diagnosi mostra un rischio generale: stdout era CP1252 e ogni carattere Unicode non rappresentabile avrebbe causato lo stesso crash. Sostituire `↔` avrebbe inoltre alterato un'evidenza UTF-8 valida già inclusa, hashata e importata.
- `src/dsl_mngr/main.py` ora riconfigura stdout e stderr a UTF-8 strict all'ingresso comune usato sia dal console script sia da `python -m dsl_mngr`; i servizi core e i dati non sono modificati.
- Aggiunta una regressione subprocess che forza `PYTHONIOENCODING=cp1252`, importa un mapping con `WorkOrder ↔ INTERVENTO`, esegue `candidates review show` e decodifica l'output come UTF-8.
- Test mirato: `1 passed in 3.33s`.
- Verifica sul vero `CREC_000094`: exit code 0; l'evidence text restituito contiene esattamente `WorkOrder ↔ INTERVENTO`; stato ancora pending.
- Verifica finale anche tramite il vero console script `dsl-manager.exe`, forzando il processo a nascere con `PYTHONIOENCODING=cp1252`: exit code 0 e simbolo `↔` restituito integro.
- Suite completa con `.venv\\Scripts\\python.exe`, Python 3.12.10: `197 passed in 1193.61s`, exit code 0.
- Durante la suite il caso Excel reale è terminato prima dei 300 s ma con margine inferiore al rerun da 183,85 s. Il mini report Docling/Windows è stato aggiornato; nessun ulteriore aumento di timeout è stato applicato.
- Il blocco Unicode è risolto e la review può riprendere da `CBATCH_000047`.

### 14. Review e merge del risultato AI

- Ispezionati con `candidates review show` tutti i candidati rappresentativi e le due evidenze indipendenti della checklist.
- Confermati nove candidati originari: glossario, appartenenza intervento-asset, due fatti equivalenti sulla checklist, mapping proposto, domanda aperta, conflitto storico/corrente, assegnazione osservata e checklist mancante osservata.
- Corretto atomicamente `CREC_000093`: la relazione inferita `FORM_ACTION_ASSEGNA invokes PRC_ASSEGNA_TECNICO` era più forte dell'evidenza. Il parent è `superseded`; `CREC_000100`, batch `CBATCH_000048`, afferma invece l'esplicito `PRC_ASSEGNA_TECNICO updates_assignment_for INTERVENTO` ed è confirmed.
- Respinto `CREC_000099`: l'evento di chiusura era già rappresentato dalla derivazione deterministica del log e non aggiungeva semantica distinta.
- `facts merge-batch` su `CBATCH_000047` e `CBATCH_000048`: 2 completati, 0 falliti. Creati 3 fatti e 3 relazioni; un fatto esistente ha ricevuto un secondo supporto.
- Skip attesi nel batch originario: parent non-leaf, mapping/question/conflict non materializzabili e candidato rejected. Non sono errori di merge.
- Verifica finale: `FACT_000051`, `INTERVENTO.closure_checklist = SICUREZZA=OK;COLLAUDO=OK`, ha `support_count=2` da due revisioni documentali.

### 15. Review temporale

- Esaminati via comando pubblico tutti i 26 candidati temporali pending, riportando revisione, target, bounds, timezone, assessment ed evidence text.
- Confermati `CREC_000067` (`effective_from: 2026-01-15` del manuale corrente) e `CREC_000077` (pubblicazione `2023-01-10` della procedura storica).
- Respinti `CREC_000070` (metadata DOCX 2013 incoerente) e `CREC_000082`/`CREC_000086` (timestamp ZIP epoch 1980). Le evidenze filesystem/package e i valori conflittuali rimanenti restano pending.
- Merge dei batch `CBATCH_000025` e `CBATCH_000035`: 2 completati, 0 falliti; creati `TINT_000001` e `TINT_000002`, entrambi target `source_revision` e timeformat `date`.
- Limite documentato verificato: l'intervallo di una sorgente non si propaga automaticamente a fatti o relazioni. Di conseguenza DSL v2 e GEXF dinamico non contengono spell per questi due intervalli.
- Non è stato usato un accesso interno al database per fabbricare un target fact/relation. Per un futuro laboratorio con spell reali serve una regola/versione o un percorso pubblico che produca evidenza temporale direttamente per quel soggetto.

### 16. DSL, diff e grafi

- Render v1: `DSL_000001`, hash `0dabe1ee...e335259`, 52 fatti, 16 relazioni, 1 conflitto.
- Render v2: `DSL_000002`, hash `f7a84f75...b365b`, stessi conteggi; intervalli vuoti sulle entità per la granularità descritta sopra.
- Diff cross-schema: `RUN_000084`, un cambiamento strutturale/governance, nessuna aggiunta o rimozione semantica.
- GEXF statico `DSL_000001`: 65 nodi, 88 archi, 3 orphan, 3 warning; export completato e validato offline dal percorso applicativo.
- GEXF dinamico `DSL_000002`, `timeformat=date`, modalità temporale strict: 65 nodi, 88 archi, nessuno spell, export completato.
- `--strict-orphans` ha restituito il fail-closed documentato, exit code 2, per `tec-9`; il normale export aggiunge gli orphan `prc_audit_intervento`, `intervento.sysdate` e `tec-9` con warning.
- Render ripetuti: `DSL_000003` byte-identico a v1 e `DSL_000004` byte-identico a v2 in JSON/YAML/Markdown. Diff `DSL_000002`→`DSL_000004`: 0 cambiamenti.

### 17. Log viewer e UI locale

- Esportati `app_log_table.html` (33.259 byte) e `app_log.csv` (9.507 byte) tramite i leaf pubblici; entrambi exit code 0.
- Primo controllo UI: richiesta errata a `/candidates`, risposta 404 corretta. Secondo controllo: inferita erroneamente `/rejected` dall'etichetta di navigazione, altra risposta 404 corretta. I processi sono stati sempre arrestati e non hanno scritto stderr.
- Istruzione futura: non derivare gli URL dalle etichette; usare il router/manuale. La rotta corretta è `/rejected-candidates`.
- Controllo finale su porta effimera `127.0.0.1`: dashboard, runs, rejected-candidates, snapshots, conflicts, logs e diff hanno risposto 200 con i contenuti attesi. `POST /` ha risposto 405. Processo hidden arrestato, stderr 0 byte.

### 18. Audit finale

- Scan conclusivo: 0 added, 0 modified, 0 deleted, 9 unchanged.
- Hash SHA-256: 9/9 copie nel corpus coincidono con gli originali in `source_material`.
- Conteggi read-only principali: 9 sources, 9 revisions, 5 chunks, 54 fragments, 2 workbook manifests, 48 candidate batches, 100 candidate records, 79 review decisions, 52 effective facts, 16 effective relations, 2 temporal intervals, 2 AI selection plans, 2 AI packages, 4 DSL snapshots, 2 graph exports e 91 runs.
- L'ipotesi che review/merge rendessero stale `AISEL_000002` era errata: la coverage della selezione considera soltanto batch `deterministic_derivation`, evitando l'auto-invalidazione causata dall'output dello stesso handoff. Il riuso ha correttamente creato `AIPKG_000002`.
- Audit script read-only: `workspace_audit.py`. L'inbox originale conserva SHA-256 `9aa3d417a6d72c157eb0b832534a4545e78f6c55cf57efcd0d82e7143eae1467`.
- `git diff --check`: nessun errore; solo warning informativi LF→CRLF. Le modifiche preesistenti Slice 30 sono rimaste nel worktree e non sono state rimosse.
- Gate finale del repository: `197 passed in 1193.61s` con `.venv\\Scripts\\python.exe` / Python 3.12.10.

### 19. Chiusura

- Percorso deterministico e percorso AI completati dall'inizio alla fine sul corpus originale Orione Assistenza.
- Tutti i parser richiesti sono stati esercitati con contenuti reali: DDL, DB code, Markdown, DOCX, HTML, XML Form, log, XLSX e XLSM.
- Artefatti, errori, workaround, limiti e proposte sono conservati nell'area temporanea. La traccia depurata per il futuro laboratorio è `traccia_tecnica_laboratorio_futuro.md`.
