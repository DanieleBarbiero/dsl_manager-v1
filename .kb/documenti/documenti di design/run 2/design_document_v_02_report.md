# Report di generazione del documento di design

**Prompt di origine:** `.kb/documenti/documenti di design/run 2/design_document_v_02_prompt.md`  
**Documento prodotto:** `.kb/documenti/documenti di design/run 2/design_document_v_02.md`  
**Documento di riferimento:** `.kb/documenti/documenti di design/run 1/design_document_v_01.md`  
**Data:** `2026-09-02`  
**Esito:** `completato_con_note`

## 1. Sintesi del risultato

- È stato prodotto un design implementativo completo per le sole slice 20–29, con indice navigabile, matrice compatta, modello dati/migrazioni, contratti di review e correzione, derivazione deterministica, Excel, temporalità, DSL v2, GEXF 1.3, sicurezza, test, tracciabilità e dieci prompt eseguibili.
- Il documento distingue lo stato realmente osservato nel codice dalle proposte. In particolare: i parser esistenti producono evidenza strutturata ma non candidati; il merge corrente non richiede una decisione persistita; Excel e temporalità non sono implementati; l'export corrente è GEXF statico `1.2draft`.
- La decisione centrale è il ciclo `evidence → pending → persisted decision → merge-eligible → authoritative merge`, con viste effettive e riconciliazione persistente.
- Nota rilevante: Docling 2.97.0 documenta e implementa `InputFormat.XLSX`, ma le fonti ufficiali consultate non documentano `.xlsm` come formato autonomo. Il design tratta il routing `.xlsm` richiesto come contratto applicativo soggetto a un integration test reale bloccante, senza fallback di conversione.
- Non sono state installate dipendenze né eseguiti test, come prescritto dal prompt di origine per questa attività esclusivamente documentale.

## 2. Perimetro degli input

| Input o gruppo | Ruolo | Copertura | Note |
|---|---|---|---|
| `.kb/documenti/documenti di design/run 2/design_document_v_02_prompt.md` (1 file) | prompt/contratto prevalente | completa | Letto integralmente e usato come checklist normativa. |
| `.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md` (1 file) | stato e architettura | selettiva | Inventario completo; lettura approfondita di registry, candidati, merge, render/diff, Docling, parser, batch, quality. |
| `.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md` (1 file) | contratto | selettiva | Migrazioni, worker, evidence, candidate, merge, snapshot, diff, batch e GEXF. |
| `.kb/documenti/manuali/manuale_utente_dsl_manager.md` (1 file) | comportamento pubblico | selettiva | Comandi, configurazione, flusso candidati/merge e limiti correnti. |
| `.kb/template/template_slice.md` (1 file) | template | completa | Usato per struttura e vincoli dei dieci prompt finali. |
| `.kb/documenti/documenti di design/run 1/design_document_v_01.md` (1 file) | baseline | selettiva | Principi, indice e sezioni relative a candidati, registry, hash, snapshot, batch e GEXF. |
| `.kb/projects/slicing/slice_{01..19}/dsl_manager_slice_{01..19}_report.md` (19 file) | storia implementativa | completa | Tutti i report letti; risultati dei test trattati come storici, non come verifica del worktree corrente. |
| `pyproject.toml` (1 file) | dipendenze/runtime | completa | Python `>=3.12,<3.13`, `docling==2.97.0`, pytest dev. |
| `src/dsl_mngr/**/*.py` (55 file rilevati) | stato implementato | selettiva | Inventario completo e letture mirate di migrazioni, config, candidate import/validator, merge, renderer, diff, graph, normalizer, parser e batch. |
| `tests/**/*` (40 file, di cui 23 Python) | contratto verificabile | selettiva | Inventario e raccolta test completa; letture mirate per slice/capability e fixture esistenti. Nessuna esecuzione. |
| `.kb/template/template_documento_design.md` (1 file) | template | completa | Tutte le sezioni e istruzioni assimilate. |
| `.kb/template/template_design_document_report.md` (1 file) | template | completa | Usato per il presente report. |
| `.kb/documenti/chat/quanto possiamo fidarci dei metadati dei file.md` (1 file) | contesto metadata | completa | Distinzione tra indizio incorporato e verità temporale. |
| `.kb/projects/corpus aurora/**/*` (23 file: 7 supporto/root, 16 sorgenti attive) | scenario/fixture | completa | Testi letti; `.xlsx` e `.docx` ispezionati strutturalmente come package ZIP/OOXML, senza estrazione o modifica. |
| `.kb/documenti/documenti di design/run 2/materiale di supporto/**/*` (4 file) | proposta | completa | Analisi candidati, due discussioni e proposta temporale. Le proposte sono state subordinate al prompt e al codice. |

Tutti gli input diretti richiesti esistevano ed erano leggibili. Non esistevano, ma erano soltanto riferimenti interni obsoleti del corpus Aurora, `corpus_mock_aurora_prestiti.zip` e `guida_dsl-manager.md` nella root del progetto/corpus. La correzione è assegnata alla slice 28. Le directory future `tests/fixtures/excel/` e `tests/fixtures/corpus_temporal/` non esistono ancora: sono deliverable proposti, non input mancanti.

### 2.1 Inventario Aurora osservato

I 16 file attivi comprendono: un dump DDL; tre XML Forms; due log; tre file PL/SQL; due documenti utili nuovi (`.md`, `.docx`); un `.xlsx`; due documenti storici utili (`.html`, `.txt`); due documenti non utili (`.docx`, `.html`). I sette file di supporto/root comprendono prompt+guida, README, inventario, checklist, limitazioni e due guide comando.

Il workbook corrente `matrice_stati_2025.xlsx` è un package valido ma minimale: 5.296 byte, un foglio visibile `Stati pratica`, intervallo A1:D6, inline strings, nessuna formula, merge, named range, foglio nascosto, external link o macro. Non soddisfa quindi la futura matrice di copertura; la slice 28 lo sostituisce/amplia. Le proprietà core riportano created/modified `2026-07-28T04:12:38Z`, in contrasto con il “2025” del nome/contenuto: il design usa il caso come esempio di evidenza non autoritativa.

Il manuale DOCX corrente dichiara un'edizione del 12 dicembre 2024 ma ha proprietà core created/modified del 2013. Anche questa divergenza giustifica il modello raw evidence→review anziché la promozione automatica.

## 3. Gerarchia e uso delle fonti

La gerarchia applicata è:

1. prompt v02;
2. codice e test del worktree corrente;
3. contratti manifest e manuale;
4. design v01;
5. materiale di supporto run 2;
6. corpus Aurora come fixture/esempio.

Per lo stato implementato sono stati considerati autorevoli codice, migrazioni e test correnti. I report 01–19 provano l'intento e l'esito storico delle singole slice, ma non sostituiscono lo stato del worktree. Per contratti e compatibilità sono stati usati contratti manifest, manuale e comportamento corrente. Il design v01 fornisce principi architetturali; il supporto run 2 fornisce proposte da correggere dove il prompt è più specifico. Aurora non è fonte normativa: è uno scenario di test e può contenere metadati intenzionalmente contraddittori.

Conflitti principali risolti:

- la proposta temporale ipotizzava un ciclo review specializzato; il prompt impone un'unica API comune, adottata nel design;
- il supporto candidati descrive il gap di derivazione, mentre il codice conferma che i parser persistono strutture e il merge consuma candidate records: sono state introdotte regole candidate-first;
- alcuni testi Aurora si aspettano che XLSX venga saltato; il prompt richiede supporto trasparente e quindi la checklist viene aggiornata nella slice 28;
- il design v01 ammetteva semantiche legacy basate su stati fisici; la v02 conserva tale compatibilità solo per schema1/static e usa effective views per schema2/dynamic.

## 4. Processo seguito

1. Inventario e classificazione di tutti i path diretti, conteggio di report, codice, test, supporto e corpus; verifica dello stato Git sporco prima di produrre output.
2. Lettura integrale di prompt, template, report, materiale di supporto, metadata chat e testi Aurora; letture selettive profonde di baseline, contratti, manuale, codice e test in base alle capability.
3. Analisi separate di review/merge, derivazione deterministica, batch, Excel/OOXML, temporalità, DSL/diff/snapshot, GEXF, sicurezza e fixture.
4. Riconciliazione delle dipendenze e assegnazione rigorosa alle sole slice 20–29, con migrazioni v7–v10.
5. Grounding su fonti ufficiali versionate, composizione secondo template, matrice di tracciabilità, dieci prompt finali e controlli statici su numerazione, link, placeholder, mojibake e scope file.

Non è stata ricostruita alcuna versione da `HEAD`, né sono state alterate modifiche già presenti.

## 5. Decisioni progettuali consolidate

| Decisione | Alternative considerate | Motivazione | Sezione del design |
|---|---|---|---|
| Una sola review per umano e policy | review temporale separata | Evita semantiche divergenti e soddisfa il prompt. | 7, 12 |
| Decisioni append-only + head pointer | aggiornare la riga precedente; calcolare head senza indice | Audit immutabile e concorrenza verificabile. | 7, 8.1 |
| `candidate_record_id` come soggetto | `candidate_id` dichiarativo | Il codice non garantisce unicità cross-batch. | 5, 7 |
| Correzione come nuovo batch/candidato | mutazione in-place; append al batch chiuso | Preserva origine, contatori e replay. | 7.3 |
| Effective views + coda reconcile | mutare immediatamente ogni fatto; ignorare stale support | Separa verità corrente da materializzazione e conserva storia. | 7.5 |
| Backfill legacy ristretto | confermare tutti i candidati esistenti | Non promuove inferred/pending/conflicted. | 8.1 |
| Regole parser candidate-first | facts diretti; AI obbligatoria | Evidenza/review uniforme e output deterministico. | 10 |
| Due viste Excel | solo Docling; solo parser OOXML | Docling è leggibile ma `data_only=True`; OOXML conserva formula/struttura. | 11 |
| `.xlsm` come gate reale | conversione/downgrade; dichiararlo supportato senza prova | Le fonti Docling non lo documentano autonomamente. | 11.1, 18.4 |
| Raw temporal evidence separata | normalizzare direttamente a intervallo | Metadati e nomi sono indizi spesso contraddittori. | 12 |
| DSL v2 opt-in, v1 default | cambio default immediato | Compatibilità con workflow e snapshot correnti. | 13.1 |
| GEXF XSD + validator semantico | sola XSD | La fonte GEXF elenca esplicitamente vincoli non verificati dall'XSD. | 13.2 |
| XSD venduti a commit e SHA | download runtime | Riproducibilità e no-network. | 13.2, 20 |
| `lxml==6.1.2` | parser standard; dipendenza non pin | XSD/resolver locali, supporto Python 3.12 e build riproducibili. | 13.2 |
| Budget default+hard maximum | soli timeout; valori ambientali | Protezione da package ostili e test machine-independent. | 15 |

## 6. Conflitti, ambiguità e assunzioni

| Tema | Evidenze in conflitto o informazione mancante | Risoluzione o assunzione | Impatto |
|---|---|---|---|
| `.xlsm` in Docling 2.97.0 | Prompt lo richiede; docs/backend dichiarano solo XLSX. | Routing esplicito a XLSX dopo verifica OOXML e test reale bloccante. | Nessun fallback; la slice 23 può risultare bloccata. |
| Versioni migrazione | DB corrente termina a v6; prompt non impone numeri. | Review v7, workbook v8, temporal core v9, consolidation v10. | Ordine implementativo deterministico. |
| Runtime XSD | Prompt richiede scelta motivata. | `lxml==6.1.2`, versione ufficiale PyPI osservata il 2026-09-02. | Nuova dipendenza pinned da introdurre nella slice 26. |
| Snapshot legacy | Vecchi renderer leggono stati fisici; nuove decisioni possono revocare supporti. | Schema1/static bloccato durante reconcile e altrimenti legacy; schema2/dynamic effective-only. | Compatibilità esplicita, nessuna riscrittura storica. |
| Outcome `superseded` | Decisioni append-only non consentono di mutare l'outcome precedente. | Una nuova decisione `superseded` diventa testa del soggetto originale. | Audit coerente e solo head confirmed positiva. |
| Numeri JSON | Float cross-platform problematici. | Numeri non interi diventano stringhe decimali tipizzate prima dell'hash. | Golden condivisi e hash riproducibili. |
| Profilo GEXF | Standard supporta più rappresentazioni/formati. | Un export usa interval e un solo `date` o `dateTime`. | Niente mix o coercizioni silenziose. |
| Limiti risorsa | Nessun valore imposto dal codice/prompt. | Default/hard maximum espliciti e override sotto hard cap. | Scelta progettuale da tarare con benchmark futuri. |
| Target esterni OOXML | OPC consente relazioni esterne; sicurezza richiede controllo. | URI sintatticamente conforme, mai dereferenziato; schemi attivi/userinfo rifiutati. | Link conservati con disposition/warning. |
| Aurora path mancanti | Guide citano due file non presenti. | Correzione documentale assegnata alla slice 28. | Nessun input fittizio creato ora. |
| Worktree sporco | Modifiche e rename preesistenti. | Analisi dello stato corrente, nessuna ricostruzione o modifica fuori dai due output. | Il report non attribuisce tali cambi alla generazione. |

Le scelte di migrazione, dipendenza XSD, budget, codici exit e profilo interval-only sono inferenze progettuali; state machine, campi review, correzione, formati, slicing e compatibilità richiesta derivano direttamente dal prompt.

## 7. Tracciabilità dei requisiti

| Requisito | Fonti principali | Sezione del design | Slice |
|---|---|---|---|
| Review persistita, idempotente e concorrente | prompt v02; candidate/merge corrente | 5, 7, 8, 9 | 20 |
| Correzione atomica e lineage | prompt v02 | 7.3, 8.1 | 20 |
| Effective views e reconcile | prompt v02; renderer/merge corrente | 7.5 | 20, 22 |
| Candidati deterministici | supporto candidati; parser correnti | 10 | 20–22 |
| Batch/retry/catalogo | contratti batch; prompt v02 | 7.4, 14 | 22 |
| Excel `.xlsx`/`.xlsm` | prompt v02; Docling/ECMA ufficiali | 11, 15 | 23–25 |
| Manifest/regioni/formule | prompt v02; backend Docling | 11.3 | 24 |
| Candidati Excel | prompt v02 | 10, 18.6 | 25 |
| Evidenza temporale raw e review | metadata chat; proposta temporale; prompt | 12 | 26–27 |
| DSL schema 2/hash/diff | prompt; contratti snapshot/diff | 9, 13.1 | 26–27 |
| GEXF 1.3 dinamico offline | prompt; GEXF/Gephi/lxml ufficiali | 13.2, 20 | 26–27 |
| Fixture/budget/no-network | prompt v02; corpus Aurora | 15, 16 | 23–28 |
| Aurora aggiornato | corpus e checklist correnti | 16.4, 18.9 | 28 |
| Documentazione consolidata | template/prompt | 18.10 | 29 |
| Dieci prompt implementativi | template slice; prompt v02 | 22 | 20–29 |

La tracciabilità dettagliata requisito→decisione→migrazione/schema→test→criterio di accettazione è nella sezione 17 del design.

## 8. File non-input consultati

Nessuno.

Sono stati consultati metadati Git del worktree tramite `git status`; non costituiscono un file di input. Le istruzioni repository erano già fornite nel contesto della richiesta. Non sono stati letti file locali aggiuntivi fuori dall'elenco diretto.

## 9. Grounding web

Tutte le fonti sono ufficiali o repository upstream primari; consultazione `2026-09-02`.

| Fonte | Data di consultazione | Punto supportato | Motivazione |
|---|---|---|---|
| `https://github.com/docling-project/docling/blob/v2.97.0/docs/usage/supported_formats.md` | 2026-09-02 | XLSX supportato; XLSM non elencato | Separare garanzia documentata da test applicativo. |
| `https://github.com/docling-project/docling/blob/v2.97.0/docling/document_converter.py` | 2026-09-02 | mapping XLSX/Excel, `DocumentStream`, `max_file_size` | Progettare routing e singoli byte. |
| `https://github.com/docling-project/docling/blob/v2.97.0/docling/backend/msexcel_backend.py` | 2026-09-02 | backend XLSX, stream/BytesIO e `data_only=True` | Giustificare vista OOXML formula/cached. |
| `https://github.com/docling-project/docling/releases/tag/v2.97.0` | 2026-09-02 | tag/release del 2026-06-03 | Riferimento versionato preciso. |
| `https://ecma-international.org/publications-and-standards/standards/ecma-376/` | 2026-09-02 | ECMA-376 Part 2 OPC, 5a edizione dicembre 2021 | Base per package, parti, content type e relazioni. |
| `https://gexf.net/schema.html` | 2026-09-02 | 1.3 raccomandata, tutti gli XSD richiesti, limiti XSD | Vendoring completo e semantic validator. |
| `https://gexf.net/dynamics.html` | 2026-09-02 | mode dynamic, timeformat, bounds e spells | Profilo export dinamico. |
| `https://docs.gephi.org/desktop/User_Manual/Import_Dynamic_Data/` | 2026-09-02 | interval/timestamp non misti, date/dateTime, inclusività, edge bounds | Regole applicative e compatibilità Gephi. |
| `https://github.com/gephi/gexf` | 2026-09-02 | GEXF 1.3 stabile, CC BY 4.0, timezone e bounds inclusivi | Versione/licenza/semantica. |
| `https://github.com/gephi/gexf/tree/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3` | 2026-09-02 | set `gexf.xsd`, `dynamics.xsd`, `viz.xsd` | Commit riproducibile. |
| `https://lxml.de/validation.html` e `https://lxml.de/resolvers.html` | 2026-09-02 | API XMLSchema, resolver e no-network | Scelta runtime offline. |
| `https://pypi.org/project/lxml/` | 2026-09-02 | `6.1.2`, upload 2026-08-19, Python 3.12 | Pin e compatibilità runtime. |

SHA-256 calcolati sui byte raw ufficiali del commit GEXF fissato, senza creare file locali:

| Risorsa | SHA-256 |
|---|---|
| `gexf.xsd` | `a8e1d0a6a5237fc4ce0825692fa3db49fb04d70cf3a84334f7a87c15422c1257` |
| `dynamics.xsd` | `d5ee084a858baf6efebe210d4799050723bfce71fb44c9ddbf20a53f45be8298` |
| `viz.xsd` | `e20e40bcfd4531026d4d1c74da5cbadc413ff5b81cf4418ca14f42ea994e2dc4` |

## 10. Copertura del template di design

| Sezione prevista | Esito | Nota |
|---|---|---|
| 1 Sintesi | compilata | Design §1. |
| 2 Relazione con design esistente | compilata | Design §2. |
| 3 Stato attuale rilevato | accorpata | Design §2 e report §§1–3. |
| 4 Obiettivi | compilata | Design §3.1. |
| 5 Non obiettivi | compilata | Design §3.2. |
| 6 Concetti e terminologia | compilata | Design §5. |
| 7 Flusso funzionale | compilata | Design §6. |
| 8 Review e decisioni utente | compilata | Design §7. |
| 9 Modello dati | compilata | Design §8. |
| 10 Normalizzazione e formato canonico | compilata | Design §§9, 11, 12. |
| 11 Propagazione agli artefatti | compilata | Design §§7.5, 13. |
| 12 Hash, diff e snapshot | compilata | Design §§9, 13.1. |
| 13 Export e interfacce esterne | compilata | Design §13.2. |
| 14 Configurazione | compilata | Design §14.2 e §15. |
| 15 CLI e API | compilata | Design §§7.1, 14.1. |
| 16 AI handoff | accorpata | Design §§3.2, 12.2, 16.1 e prompt 27; solo candidate handoff finto. |
| 17 Failure mode | compilata | Design §14.3. |
| 18 Strategia di test | compilata | Design §16. |
| 19 Slice verticali | compilata | Design §18, esattamente 20–29. |
| 20 Roadmap consigliata | compilata | Design §19. |
| 21 Acceptance criteria | accorpata | Per-slice §18 e globali §19. |
| 22 Esempio end-to-end | accorpata | Flusso §6 e scenario Aurora §16.4. |
| 23 Riferimenti tecnici | compilata | Design §20. |
| 24 Autoverifica | compilata | Design §21. |
| 25 Nota finale | compilata | Conclusione in §21. |

Il prompt richiedeva che indice e matrice comparissero dopo la sintesi e prima del dettaglio tecnico: sono in §4, dopo sintesi, relazione e obiettivi e prima delle specifiche.

## 11. Autoverifica

- [x] Il documento richiesto è stato creato nel path previsto.
- [x] Il report richiesto è stato creato nel path previsto.
- [x] La baseline e lo stato implementato sono distinti dalle proposte.
- [x] Ogni capability richiesta è coperta da design, test e slice.
- [x] Compatibilità, migrazioni, hash, diff e snapshot sono considerati.
- [x] Le nuove slice sono esattamente 20–29 e rispettano il perimetro imposto.
- [x] Le decisioni non direttamente imposte sono dichiarate.
- [x] I riferimenti tecnici usati sono tracciabili, versionati e datati.
- [x] Ogni riga della matrice di tracciabilità ha un test o una motivazione esplicita.
- [x] Sono presenti dieci prompt senza placeholder, uno per slice, collegati dalle sezioni delle slice.
- [x] I riferimenti obsoleti interni sono assegnati a una slice correttiva.
- [x] Non sono stati creati o modificati file fuori dallo scope autorizzato.
- [x] Non sono state installate dipendenze, modificato l'ambiente o eseguiti test.
- [x] Controlli statici non-Python non hanno rilevato mojibake o placeholder residui negli output.

### 11.1 Stato del worktree preservato

Prima della generazione erano già presenti:

- modificati: `.gitignore`, `AGENTS.md`, `src/dsl_mngr/core/config.py`;
- cancellati: i test con vecchi nomi non zero-padded delle slice 1–19;
- non tracciati: i corrispondenti test rinominati `test_slice_01_*` … `test_slice_19_*`.

Questi cambi non sono stati alterati né attribuiti al presente lavoro. `.kb` è intenzionalmente fuori Git secondo la policy del repository. I soli output prodotti sono i due file dichiarati in testa al report.

### 11.2 Verifiche effettuate

- Inventario e conteggio file via comandi di sola lettura.
- Ricerca statica di intestazioni slice/prompt, placeholder, mojibake, formati esclusi e nome `sources.first_seen_at`.
- Controllo di presenza, non-vuotezza e codifica UTF-8 dei due output.
- Nessun test applicativo: il prompt vieta installazione/modifica ambiente/test per questa generazione documentale.

## 12. Limiti e follow-up

- Il supporto `.xlsm` deve essere confermato nella slice 23 con il binario reale e Docling 2.97.0; non è dichiarato garantito dalle fonti upstream.
- I budget proposti sono scelte iniziali conservative e dovranno essere validati con benchmark, senza superare gli hard maximum senza una nuova decisione di design.
- I tre SHA GEXF sono fissati al commit upstream indicato; la slice 26 deve vendere esattamente quei byte e conservarne l'attribuzione CC BY 4.0.
- I risultati “73 passed” riportati storicamente dalla slice 19 non descrivono necessariamente il worktree sporco attuale; la prima slice di codice dovrà reinstallare con l'interprete configurato ed eseguire la suite completa.
- Nessuna decisione ulteriore è richiesta per iniziare la slice 20; ogni scostamento dai contratti qui fissati richiede aggiornamento esplicito del design.
