# Diario tecnico di validazione

Data: 2026-09-14. Interprete usato in ogni invocazione Python:
`PROJECT_PYTHON`, Python 3.12.10. Non sono stati eseguiti test pytest e non sono
stati modificati `src/` o `tests/`. La rete e le macro non sono state usate.

I path assoluti locali non sono pubblicati. Il workspace principale e'
identificato come `%TEMP%\orione_assistenza_e2e_73077a1cc436451faf3cf1485232ebd7\workspace`;
quello delle fixture negative come la sottodirectory `controlled_workspace`.
Entrambi sono nuovi, fuori dal repository e sono stati conservati per diagnosi.

## Preparazione e fixture

`build_orione_assistenza_fixtures.py` e' stato eseguito due volte senza rete:
exit 0 entrambe le volte. `checksums.json` e `inventario_fonti.csv` sono rimasti
byte-identici tra le due esecuzioni. Hash SHA-256 finali dei due manifest:

- checksums: `e138bb42ad8f21a197da783ea5348a8a57cfbed9c6e62100051e448c1051edaf`;
- inventario: `e4478fac38630b557f16f5140ee002ba206c252ec40f2cecba3b9e8157bead64`.

Sono coperte 15 fonti attive e 3 fixture controllate. Tutti i membri dei ZIP
OOXML hanno timestamp DOS 1980-01-01. Il workbook XLSM espone
`xl/vbaProject.bin`, hash
`98fc6b0e03873ad8ef2e31634c1b0ab65cad5a45306961ce75cff3c971aac5f4`,
`present=true`, `executed=false`. Il link a `orione.invalid` risulta
`not_dereferenced`; `external_targets_dereferenced=false`.

## Percorso deterministico reale

Comandi pubblici: `init`, `db init`, due `corpus scan`, quindi
`batch consolidate --reconcile`. Init e DB hanno terminato 0; la prima
migrazione ha applicato 11 versioni. Hash della copia e delle fonti canoniche:
15 su 15 uguali. Primo scan: 15 added; secondo: 15 unchanged. Dopo tutte le
prove il controllo e' stato ripetuto: 15 file, zero differenze SHA-256, scan
finale 15 unchanged, exit 0.

La run consolidata `RUN_000001` ha terminato 0:

| Misura | Osservato |
|---|---:|
| parse completed / failed / skipped | 25 / 0 / 0 |
| candidati prodotti | 117 |
| candidati temporali | 31 |
| auto-confirmed | 86 |
| fatti / relazioni iniziali | 78 / 8 |
| reconciliation pending | 0 |

Artefatti verificati: 6 tabelle, 28 colonne, 4 FK, 2 indici e 49 frammenti
DDL; la view e' il solo `unsupported_statement` in warning. Forms: 1 form, 6
campi, 4 pulsanti, 4 tabelle, 11 frammenti. PL/SQL: 1 procedure e 1 trigger;
gli statement interni restano 0 nel sottoinsieme corrente. Log: 5 eventi e una
riga invalida segnalata. Markdown, TXT, HTML, DOCX, PDF, PPTX, XLSX e XLSM
hanno prodotto normalizzato e chunk. I workbook hanno inoltre manifest e
frammenti strutturali; sono state osservate visibilita' visible/hidden/
very_hidden, quattro regioni nel foglio principale, tabella, named range,
merge, tipi scalari, errore e blank, formula B7 con cache 8 e formula B8 senza
cache.

Una seconda consolidazione `RUN_000077` ha terminato 0 e ha riutilizzato lo
stato effettivo: 78 fatti e 8 relazioni existing, 0 creati, reconciliation
pending 0. Il batch puo' durare diversi minuti per Docling; il timeout letto
dalla configurazione e' 300 s, con hard maximum 600 s.

## Selezione e percorso AI

I piani iniziali reali hanno dato:

- `AISEL_000001`, technical_extraction: 89 esaminate, 11 incluse, 78 escluse,
  603 caratteri;
- `AISEL_000002`, domain_interpretation: 89 esaminate e incluse, 26 884
  caratteri.

Sono stati eseguiti `list` ed `explain` su esiti inclusi ed esclusi. Il package
interpretativo `AIPKG_000001` e' stato letto integralmente: istruzioni, schema,
template, contenuto, source manifest, selection plan e package manifest.
Durante il percorso autentico la risposta e' stata composta soltanto da
frammenti/chunk del package con testo letterale; sono stati esercitati fact,
relation, mapping, conflict e question e le quattro assertion type explicit,
observed, inferred, ambiguous.

Scostamento incontrato durante la costruzione: la prima bozza aveva 12 righe e
una relazione orphan usava `Una` invece del letterale `una`; import: 11
accepted, 1 rejected. Non e' stato cambiato l'expected per nasconderlo. Il testo
e' stato corretto nella fixture, e un fatto distinto sul tecnico e' stato
aggiunto per poter esercitare aggregation senza collisione semantica.

Il replay finale pubblicato e' stato verificato di nuovo contro un package
non stale `AIPKG_000004`: tutti i 13 evidence ID e i 13 `evidence_text`
compaiono letteralmente nel package. `ai inbox scan` ha indicato non stale;
`ai import --package` ha creato `CBATCH_000119`, total 13, accepted 13,
rejected 0, stale allowed false, exit 0. Si tratta sempre di replay controllato:
non e' stata effettuata una chiamata a un modello.

La review autentica precedente ha dimostrato:

- conferme, rifiuto e correzione con idempotency key;
- parent dell'asserto SLA `CREC_000120` superseded e replacement
  `CREC_000129` confirmed;
- autoassegnazione storica rifiutata;
- contratto esterno ambiguous lasciato pending;
- mapping, conflict e question revisionati con skip di materializzazione
  appropriati;
- fatto checklist `FACT_000079` con due supporti indipendenti, `REV_000005` e
  `REV_000008`, senza duplicazione;
- relazione assegnazione `REL_000009` e orphan intenzionale `REL_000010`.

Il tentativo di costruire un package da un piano dopo una vera modifica di
revisione e' stato respinto: `selection_plan_stale`, exit 4. La fonte temporanea
e' stata immediatamente ripristinata byte per byte e riscansionata. Un test
precedente aveva cambiato soltanto la descrizione della policy: il package era
rimasto valido; questo comportamento e' registrato come distinzione corretta,
non come falsa prova di staleness.

## Decisioni e propagazione temporale

Due candidati espliciti e concordanti 2026-03-01 sulle revisioni correnti sono
stati confermati. `sources.first_seen_at` esatto
`2026-09-14T17:42:57+02:00` e' stato mostrato e rifiutato come metadata tecnico,
non come validita' di dominio. Le date da filename e i metadata DOCX/PPTX
incoerenti non sono stati promossi; i conflitti non risolti sono rimasti
pending. Mtime e ctime non compaiono come evidenze promosse. Il log conserva
timezone nel messaggio.

Le due evidenze HTML sono state corrette con la review pubblica in un intervallo
sorgente 2023-01-01/2025-02-28. Il parent e' superseded; il replacement
`CREC_000254` e' confirmed. L'adapter, verificato privo di SQL e accessi diretti
al DB, ha poi prodotto candidati pending:

- explicit_copy corrente su `FACT_000079`, `FACT_000081` e `REL_000009`;
- aggregation delle due fonti correnti su `FACT_000082`;
- explicit_copy storico su `FACT_000079` e `REL_000009`.

Ogni ID prodotto e' stato passato a `review show`, confermato tramite i comandi
comuni e materializzato solo dopo `facts merge-batch`. Un primo tentativo di
aggregation sul fatto SLA gia' coperto ha riusato semanticamente l'intervallo
ma non ha creato un'associazione al nuovo candidato; `merge-batch` ha terminato
2 con `Confirmed temporal candidate has no materialized interval`. Workaround
pubblico e sicuro: candidato rifiutato, target distinto creato tramite normale
candidato AI/review/merge, aggregation ripetuta e completata. Nessun SQL.

Stato finale: 82 fatti e 10 relazioni. Lo schema 2 contiene intervalli non
vuoti su tre fatti e una relazione; `FACT_000079` e `REL_000009` hanno entrambi
lo storico chiuso e il corrente aperto. Gli intervalli dell'arco sono uguali,
quindi contenuti, nei bounds del fatto di dominio usato per il controllo.

## Render, grafi, log e UI

Render finali pubblici:

| Output | ID | Hash semantico |
|---|---|---|
| schema 1 | `DSL_000010` | `ad0abccce0bc780d0650db27c2819cd33925a5a660e9a547258da21670733ba9` |
| schema 2 A | `DSL_000011` | `700c78184ce5c5e5f48f7414f6d993ac07f10349c6a4856c6885c90b9e201620` |
| schema 2 B | `DSL_000012` | identico ad A |

I due render schema 2 sono byte-identici separatamente per JSON, YAML e
Markdown. SHA-256: JSON `36753beefbd3a2434214437f7f217b53e3ebaa4e46135728d6fc2d947ac84f2d`,
YAML `6754b33beb3b71452e763c5d915ea28650dac633de8100a375745a7b10bda458`,
Markdown `7bb2d264dda71ef017919cabe448d47e832c9feca40e36ee7572e444e2f2edf2`.
Il diff cross-schema ha terminato 0 con 2 modifiche governate.

GEXF statico: exit 0, 95 nodi, 109 archi, 1 orphan, 1 warning. Lo stesso
export con `--strict-orphans` ha terminato 2 come previsto. GEXF dinamico:
exit 0, validazione XSD e semantica completate. Ispezione XML namespace-aware:
2 spell di nodo e 4 spell di arco. Il nodo `fact:FACT_000079` e l'arco
`relation:REL_000009` mostrano entrambi:

- 2023-01-01 / 2025-02-28;
- 2026-03-01 / aperto.

La relazione XML collega nodi entity mentre la temporalita' del fatto vive sul
nodo fact; il validatore tratta entity senza intervalli come non limitanti.
Questo limite pubblico e' dichiarato senza fingere che il nodo fact sia
l'endpoint XML dell'arco.

`log table --format html` e `log csv` hanno terminato 0 e prodotto file da
68 061 e 19 845 byte. La UI e' stata avviata con il comando pubblico in
loopback su una porta libera tramite `Start-Process -WindowStyle Hidden
-PassThru`. GET 200 osservato per `/`, `/runs`, `/runs/RUN_000161`, `/logs`,
`/rejected-candidates`, `/conflicts`, `/snapshots`, `/diff`; POST `/` ha dato
405. Nel `finally` e' stato arrestato soltanto il PID avviato.

## Fixture negative e ripresa

Nel workspace controllato separato, il batch con entrambi i workbook ha
terminato 2: malformed fallito nel worker con exit 3 e
`ooxml_security_violation` per ZIP senza central directory; relativo chunk
skipped. Il workbook partial controllato e' stato normalizzato e chunkato con
exit 0 dal worker reale. Il contratto `partial_success`/exit 6 richiede un
worker controllato iniettabile, che la CLI non espone: la fixture e' quindi
valida ma non viene presentata come prova pubblica di uno stato partial.

`run status` ha mostrato il fallimento retryable. Un singolo
`batch consolidate --resume RUN_000001` ha creato `RUN_000006` con
`retry_of=RUN_000001`, `attempts=2` e ha ripetuto l'intera fase parse: stesso
fallimento malformed e stesso successo del workbook valido. Questo e'
l'esito intenzionale, non un test da rendere verde.

Lo script interattivo ha superato parsing PowerShell con zero errori,
`-ValidateOnly` con exit 0, avvio/uscita e ripresa della medesima sessione con
exit 0. E' stata inoltre eseguita davvero la fase mutante iniziale: `init`,
`db init`, copia di 15 fonti, confronto degli hash e scrittura dell'allowlist
nel solo workspace temporaneo; exit 0. Sono stati creati e riletti `session_state.json`,
`diario_esecuzione.md` e `commands.log`. Lo script non contiene path assoluti,
risale alla root e invoca soltanto l'interprete configurato.

## Scostamenti e limiti aperti

Non sono emersi difetti che richiedano modifiche a `src/` o `tests/`. Restano
tre limiti pubblici, tutti documentati:

1. manca un leaf CLI per la propagazione temporale; e' necessario l'adapter
   governato richiesto dal contratto;
2. manca un leaf CLI per configurare l'allowlist; il tutorial modifica soltanto
   il YAML del workspace;
3. manca una rotta pubblica per iniettare un worker che restituisca
   `partial_success`; il workbook controllato non puo' dimostrarlo con la sola
   CLI reale.

Non e' stato chiesto ne' applicato alcun workaround privato. Il problema della
aggregation semanticamente duplicata e' stato aggirato usando review e target
distinto tramite comandi pubblici. Nessun blocco impedisce il percorso
principale o la produzione di intervalli e spell reali.

Audit documentale finale: 30 file previsti su 30, 18 checksum verificati su 18,
18 righe inventario, 7 link relativi risolti, zero errori UTF-8/JSON/JSONL,
zero path macchina pubblicati, zero trailing whitespace e zero errori del
parser PowerShell. `git diff --check` sul progetto Orione non ha segnalato
errori. Le modifiche preesistenti in altre aree del worktree sono rimaste
intatte.

## Addendum post-Slice 31

La registrazione precedente resta storia del collaudo pre-Slice 31. Dopo
l'installazione della Slice 31, Orione e' stato rieseguito in un workspace
temporaneo nuovo usando esclusivamente i nuovi comandi pubblici nel flusso
principale. Il percorso e gli ID qui riportati sono relativi alla sola sessione
post-slice e non sono input riutilizzabili.

Esiti osservati:

- `db init`: 12 migrazioni applicate, exit 0;
- `config review show`: allowlist iniziale vuota, exit 0;
- `config review profiles`: `conservative/1`, 13 policy, profile hash
  `1fc093f7f59056c195aa4b0deb352f96e42dec42fc1b8b29779441b6b81e7eb6`, exit 0;
- `config review apply-profile` e `config validate --profile conservative/1`:
  configurazione valida, 13 policy effettive, exit 0;
- doppio `corpus scan`: 15 added, poi 15 unchanged, exit 0.
- `batch consolidate --reconcile`: exit 0; 25 parse completed, 117 candidati,
  86 auto-confirmed, 31 candidati temporali pending, 78 fatti e 8 relazioni;
- review e merge di `CREC_000095`/`CREC_000106`, intervalli sorgente aperti
  `2026-03-01`, exit 0;
- quattro propagazioni pubbliche (`explicit_copy` verso due fatti e una
  relazione; `aggregation` da due revisioni verso un fatto): `CREC_000118`–
  `CREC_000121` osservati pending prima della review, poi quattro conferme e
  merge 4/4, exit 0;
- review/merge dell'intervallo sorgente storico 2023-01-01/2025-02-28 e due
  ulteriori `explicit_copy` verso lo stesso fatto e la stessa relazione:
  `CREC_000122`/`CREC_000123` pending prima della review, merge 2/2, exit 0;
- DSL v2 finale `DSL_000003`, hash
  `ffb1af507338ce3e4d17f0f7971ca50d4be933acd7f76cbcb6f49905ab5d70de`:
  tre fatti e una relazione con intervalli, quattro intervalli fact e due
  relation, render exit 0;
- GEXF dinamico strict: exit 0, due `<spell>` di nodo e quattro di arco; gli
  intervalli osservati sono 2023-01-01/2025-02-28 e 2026-03-01/aperto;
- `diagnostics normalization run` su `REV_000005`: `RUN_000074`, run e worker
  `partial`, exit worker/CLI 6, `controlled_simulation: true`, due artefatti
  workspace-relative nel namespace diagnostico e hash dello stato di
  produzione identico prima/dopo; `run status` exit 0.

Il verbale complessivo dei comandi e degli exit code è nel
[report Slice 31](../../../slicing/slice_31/dsl_manager_slice_31_report.md). Il
tutor e le due guide ora orchestrano `config review`, `temporal propagate` e
`diagnostics normalization run`; non modificano YAML, non importano servizi
core e non selezionano worker arbitrari.
