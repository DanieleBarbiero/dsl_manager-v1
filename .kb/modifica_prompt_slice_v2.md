# Modifica dei prompt delle Slice v2 — guida e registro di verifica

Data: 2026-09-03  
Repository di riferimento: `DanieleBarbiero/dsl_manager-v1`  
Baseline: branch `main`, consultato in sola lettura  
Design v2 Git blob SHA dichiarato da GitHub: `8aa78b1210216b78d97e4e2554b075a7c1b462df`

## 1. Obiettivo

Trasformare i prompt embedded delle Slice 20–29 in prompt canonici autonomi sotto `.kb/projects/slicing/slice_<NN>/`, conservando letteralmente il nucleo normativo del design v02 e aggiungendo la disciplina operativa dei prompt maturi della run 1.

La trasformazione non rigenera semanticamente le Slice. Il modello adottato è:

`core v02 immutato → protocollo operativo comune → integrazioni specifiche → audit automatico + audit semantico`

Non vengono creati report delle Slice 20–29: i report devono nascere soltanto durante l'effettiva implementazione di ciascuna Slice.

## 2. Baseline verificata

- `AGENTS.md` corrente: versione 3.2; `.kb` e `.wb` sono directory versionate e devono restare tracciate.
- `.gitignore` corrente contiene le eccezioni per `.kb/**` e `.wb/**`; non è richiesta alcuna modifica.
- `design_document_v_02.md` contiene ancora i prompt embedded 20–29 e i link `#prompt-slice-NN`.
- Esistono le directory/report delle Slice 01–19; non esistono ancora le Slice 20–29.
- Il commit del tentativo precedente `2fa7f29` non è presente su GitHub.
- `template_slice.md`, `template_slice_report.md`, design v01 e i prompt maturi v1 sono stati usati come baseline di equivalenza operativa.

## 3. Autorità delle fonti

La regola consolidata applicata a tutti i prompt è:

1. `AGENTS.md` governa ambiente, processo e convenzioni.
2. `.kb/documenti/documenti di design/run 2/design_document_v_02.md` governa requisiti funzionali, invarianti e confini.
3. il prompt esterno della Slice governa il contratto operativo di esecuzione.
4. codice, schema e test sono lo stato osservato e non ridefiniscono implicitamente il design.
5. report precedenti e design v01 sono storia/baseline, salvo richiami normativi espliciti del v02.
6. una contraddizione non risolvibile non viene arbitrata silenziosamente: va documentata e il lavoro si ferma prima di introdurre una nuova decisione progettuale.

## 4. Protocollo operativo comune aggiunto alle Slice 20–29

Ogni prompt finale richiede esplicitamente:

- lettura integrale di `AGENTS.md`, design v02, design v01, template del report e documenti pertinenti con path letterali;
- lettura integrale di **tutti** i report precedenti con elenco zero-padded esplicito;
- ispezione di `src/dsl_mngr`, `tests`, fixture/golden, schema/migrazioni e CLI correnti;
- controllo anti-drift design ↔ report ↔ schema ↔ codice ↔ test;
- verifica reale delle dipendenze, senza assumere che un report dimostri lo stato corrente;
- classificazione preflight `pronta | gap non bloccante | bloccata`;
- gestione esplicita delle precondizioni mancanti e divieto di fix fuori scope silenziosi;
- preservazione delle modifiche utente non correlate;
- interprete determinato esclusivamente da `AGENTS.md`, senza fallback concorrenti;
- installazione editable con extra dev prima delle modifiche di codice;
- dichiarazione preventiva dei file da toccare;
- test mirati, poi suite completa;
- verifica delle CLI modificate tramite `dsl-manager`, `python -m dsl_mngr`, `--help`, exit code e stdout/stderr;
- `git diff --check`, `git diff --stat`, `git status --short` e revisione del diff;
- autoverifica finale contro scope, non-obiettivi, invarianti, tracciabilità, failure mode e Definition of Done;
- policy trasparente per test falliti/non eseguiti/limitati dall'ambiente;
- divieto di modificare fixture/golden per mascherare regressioni;
- report obbligatorio tramite `.kb/template/template_slice_report.md`, con stato `completata | parziale | bloccata`.

## 5. Matrice dei report storici

| Slice | Report richiesti | Totale |
|---:|---|---:|
| 20 | 01–19 | 19 |
| 21 | 01–20 | 20 |
| 22 | 01–21 | 21 |
| 23 | 01–22 | 22 |
| 24 | 01–23 | 23 |
| 25 | 01–24 | 24 |
| 26 | 01–25 | 25 |
| 27 | 01–26 | 26 |
| 28 | 01–27 | 27 |
| 29 | 01–28 | 28 |

Gli elenchi sono materializzati nei singoli prompt come path espliciti; non vengono usate wildcard.

## 6. Integrazioni specifiche

### Slice 20
- audit completo baseline 01–19 e stato reale merge/candidate/schema v6;
- interpretazione della vecchia frase `.codex/config.toml` esclusivamente tramite `AGENTS.md`;
- solo `ddl_table_fact/1`, senza anticipare le regole della 21;
- tabella precondizioni/evidenze/esito nel report.

### Slice 21
- gate su importer/review/v7/validator/lineage della 20;
- inventario reale degli output parser 12–14;
- nessuna logica batch;
- matrice `rule → input schema → evidence locator → candidate type → default review state → policy`.

### Slice 22
- prova delle API pubbliche 20–21 prima di modificare l'orchestratore;
- conservazione contratti batch legacy;
- state transitions, checkpoint, exit-code table ed effective hash sui retry.

### Slice 23
- ingresso diretto degli stessi byte in preflight e Docling; nessuna pre-conversione/fallback/riapertura;
- versione Docling effettiva e test `.xlsm` reale come gate;
- SHA fixture; distinzione hard/monitored memory limit;
- regressioni sui formati legacy.

### Slice 24
- riuso obbligatorio del preflight 23; nessun parser OOXML parallelo;
- schema/artefatti collegati alle sezioni normative;
- checksum dei binari prima/dopo.

### Slice 25
- gate su manifest/fragments e review comune;
- matrice `regola | input strutturale | evidence locator | candidate type | auto-review? | ragione`;
- prova che celle/header/label non diventino semantica di dominio.

### Slice 26
- gate completo sullo stato 20–25;
- path temporali/metadata/contratti risolti;
- XSD: URL, commit, licenza, SHA e offline;
- cinque checklist: migrazione/review, temporalità, DSL2/hash, GEXF, packaging;
- matrice `schema × render × diff × export × allow-incomplete` e immutabilità v1.

### Slice 27
- verifica end-to-end 20, 22, 23–25, 26;
- sottopassi obbligatori senza nuove Slice;
- matrice `source → raw evidence → correlation → candidate → review → interval → effective view → DSL v2 → GEXF spell`;
- fake-AI candidate-only obbligatoria; AI reale facoltativa.

### Slice 28
- inventario e SHA Aurora prima/dopo;
- matrice fixture → requisito → expected;
- golden derivati dal contratto, non dall'output corrente;
- difetti runtime assegnati alla Slice proprietaria, senza hidden fix.

### Slice 29
- capacità verificate in codice/test/`--help`, non soltanto nei report;
- matrice documentazione → evidenza → test → stato;
- ricerca link/comandi/riferimenti obsoleti;
- coerenza finale migrazioni v7–v10, CLI, result catalog, manuale e contratti;
- nessun runtime nuovo.

## 7. Estrazione deterministica e prova di non-perdita

L'estrazione usa esclusivamente gli heading `### Prompt Slice NN` nella sezione 22 e richiede esattamente la sequenza 20–29, senza duplicati, omissioni o blocchi vuoti. Il testo fra un heading e il successivo viene conservato letteralmente come **core**; wrapper e integrazioni sono aggiunti fuori dal core.

| Slice | SHA-256 core originale | Byte core | Destinazione |
|---:|---|---:|---|
| 20 | `54e69abe5be83242822fae46c3daaca90477a4d5d0424fe8cfa734488d9314b9` | 3042 | `.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md` |
| 21 | `d66ea9c81f9ff8f4fb67490201c049ae2c026b9e1ad588225d383e6147c9edb5` | 2142 | `.kb/projects/slicing/slice_21/dsl_manager_slice_21_prompt.md` |
| 22 | `a71a2b74377e17303dd5d327fadf28174e7d9d1a5cb502601052df284ba07eb7` | 1924 | `.kb/projects/slicing/slice_22/dsl_manager_slice_22_prompt.md` |
| 23 | `e2860923260aa9fb785424b626f1c02dc091a8ac23dbb357761209064d345103` | 2186 | `.kb/projects/slicing/slice_23/dsl_manager_slice_23_prompt.md` |
| 24 | `d7860c9acd55df66d440775d15fb02373596569f34e9c4c2368369a742a5cd42` | 1892 | `.kb/projects/slicing/slice_24/dsl_manager_slice_24_prompt.md` |
| 25 | `bbef43ecef60fb39af70cfc29ff7471b2a5dce165734a7fc5cca7a0f50cf1c13` | 1622 | `.kb/projects/slicing/slice_25/dsl_manager_slice_25_prompt.md` |
| 26 | `be28bf91860d2f93ca30cf4795313ca7a8e8843ac86e5a567332ff71831451e7` | 2737 | `.kb/projects/slicing/slice_26/dsl_manager_slice_26_prompt.md` |
| 27 | `aaea2c41f566d74707bf834dc451f051019229e107a1d1f4e8f096bcd5e91e90` | 2371 | `.kb/projects/slicing/slice_27/dsl_manager_slice_27_prompt.md` |
| 28 | `d195abd140ccc23a0cbca811a830234c53b54cc4fe99c0662bd5989180c33398` | 2125 | `.kb/projects/slicing/slice_28/dsl_manager_slice_28_prompt.md` |
| 29 | `d363865ac465e98e68a499c7f169005f9c9841dd288ae39f3400c6b1f763882e` | 1931 | `.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md` |

Il controllo finale verifica che ogni core compaia letteralmente e una sola volta nel prompt prodotto.

## 8. Aggiornamento del design v02

Dopo la validazione dei dieci prompt:

- i dieci link `#prompt-slice-NN` nelle sezioni 18.1–18.10 vengono sostituiti con link relativi ai file canonici;
- la sezione 22 resta presente ma diventa un indice dei dieci prompt esterni;
- i blocchi embedded `### Prompt Slice NN` vengono rimossi dal design;
- l'auto-verifica viene aggiornata per dichiarare i prompt esterni collegati e pronti all'uso;
- il design resta autorità funzionale, i prompt esterni contratto operativo, `AGENTS.md` autorità di ambiente/processo.

Nel pacchetto è presente anche `PATCH_design_document_v_02.diff`. **Per applicare la modifica al clone reale è preferibile usare la patch**: agisce sulla copia esatta del design presente nel repository e impedisce che differenze non intenzionali in una copia di lavoro sostituiscano il file completo.

## 9. Equivalenza funzionale con i prompt v1

Criterio di accettazione:

> ogni comportamento operativo richiesto dal template storico o dai prompt v1 maturi deve avere nel prompt v2 un requisito equivalente o più forte; le aggiunte non possono ampliare lo scope, spostare feature o introdurre fallback.

| Comportamento operativo | v2 finale |
|---|---|
| legge `AGENTS.md` | PASS |
| legge design completo | PASS |
| usa template report | PASS |
| legge tutti i report precedenti | PASS |
| ispeziona codice corrente | PASS |
| ispeziona test/fixture/golden | PASS |
| controllo anti-drift | PASS |
| dichiara file previsti | PASS |
| install editable | PASS |
| test mirati | PASS |
| suite completa | PASS |
| verifica `dsl-manager` e `python -m dsl_mngr` | PASS |
| verifica `--help`/exit/stdout/stderr per CLI interessate | PASS |
| `git diff --check` | PASS |
| diff/status | PASS |
| autoverifica finale | PASS |
| report tramite template | PASS |
| fuori scope/gap/deviazioni | PASS |
| gestione test non eseguiti/falliti | PASS |
| tracciabilità requisito→test | PASS+ |

## 10. Test statici eseguiti sul pacchetto

I controlli vengono rieseguiti al termine della costruzione del pacchetto. I gate previsti sono:

1. esattamente 10 prompt e 0 report 20–29;
2. numerazione/directory/filename 20–29 coerenti;
3. core originale contenuto letteralmente una sola volta;
4. tutti i report 01–NN-1 presenti una volta e nessun report futuro;
5. nessun placeholder del template v1 residuo;
6. protocollo comune obbligatorio presente;
7. `AGENTS.md` autorità esclusiva dell'interprete;
8. report path/template corretti;
9. marker specifici della singola Slice presenti;
10. equivalenza operativa v1 automatica;
11. zero anchor `#prompt-slice-NN` nel design modificato;
12. zero blocchi prompt embedded nel design modificato;
13. ogni prompt esterno collegato esattamente due volte dal design (piano + indice);
14. auto-verifica design aggiornata;
15. patch del design applicabile e risultato equivalente alla copia modificata;
16. audit semantico finale dei dieci prompt;
17. SHA-256 finale di ogni file del pacchetto.

## 11. Decisioni deliberate / scostamenti dai vecchi piani

- `AGENTS.md` e `.gitignore` **non vengono modificati**: la baseline corrente è già allineata e dichiara `.kb`/`.wb` versionati.
- nessun report Slice 20–29 viene creato preventivamente;
- lo script di estrazione/build resta strumento temporaneo del workspace e non viene aggiunto al progetto;
- nessun codice runtime DSL Manager viene eseguito durante questa trasformazione documentale;
- nessun commit, branch, push o pull request viene creato tramite il collegamento GitHub;
- per il design viene fornita una patch applicativa, così la trasformazione può essere applicata alla copia esatta del clone locale con `git apply --check` prima di ogni modifica.

## 12. Stato finale

La checklist finale e gli hash definitivi sono riportati anche in `MANIFEST.json` e `SHA256SUMS.txt` alla radice del pacchetto. Il file `ISTRUZIONI_APPLICAZIONE.md` descrive l'applicazione sicura al clone locale.

## 11. Esito dell'audit finale del pacchetto

Audit finale eseguito dopo la generazione:

- 10/10 prompt Slice 20–29: **PASS**;
- 36 gate globali/strutturali: **PASS**;
- 0 report Slice 20–29 creati;
- tutti i core normativi compaiono una sola volta nei prompt finali;
- tutti i report precedenti `01…NN-1` sono elencati esattamente una volta;
- equivalenza operativa con i prompt v1 maturi: **PASS**;
- marker e integrazioni specifiche di ogni Slice: **PASS**;
- design preview: 0 anchor `#prompt-slice-NN`, 0 prompt embedded, 2 link per ogni prompt esterno: **PASS**;
- patch applicata al checkpoint locale: `git apply --check` e `git diff --check`: **PASS**;
- sezioni normative 20–29 rifetchate singolarmente dal `main` GitHub durante l'audit finale: **coerenti con i core generati**.

### Nota di sicurezza sulla rappresentazione del design

GitHub riporta per il design v02 corrente il Git blob SHA
`8aa78b1210216b78d97e4e2554b075a7c1b462df`. Il checkpoint testuale
materializzato dal connettore ha la stessa dimensione (`89660` byte), ma un
Git blob SHA locale diverso (`a687c84207c8a3ace1a8e54a5928e1ae5b92e6a6`).
Le sezioni prompt 20–29 sono state per questo riverificate direttamente su
GitHub e risultano coerenti; tuttavia il file `reference/design_document_v_02.modified.preview.md`
**non deve essere usato per sovrascrivere alla cieca il design del clone**.

Il metodo di applicazione raccomandato è `tools/apply_design_update.py`, che:

1. calcola il Git blob SHA del design reale nel clone;
2. accetta per default solo la baseline GitHub verificata `8aa78b…`;
3. applica trasformazioni puntuali e validate;
4. controlla che non restino anchor o prompt embedded e che ogni nuovo link compaia due volte;
5. scrive atomicamente il risultato.

L'opzione `--force-baseline` esiste solo per diagnosi/manual review e **non va usata nel normale flusso di applicazione**.
