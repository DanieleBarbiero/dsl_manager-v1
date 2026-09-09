# DSL Manager: dal dato grezzo all'output

Questa è la mappa architetturale sintetica dello stato consegnato fino alla
Slice 28. Per l'uso dettagliato vedere il
[manuale utente](manuale_utente_dsl_manager.md); per le invarianti vedere
l'[analisi tecnica](../documenti%20tecnici/analisi_tecnica_dsl_manager.md) e il
[design v02](../documenti%20di%20design/run%202/design_document_v_02.md).

## Il viaggio in una figura

```text
corpus/active
    |
    v
scan: source + source_revision + SHA-256
    |
    +--> documenti --------> Docling --------> normalized + chunk
    |
    +--> DDL/XML/code/log --> parser --------> source_fragment
    |
    +--> .xlsx/.xlsm ------> preflight ------> Docling (vista leggibile)
                            |                 + manifest (vista strutturale)
                            +---------------> raw temporal evidence
                                                   |
                                                   v
evidenze --regole/import--> candidato pending --review--> testa confirmed
                                                   |
                                                   v
                                                merge
                                                   |
                         +-------------------------+---------------------+
                         |                                               |
                         v                                               v
                  effective views                              reconcile queue
                         |                                               |
                         +--------------------<--------------------------+
                         |
                         v
           DSL v1/statico oppure DSL v2/dinamico
                         |
                         +--> diff
                         +--> GEXF statico o GEXF 1.3 dinamico
```

## 1. Registrare i byte

`init`, `db init` e `corpus scan` preparano workspace, schema v10 e registro.
Una `source` identifica il documento logico; una `source_revision` identifica
byte precisi. Ogni elaborazione rilegge quei byte e ne verifica l'hash.

## 2. Estrarre osservazioni

Docling crea una vista leggibile; i parser creano frammenti strutturali. Nel caso
Excel il preflight OOXML precede tutto, poi gli stessi byte alimentano due viste:

- `normalized.json`/`normalized.md` per la lettura;
- `workbook_manifest.json` e `excel_region` per la struttura.

`.xlsm` viene letto direttamente e non convertito. Macro, link esterni e formule
non sono eseguiti o ricalcolati. Formula e cached value restano distinti.

## 3. Proporre candidati

Le regole DDL/XML/codice DB/log/Excel e l'import AI producono candidati. Il
validator verifica schema, revisione, locator ed evidence text. Un candidato
accettato dal validator resta pending: non è ancora mergeabile.

## 4. Decidere

La review persiste decisioni append-only. Una foglia diventa merge-eligible solo
quando la testa corrente è `confirmed`. Idempotency key e expected head rendono
retry e concorrenza espliciti. Una correzione crea una nuova foglia e non altera
l'originale.

## 5. Consolidare e riconciliare

Il merge materializza esclusivamente candidati eleggibili e conserva la
traceability. Se una decisione già materializzata viene superata, una richiesta
di reconcile riallinea lo stato senza cancellare la storia. Le effective views
mantengono un oggetto se resta almeno un altro supporto positivo corrente.

## 6. Trattare il tempo come evidenza

Proprietà documento/package, contenuto dichiarativo, nome file e
`sources.first_seen_at` sono segnali, non verità. `mtime` e `ctime` del filesystem
non sono evidenza. Segnali correlati non contano due volte; conflitti restano
aperti e ogni intervallo proposto passa dalla review comune.

Anno e mese mantengono la precisione tramite coverage envelope; i `dateTime`
richiedono timezone esplicita o risolta. Intervalli disgiunti restano spells
distinti.

## 7. Pubblicare viste compatibili

DSL schema 1 e GEXF statico preservano la lettura fisica legacy. DSL schema 2 e
GEXF dinamico usano le viste effettive. Con reconcile aperto il default è il
blocco. `--allow-incomplete` è ammesso solo per schema 2 o export dinamico e
produce omissioni e warning; non approva pending.

Il diff fra schema diversi richiede `--cross-schema`. GEXF dinamico usa 1.3,
un solo timeformat, bounds inclusivi e validazione offline sia XSD sia semantica.

## 8. Limiti da ricordare

- `candidate_mapping`, `candidate_conflict` e `candidate_question` non hanno una
  materializzazione semantica dedicata.
- Il budget nodi+archi GEXF previsto dal design non è applicato nel runtime.
- `result_catalog_v1` è completo per review/derive/merge/reconcile/batch, ma non
  uniforme nei report OOXML/worker/temporali/GEXF.
- La pipeline AI è un handoff locale: nessuna risposta AI scrive direttamente
  fatti, decisioni o intervalli.

## 9. Percorso operativo breve

```powershell
dsl-manager init <workspace>
dsl-manager db init <workspace>
dsl-manager corpus scan <workspace>
dsl-manager batch consolidate <workspace>
dsl-manager candidates review list <workspace> --outcome pending
dsl-manager candidates review confirm <workspace> <CREC_ID> --actor-id <ACTOR_ID>
dsl-manager facts merge <workspace> --batch <CBATCH_ID>
dsl-manager facts reconcile <workspace>
dsl-manager dsl render <workspace> --schema-version 2
dsl-manager graph export <workspace> --snapshot-id <DSL_ID> --dynamic
```

Gli ID vanno presi dall'output reale. Il corpus
[Aurora Prestiti](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/LEGGIMI_PRIMA.md)
offre un esempio end-to-end verificato.
