# Traccia tecnica pulita per un futuro laboratorio DSL Manager

Questa traccia deriva dal percorso end-to-end “Orione Assistenza”. Non dipende
dal corpus Aurora e usa soltanto comandi pubblici. Gli ID mostrati sono
segnaposto: in ogni passaggio si devono riutilizzare quelli realmente stampati.

## 1. Preparazione

1. Leggere design, manuale, analisi tecnica, contratti manifest e prompt/report
   delle slice disponibili.
2. Su Windows leggere `PROJECT_PYTHON` da `.codex/config.toml` e usare sempre
   quell'interprete.
3. Installare in editable mode e fare un gate mirato prima del laboratorio.
4. Creare area sorgenti e workspace in una directory temporanea distinta dal
   repository.

Il corpus minimo consigliato contiene DDL con indici e foreign key, codice DB,
Markdown, DOCX, HTML, XML Form, log, XLSX strutturale e XLSM con macro inerte.
Per Excel includere almeno più fogli, hidden sheet, tabella, named range, merge,
formula e cached value. Conservare gli SHA-256 degli originali.

## 2. Workspace e percorso deterministico

```powershell
dsl-manager init <workspace>
dsl-manager db init <workspace>
dsl-manager corpus scan <workspace>
dsl-manager corpus scan <workspace>
dsl-manager batch consolidate <workspace> --reconcile
```

Il secondo scan deve risultare invariato. Configurare una allowlist di
auto-review conservativa prima del batch. I candidati interpretativi e temporali
devono restare pending.

Se una run fallisce con checkpoint:

```powershell
dsl-manager run status <workspace> <RUN_ID>
dsl-manager batch consolidate <workspace> --resume <RUN_ID>
```

Il resume crea una nuova run `retry_of` e può ripetere l'intera fase fallita,
non soltanto la singola azione. Prevedere quindi il costo dei worker Docling.

## 3. Selezione e handoff AI reale

Creare almeno un piano tecnico e uno interpretativo:

```powershell
dsl-manager ai evidence plan <workspace> --policy technical_extraction --revision <REV> ...
dsl-manager ai evidence list <workspace> --plan <AISEL> --outcome included
dsl-manager ai evidence explain <workspace> <EVIDENCE_ID> --plan <AISEL>
dsl-manager ai evidence plan <workspace> --policy domain_interpretation --revision <REV> ...
dsl-manager ai package <workspace> --selection-plan <AISEL_DOMAIN>
```

Leggere integralmente `instructions.md`, `candidate_schema.json`,
`output_template.jsonl`, `content.md`, `source_manifest.json`,
`selection_plan.json` e `package_manifest.json`.

L'AI esterna deve:

- usare soltanto i blocchi inclusi;
- copiare esattamente revision/chunk/fragment ID;
- usare un `evidence_text` letteralmente contenuto nell'evidenza;
- distinguere explicit, observed, inferred e ambiguous;
- emettere esclusivamente JSONL nell'inbox atteso.

```powershell
dsl-manager ai inbox scan <workspace>
dsl-manager ai import <workspace> --package <AIPKG>
```

Un set utile esercita fact, relation, mapping, conflict e question. Inserire due
fonti indipendenti per la stessa identità di fatto per verificare il supporto
multiplo.

## 4. Review e merge

```powershell
dsl-manager candidates review list <workspace> --outcome pending
dsl-manager candidates review show <workspace> <CREC>
dsl-manager candidates review confirm <workspace> <CREC> --reason <TESTO> --idempotency-key <KEY>
dsl-manager candidates review reject <workspace> <CREC> --reason <TESTO> --idempotency-key <KEY>
dsl-manager candidates review correct <workspace> <CREC> --reason <TESTO> --payload <JSON>
dsl-manager facts merge-batch <workspace> --batch <CBATCH> ... --stop-on-error
```

Confermare soltanto semantica sostenuta. Una correzione deve restringere
l'asserto troppo forte e produce parent superseded più replacement confirmed.
Mapping, question e conflict restano nel registry ma non sono materializzati;
lo skip `unsupported_record_type` è atteso.

## 5. Temporalità

Esaminare singolarmente i candidati temporali. Confermare date di dominio
esplicite; respingere epoch ZIP, proprietà tecniche incoerenti e timestamp non
semantici; lasciare pending i conflitti non risolti.

La temporalità di una `source_revision` non si propaga automaticamente a fatti
o relazioni. Per ottenere spell nel DSL/GEXF serve evidenza con target esplicito
`fact` o `relation`, prodotta da una regola/versione governata o da un percorso
pubblico dedicato. Non inserire righe nel database per simulare il risultato.

## 6. Output e verifiche finali

```powershell
dsl-manager dsl render <workspace>
dsl-manager dsl render <workspace> --schema-version 2
dsl-manager dsl diff <workspace> --from <DSL_V1> --to <DSL_V2> --cross-schema
dsl-manager graph export <workspace> --snapshot-id <DSL_V1>
dsl-manager graph export <workspace> --snapshot-id <DSL_V2> --dynamic --timeformat date
dsl-manager graph export <workspace> --snapshot-id <DSL_V1> --strict-orphans
dsl-manager log table <workspace> --format html --output <REPORT_HTML>
dsl-manager log csv <workspace> --output <REPORT_CSV>
dsl-manager ui serve <workspace> --host 127.0.0.1 --port 0
```

Il fail di `--strict-orphans` è previsto quando una relazione punta a un'entità
senza fatto; l'export normale deve aggiungere l'orphan con warning. Ripetere i
render senza mutazioni e verificare hash/byte identici e diff zero.

Le rotte UI pubbliche sono `/`, `/runs`, `/runs/<ID>`, `/logs`,
`/rejected-candidates`, `/conflicts`, `/snapshots` e `/diff`. Verificare GET 200,
POST 405 e shutdown pulito. Non inferire lo slug dall'etichetta visibile.

Chiudere con scan invariato, confronto SHA-256 originali/corpus, conteggi
read-only, `git diff --check` e suite completa.

## 7. Note operative Windows

- La CLI deve emettere UTF-8 anche se il processo nasce con code page CP1252.
- Il timeout predefinito Docling/Excel è 300 s, hard maximum 600 s.
- Tempi Excel molto variabili richiedono monitoraggio; non aumentare ancora il
  limite senza telemetria per fase.
- Il cleanup dei file worker usa retry/backoff limitato e resta fail-closed se
  il lock persiste.
- Per i path usare una sola forma canonica; non mescolare path 8.3 ed espansi
  nei calcoli di relativizzazione.
