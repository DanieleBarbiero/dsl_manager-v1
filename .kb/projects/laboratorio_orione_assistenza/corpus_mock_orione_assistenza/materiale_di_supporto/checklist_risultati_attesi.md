# Checklist dei risultati attesi

Compilare con ID e percorsi reali della sessione; non sostituire gli spazi con
ID copiati da un'altra esecuzione.

Questa e' la checklist riutilizzabile, lasciata intenzionalmente non marcata.
Gli esiti della validazione canonica sono nel
[diario tecnico](diario_tecnico_validazione.md).

## Preparazione e immutabilita'

- [ ] Python e' 3.12 e proviene da `PROJECT_PYTHON`.
- [ ] Workspace e sorgenti di lavoro sono fuori dal repository.
- [ ] `init` e `db init` terminano con exit 0.
- [ ] L'allowlist contiene solo policy deterministiche esplicite/observed.
- [ ] Le 15 fonti attive hanno lo stesso SHA-256 prima e dopo la copia.
- [ ] Primo scan: 15 added; secondo scan: 15 unchanged; exit 0.
- [ ] Nessun artefatto pubblicato contiene il path assoluto della macchina.

## Parser e consolidazione

- [ ] Batch parse: 25 azioni completed, zero failed nella fixture canonica.
- [ ] DDL: 6 tabelle, 28 colonne, 4 FK, indici rilevati; view in warning.
- [ ] XML: 1 form, 6 campi, 4 pulsanti, 4 riferimenti tabella.
- [ ] PL/SQL: 1 procedure e 1 trigger.
- [ ] Log: 5 eventi e 1 warning di riga.
- [ ] DOCX, PDF, PPTX, TXT, Markdown, HTML, XLSX e XLSM hanno normalized/chunk.
- [ ] Workbook manifest mostra fogli, regioni, tabella, named range, formula,
  external link e macro part senza dereferenziazione/esecuzione.
- [ ] `run status` legge la run; un eventuale resume crea una nuova `retry_of`.

## Percorso AI e review

- [ ] Esistono piani technical_extraction e domain_interpretation confrontati.
- [ ] `list` ed `explain` motivano almeno un included e un excluded.
- [ ] Istruzioni, schema, template, contenuto, manifest e selection plan sono
  stati letti integralmente.
- [ ] Inbox scan indica file presente e package non stale.
- [ ] Import crea candidati pending e non fatti immediati.
- [ ] Tutti i cinque record type e i quattro assertion type sono esercitati.
- [ ] Almeno una conferma, un rifiuto e una correzione con idempotency key.
- [ ] Parent SLA e' superseded; replacement e' confirmed.
- [ ] Il fatto checklist ha due supporti indipendenti senza duplicazione.
- [ ] Mapping/question e altri tipi non materializzabili risultano skipped.
- [ ] Un piano reso stale da una nuova revisione viene rifiutato con exit 4;
  una modifica solo descrittiva della policy non viene spacciata per staleness.

## Temporalita'

- [ ] Due revisioni confermano `effective_from=2026-03-01`.
- [ ] Intervallo storico HTML 2023-01-01/2025-02-28 ispezionato.
- [ ] Intervallo aperto corrente ispezionato.
- [ ] Date discordanti DOCX/PPTX e filename restano pending o sono rifiutate.
- [ ] `sources.first_seen_at` esatto e' visibile ma rifiutato come dominio.
- [ ] Epoch ZIP 1980 verificata; `mtime`/`ctime` assenti dalle evidenze.
- [ ] Adapter riceve ID reali e crea candidati, non intervalli approvati.
- [ ] `explicit_copy` produce candidati per due fatti e una relazione.
- [ ] `aggregation` o `intersection` e' esercitata e ispezionata.
- [ ] Review conferma i candidati propagati prima del render.

## Output

- [ ] Reconcile termina senza elementi aperti o li documenta onestamente.
- [ ] DSL schema 1 e 2 renderizzati; diff cross-schema disponibile.
- [ ] Due render uguali producono DSL hash e byte stabili.
- [ ] DSL v2 contiene intervalli non vuoti su almeno due fatti e una relazione.
- [ ] GEXF statico valido.
- [ ] GEXF dinamico contiene spell di nodo e arco e passa XSD/semantica.
- [ ] Bounds dell'arco rientrano nell'intervallo di dominio selezionato.
- [ ] `--strict-orphans` fallisce per l'orphan intenzionale; non-strict aggiunge warning.
- [ ] Log esportati in HTML e CSV.
- [ ] Le otto rotte UI consentite rispondono GET 200; POST non e' consentito.
- [ ] Viene arrestato soltanto il PID UI avviato dalla sessione.
