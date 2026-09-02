Implementa solo la Slice 13 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/template/template_slice_report.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`
- `.kb/projects/slicing/slice_06/dsl_manager_slice_06_report.md`
- `.kb/projects/slicing/slice_07/dsl_manager_slice_07_report.md`
- `.kb/projects/slicing/slice_08/dsl_manager_slice_08_report.md`
- `.kb/projects/slicing/slice_09/dsl_manager_slice_09_report.md`
- `.kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md`
- `.kb/projects/slicing/slice_11/dsl_manager_slice_11_report.md`
- `.kb/projects/slicing/slice_12/dsl_manager_slice_12_report.md`
- l'attuale codice in `src/dsl_mngr`
- l'attuale suite in `tests`

Task:
Implementare la minima slice verticale funzionante per parsare XML form e registrare evidenza strutturale deterministica nel registry.

La Slice 13 deve introdurre un parser XML form base, isolato dietro worker, capace di leggere sorgenti XML gia' registrate dal corpus scan, estrarre form, field, button, required fields, table/column references e relazioni tecniche "form edits table". Deve produrre artifact riproducibili e persistere record in `source_fragments`.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs`, `run_worker` e artifact deterministici.
- Slice 5 ha introdotto `chunks`, `source_fragments`, `candidate_batches`, `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto merge deterministico di `candidate_fact` e `candidate_relation`.
- Slice 7 ha introdotto renderer DSL JSON/YAML/Markdown e `dsl_snapshots`.
- Slice 8 ha introdotto `dsl diff` tracciabile.
- Slice 9 ha stabilizzato il golden pipeline test dell'MVP tecnico.
- Slice 10 ha introdotto normalizzazione Docling no-images dietro adapter/worker.
- Slice 11 ha introdotto chunking stabile ed evidence lookup su `chunks`.
- Slice 12 ha introdotto parser DDL, `fragment_registry`, worker `parse_ddl`, artifact `fragments.jsonl`/`ddl_report.json` ed evidence lookup su `fragment_id`.
- `candidate_validation.validate_candidate_payload` supporta gia' `fragment_id`.
- `fragment_registry` esiste gia', ma e' attualmente DDL-specific: la Slice 13 deve estenderlo o affiancarlo in modo compatibile, senza rompere la Slice 12.

Decisione di scope:
- Per questa slice, "`facts` strutturali" significa: oggetti XML form normalizzati prodotti dal parser e rappresentati in artifact/report e in `source_fragments.metadata_json`.
- Non inserire direttamente record nelle tabelle `facts` o `relations`.
- Non creare candidate records sintetici dentro il parser.
- La relazione "form edits table" deve essere esposta in modo deterministico nel report e nei metadata dei frammenti; il test puo' poi dimostrare il percorso corretto via `candidate_relation` con `fragment_id`, `candidates validate` e, se piccolo, `facts merge`.
- I mapping tecnici field -> table.column devono vivere nei metadata dei frammenti e nel report XML, non in una nuova tabella.
- Non aggiungere una migration per una tabella `mappings`: lo schema attuale non la include e il merge corrente salta `candidate_mapping`.
- Se ritieni indispensabile una nuova migration, deve essere append-only, piccola, motivata nel report e non deve modificare i contratti pubblici di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`.
- Il deliverable primario e accettabile della slice e': parser XML form deterministico + `source_fragments` idempotenti + artifact + test su form/fields/buttons/required/table-column references/relation edits via evidence.

Scope:
- aggiungere un core piccolo e testabile per il parsing XML form, per esempio:

```text
src/dsl_mngr/core/xml_form_parser.py
```

- estendere `src/dsl_mngr/core/fragment_registry.py` in modo minimale, oppure aggiungere un wrapper dedicato, per persistere anche frammenti XML:

```text
xml_form
xml_field
xml_button
```

- mantenere pienamente compatibile il comportamento DDL della Slice 12;
- aggiungere un worker reale:

```text
src/dsl_mngr/workers/parse_xml_form.py
```

- integrare un comando CLI nello stile `argparse` esistente:

```powershell
dsl-manager corpus parse-xml-form <workspace> --revision REV_000001
```

- mantenere compatibilita' con:

```powershell
python -m dsl_mngr corpus parse-xml-form <workspace> --revision REV_000001
```

- aggiungere un profilo default nel workspace inizializzato:

```text
configs/workers/xml_form.default.yaml
```

- aggiungere `parse_xml_form` ai run type ammessi;
- usare `worker_runner.run_worker` per invocare il worker e registrare `worker_runs`;
- creare run di tipo `parse_xml_form`;
- produrre output sotto:

```text
fragments/<source_id>/<source_revision_id>/fragments.jsonl
fragments/<source_id>/<source_revision_id>/xml_form_report.json
```

- persistere i frammenti prodotti nella tabella `source_fragments`;
- se la source ha `source_type = "unknown"`, puoi aggiornarla a:
  - `source_type = "xml_form"`;
  - `source_subtype = "form"`;
  - `authority_level = "technical_structure"`;
- non sovrascrivere classificazioni gia' esplicite e diverse senza una ragione testata.

Profilo default minimo consigliato:

```yaml
worker:
  name: parse_xml_form
  version: 1.0
xml_form:
  parser: elementtree
  require_root_form: true
  parse_fields: true
  parse_buttons: true
  parse_required_fields: true
  parse_table_column_references: true
  infer_edit_relations: true
  strict_options_fail_on_unsupported_option: true
  malformed_xml_policy: fail
  output_fragments_jsonl: true
```

Se il parser YAML minimale non supporta strutture oltre un livello, mantieni questa forma flat a sezioni semplici. Non fare un refactor generale della configurazione.

Parsing minimo richiesto:
- XML UTF-8 con newline normalizzati a `\n`;
- root `<form ...>` quando `require_root_form = true`;
- attributi form:
  - `name` obbligatorio;
  - `title` opzionale;
- elementi `<field .../>` o `<field ...></field>`, anche se annidati in contenitori semplici;
- attributi field:
  - `name` obbligatorio;
  - `label` opzionale;
  - `table` opzionale;
  - `column` opzionale;
  - `required` opzionale, interpretando almeno `true`, `false`, `1`, `0`, `yes`, `no`;
- elementi `<button .../>` o `<button ...></button>`;
- attributi button:
  - `name` obbligatorio;
  - `label` opzionale;
- inferenza minima di action kind dei button:
  - `save` per `SAVE`, `SALVA` o label che contiene `salva`;
  - `confirm` per `CONFIRM`, `CONFERMA` o label che contiene `conferma`;
  - `delete` per `DELETE`, `ELIMINA` o label che contiene `elimina`;
  - `cancel` per `CANCEL`, `ANNULLA` o label che contiene `annulla`;
  - `unknown` altrimenti;
- table/column references da ogni field con entrambi gli attributi `table` e `column`;
- edit `relations` inferite: ogni form edita ogni tabella distinta referenziata dai suoi field.

Implementazione parsing:
- usa solo standard library, preferibilmente `xml.etree.ElementTree` per la struttura XML;
- non aggiungere dipendenze runtime;
- non usare parser XML esterni;
- non fare chiamate di rete;
- per `line_start`, `line_end`, `char_start`, `char_end`, calcola offsets ragionevoli sul testo XML normalizzato con `\n`;
- per i fixture minimi e' accettabile trovare lo span di form/field/button tramite scanning testuale deterministico del sorgente, purche' il parsing semantico resti XML-aware;
- non basare il parsing semantico solo su regex fragili.

Fixture XML minima da coprire nei test:

```xml
<form name="FRM_CLIENTE" title="Cliente">
  <field name="CODCLI" label="Codice cliente" table="ANCLI" column="CODCLI" required="true"/>
  <field name="RAGSOC" label="Ragione sociale" table="ANCLI" column="RAGSOC" required="true"/>
  <field name="PIVA" label="Partita IVA" table="ANCLI" column="PIVA"/>
  <button name="SAVE" label="Salva"/>
</form>
```

Seconda fixture consigliata:

```xml
<form name="FRM_ORDINE" title="Ordine cliente">
  <field name="IDORD" label="Numero ordine" table="ORDTES" column="IDORD" required="true"/>
  <field name="CODCLI" label="Cliente" table="ORDTES" column="CODCLI" required="true"/>
  <field name="STATO" label="Stato" table="ORDTES" column="STATO" required="true"/>
  <button name="CONFIRM" label="Conferma ordine"/>
</form>
```

Expected behavior:
- il comando verifica che workspace e database siano inizializzati e migrati;
- il comando verifica che `source_revision_id` esista;
- la revision deve appartenere a una `source` esistente;
- il comando legge il file sorgente da `source_revisions.file_path`;
- il path sorgente deve essere relativo al workspace, senza path traversal;
- il contenuto letto deve avere SHA-256 coerente con `source_revisions.content_hash`; se non coincide, fallire con errore leggibile che inviti a rieseguire `corpus scan`;
- il comando carica e valida il profilo `xml_form.default` o quello indicato da `--profile`;
- il comando crea una run `parse_xml_form`;
- il comando invoca `parse_xml_form` via `run_worker`;
- il worker non scrive direttamente nel database principale;
- il worker produce oggetti e frammenti in ordine stabile;
- al successo, il sistema scrive:
  - `fragments.jsonl`;
  - `xml_form_report.json`;
- al successo, `worker_runs.status == "completed"`;
- al successo, `runs.status == "completed"`;
- al successo, i frammenti sono persistiti in `source_fragments` con `status = "active"`;
- rieseguire il parsing della stessa revision con stesso input/config non deve creare duplicati attivi;
- rieseguire il parsing della stessa revision deve riusare gli stessi `fragment_id` per le stesse sequence quando possibile;
- eventuali frammenti attivi in eccesso per la stessa revision devono essere marcati `stale`;
- i path salvati in output, report, artifact e database devono essere relativi al workspace e usare `/`;
- i log non devono contenere contenuti lunghi dell'XML.

Output CLI minimo al successo:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Forms: 1
Fields: 3
Required fields: 2
Buttons: 1
Table references: 1
Edit relations: 1
Fragments: 5
Fragments hash: <sha256>
Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl
Report: fragments/SRC_000001/REV_000001/xml_form_report.json
```

Contratto worker:
- il worker deve accettare il contratto gia' usato da `run_worker`:

```powershell
python <worker_path> --input artifacts\runs\RUN_000001\input.json --output artifacts\runs\RUN_000001\output.json
```

- il worker deve produrre `output.json` coerente con `run_worker`, includendo almeno:
  - `run_id`;
  - `worker_name`;
  - `worker_version`;
  - `status`;
  - `exit_code`;
  - `source_id`;
  - `source_revision_id`;
  - `source_hash`;
  - `input_path`;
  - `fragments_jsonl_path`;
  - `xml_form_report_path`;
  - `fragment_count`;
  - `fragments_hash`;
  - `form_count`;
  - `field_count`;
  - `required_field_count`;
  - `button_count`;
  - `table_reference_count`;
  - `edit_relation_count`;
  - `profile`;
  - `parser`;
  - `xml_form_objects`;
  - `edit_relations`;
  - `fragments`;
- `fragments` puo' contenere record senza `fragment_id` tecnico solo se il core applicativo assegna o riusa gli ID prima di scrivere il `fragments.jsonl` canonico finale;
- non lasciare nel `fragments.jsonl` finale ID provvisori.

Formato `fragments.jsonl` canonico:

Ogni riga deve essere JSON valido e deterministico. Esempio:

```json
{"char_end":337,"char_start":0,"fragment_id":"FRAG_000001","fragment_type":"xml_form","line_end":6,"line_start":1,"metadata":{"edit_relations":[{"relation_type":"edits","source_form":"FRM_CLIENTE","target_table":"ANCLI"}],"field_count":3,"form_name":"FRM_CLIENTE","object_type":"form","parser":"parse_xml_form","parser_version":"1.0","source_hash":"<sha256>","table_references":["ANCLI"],"title":"Cliente"},"path_or_selector":"/form[@name='FRM_CLIENTE']","sequence":1,"source_revision_id":"REV_000001","status":"active","text":"<form name=\"FRM_CLIENTE\" title=\"Cliente\">...","text_hash":"<sha256>"}
```

Regole frammenti:
- `sequence` parte da 1 per ogni `source_revision_id`;
- `fragment_id` usa il formato `FRAG_000001`, riusando il meccanismo esistente quando possibile;
- `fragment_type` deve essere almeno:
  - `xml_form` per il form completo;
  - `xml_field` per ogni field;
  - `xml_button` per ogni button;
- `text` deve essere non vuoto;
- `text` deve usare newline `\n`;
- `text_hash` e' SHA-256 del `text` UTF-8;
- `fragments_hash` e' SHA-256 del contenuto canonico di `fragments.jsonl`;
- `metadata_json` nel database deve essere JSON canonico, con chiavi ordinate;
- `metadata_json` deve includere almeno:
  - `parser`;
  - `parser_version`;
  - `source_hash`;
  - `object_type`;
  - `form_name`;
  - `title`, quando applicabile;
  - `field_name`, quando applicabile;
  - `button_name`, quando applicabile;
  - `label`, quando applicabile;
  - `required`, quando applicabile;
  - `table_name`, quando applicabile;
  - `column_name`, quando applicabile;
  - `mapping_type`, quando applicabile, per esempio `form_field_to_column`;
  - `action_kind`, quando applicabile;
  - `table_references`, per i form;
  - `edit_relations`, per i form;
- `line_start` e `line_end` sono 1-based;
- `char_start` e `char_end` sono offset sul XML normalizzato con newline `\n`;
- `path_or_selector` deve essere stabile, per esempio:
  - `/form[@name='FRM_CLIENTE']`;
  - `/form[@name='FRM_CLIENTE']/field[@name='CODCLI']`;
  - `/form[@name='FRM_CLIENTE']/button[@name='SAVE']`.

Persistenza DB:
- usare la tabella `source_fragments` gia' esistente;
- non modificare migrazioni gia' applicate;
- se serve una modifica schema, aggiungere una nuova migration append-only e motivarla nel report;
- per questa slice dovrebbe bastare lo schema attuale;
- estendere `fragment_registry` senza rompere le validazioni DDL:
  - mantenere supporto a `ddl_table`, `ddl_column`, `ddl_constraint`;
  - aggiungere supporto a `xml_form`, `xml_field`, `xml_button`;
  - accettare `metadata["parser"] == "parse_ddl"` per DDL;
  - accettare `metadata["parser"] == "parse_xml_form"` per XML form;
  - mantenere JSON canonico e idempotenza;
  - mantenere `load_fragment_id_seed`;
- se generalizzi `persist_worker_fragments`, conserva il contratto usato da `parse_ddl`;
- se aggiungi una funzione dedicata, per esempio `persist_worker_xml_form_fragments`, riusa helper comuni dove sensato e mantieni il codice piccolo;
- inserire o aggiornare i campi:
  - `fragment_id`;
  - `source_revision_id`;
  - `fragment_type`;
  - `sequence`;
  - `path_or_selector`;
  - `line_start`;
  - `line_end`;
  - `char_start`;
  - `char_end`;
  - `text`;
  - `text_hash`;
  - `metadata_json`;
  - `status`;
  - `created_at`;
- non cancellare frammenti storici;
- per idempotenza:
  - se esiste gia' un fragment per stessa revision e stessa sequence, riusa il suo `fragment_id`;
  - aggiorna testo/metadati se sono cambiati;
  - marca `active` i fragment prodotti dalla run corrente;
  - marca `stale` eventuali fragment attivi della stessa revision con sequence non piu' prodotta;
  - non creare una nuova serie di fragment attivi identica a ogni rerun.

Relation edits ed evidence lookup:
- il report XML deve includere almeno una lista `edit_relations`, per esempio:

```json
[
  {
    "source_form": "FRM_CLIENTE",
    "relation_type": "edits",
    "target_table": "ANCLI",
    "field_names": ["CODCLI", "RAGSOC", "PIVA"]
  }
]
```

- aggiungi un test che dimostri che un candidato puo' essere validato usando un `fragment_id` prodotto dal parser XML form;
- il candidato puo' essere un `candidate_relation` con:
  - `source_entity = "FRM_CLIENTE"`;
  - `relation_type = "edits"`;
  - `target_entity = "ANCLI"`;
  - `fragment_id` del fragment `xml_form` o di un field fragment coerente;
  - `chunk_id` assente;
  - `evidence_text` contenuto nel `source_fragments.text`;
- se il test resta piccolo, esegui anche `facts merge --batch CBATCH_000001` e verifica che la relazione `FRM_CLIENTE -[edits]-> ANCLI` sia stata inserita nella tabella `relations`;
- non far creare al parser record in `candidate_records`, `facts` o `relations`.

Gestione errori:
- se `source_revision_id` non esiste, errore leggibile;
- se la revision non appartiene a una source esistente, errore leggibile;
- se il file sorgente manca, errore leggibile;
- se il file sorgente ha hash diverso da `source_revisions.content_hash`, errore leggibile;
- se il profilo contiene un'opzione non supportata e `strict_options_fail_on_unsupported_option` e' true:
  - il worker deve fallire con exit code `4`;
  - `worker_runs.exit_code` deve essere `4`;
  - `worker_runs.status` deve essere `failed`;
  - `runs.status` deve essere `failed`;
  - `process_report.json` o `log.jsonl` devono includere `unsupported_xml_form_option` e la chiave problematica;
  - non devono essere creati frammenti attivi nel database;
- se l'XML e' malformato e `malformed_xml_policy = "fail"`:
  - fallire con errore leggibile;
  - non applicare mutazioni parziali al database;
  - registrare run/worker failed;
- se mancano attributi obbligatori (`form.name`, `field.name`, `button.name`):
  - fallire con errore leggibile o registrare warning solo se scegli una policy esplicita e testata;
  - per questa slice e' preferibile fallire.

Artifact:
- `artifacts/runs/<run_id>/input.json` deve includere almeno:
  - `source_id`;
  - `source_revision_id`;
  - `source_hash`;
  - `input_path`;
  - `output_dir`;
  - `profile`;
  - `xml_form_options`;
  - `fragment_id_by_sequence`, se usato;
  - `next_fragment_number`, se usato;
- `artifacts/runs/<run_id>/output.json` deve includere almeno il payload del worker/core;
- `artifacts/runs/<run_id>/process_report.json` deve avere:
  - `run_type = "parse_xml_form"`;
  - `status = "completed"` al successo;
  - una voce worker `parse_xml_form`;
  - `artifact_dir` relativo;
  - `config_hash`;
- `resolved_config.yaml`, `config_hash.txt` e `log.jsonl` devono restare coerenti con Slice 4.

Test minimi richiesti:
- `test_parse_xml_form`;
- `test_form_edits_table_relation`.

Aggiungi preferibilmente anche:
- `test_parse_xml_form_idempotent_rerun`;
- `test_parse_xml_form_unsupported_option_fails_without_active_fragments`.

I test devono verificare almeno:
- un workspace temporaneo viene inizializzato con `tmp_path`;
- il database viene inizializzato/migrato;
- `configs/workers/xml_form.default.yaml` esiste o il profilo default e' disponibile in modo equivalente;
- una o piu' fixture XML vengono copiate in `corpus/active`;
- `corpus scan` registra le source/revision;
- `corpus parse-xml-form <workspace> --revision REV_000001` completa con exit code 0;
- il comando funziona anche via `python -m dsl_mngr`;
- `fragments/<source_id>/<source_revision_id>/fragments.jsonl` e `xml_form_report.json` vengono creati;
- `source_fragments` contiene record `xml_form`, `xml_field`, `xml_button`;
- il form `FRM_CLIENTE` e' estratto;
- i field `CODCLI`, `RAGSOC`, `PIVA` sono estratti;
- `CODCLI` e `RAGSOC` sono required;
- `PIVA` non e' required quando l'attributo manca;
- i mapping tecnici `ANCLI.CODCLI`, `ANCLI.RAGSOC`, `ANCLI.PIVA` sono presenti nei metadata;
- il button `SAVE` e' estratto con `action_kind = "save"`;
- la relazione tecnica `FRM_CLIENTE edits ANCLI` e' presente nel report o nei metadata del form;
- ogni `text_hash` coincide con SHA-256 del `text`;
- `fragments_hash` resta stabile su rerun con stesso input/config;
- rerun della stessa revision non crea duplicati attivi;
- `runs` contiene run `parse_xml_form` completate;
- `worker_runs` contiene worker `parse_xml_form` completati;
- `process_report.json` contiene path relativi e nessun `\`;
- evidence lookup con `fragment_id` accetta il candidato fixture;
- se esegui anche merge, `facts merge` crea la relazione `edits` attesa;
- nessuna regressione sulle slice 1-12.

Fixture consigliata:
- crea fixture XML dedicate, per esempio sotto:

```text
tests/fixtures/xml_forms/
```

- non aggiungere XML a `tests/fixtures/corpus_initial/` salvo aggiornare consapevolmente i golden test della Slice 9;
- usare file piccoli e locali;
- non usare rete nei test;
- non usare AI reale;
- non dipendere da Docling;
- non introdurre parser XML esterni;
- evitare assert fragili sull'intero report; verificare invece hash, path, conteggi, oggetti e metadata essenziali.

Constraints:
- non implementare parser SQL code, procedure, trigger o log;
- non implementare AI package handoff;
- non implementare batch orchestration;
- non implementare export GEXF;
- non implementare UI, web/API/auth o integrazioni esterne;
- non aggiungere ORM;
- non aggiungere dipendenze runtime per il parser XML;
- non modificare il contratto pubblico di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`;
- non salvare path assoluti negli artifact o nel database;
- non fare chiamate di rete durante parsing o test;
- non usare import da `src`;
- usare import assoluti da `dsl_mngr`;
- mantenere separati CLI, worker, core parser, persistence e test;
- mantenere l'implementazione piccola, leggibile e deterministica;
- i test devono usare `tmp_path`.

Done when:
- Slice 13 e' implementata end-to-end nello scope richiesto;
- `corpus parse-xml-form` produce artifact XML stabili;
- `fragments.jsonl` e `xml_form_report.json` vengono prodotti;
- la tabella `source_fragments` viene popolata in modo idempotente con `xml_form`, `xml_field`, `xml_button`;
- il parser estrae form, fields, required fields, buttons e table/column references minime;
- la relazione tecnica "form edits table" e' esposta nei report/metadata e dimostrata via evidence;
- evidence lookup funziona con `fragment_id`;
- i test nuovi sono significativi;
- tutta la suite passa;
- non e' stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato;
6. esegui una breve autoverifica finale contro scope, constraints e done criteria.

Report finale:

```text
salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_13/dsl_manager_slice_13_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
```
