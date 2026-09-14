# Prompt per creare il laboratorio «Orione Assistenza»

Agisci come autore tecnico e collaudatore umano di DSL Manager. Crea un
laboratorio canonico, autonomo e ripetibile dedicato a **Orione Assistenza**,
una piccola applicazione legacy Oracle Forms/PL/SQL per asset, interventi,
tecnici, assegnazioni, checklist di chiusura e SLA. Il laboratorio deve essere
parallelo ad Aurora per qualita' didattica e completezza, ma non deve copiarne
scenario, contenuti, valori attesi, file o workspace.

Questo e' un lavoro documentale e di fixture: non modificare `src/` o `tests/`
e non rieseguire `pytest`. Per validare il risultato usa realmente i comandi
pubblici dell'applicazione su un workspace temporaneo nuovo. Se emerge un
difetto di codice o infrastruttura non aggirabile con un percorso pubblico e
sicuro, fermati, documenta comando, exit code, log e diagnosi, quindi chiedi
autorizzazione prima di correggere il programma.

## 1. Fonti da assimilare prima di scrivere

Leggi integralmente `AGENTS.md`, tutto il codice in `src/dsl_mngr/`, i test
pertinenti in `tests/` e almeno questi documenti canonici:

- `.kb/documenti/project_summary.md`;
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
- `.kb/documenti/documenti di design/run 2/materiale di supporto/analisi_presenza_funzione_candidati_deterministici.md`;
- `.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_01.md`;
- `.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_02.md`;
- `.kb/documenti/documenti di design/run 2/materiale di supporto/dsl_manager_estensione_temporalita_semantica_v_01.md`;
- `.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md`;
- `.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md`;
- `.kb/documenti/manuali/manuale_utente_dsl_manager.md`;
- `.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_completo.md`;
- `.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md`;
- `.kb/documenti/bugfixes/bugfix_01_ooxml_temporal_docx_preflight.md`;
- `.kb/documenti/bugfixes/bugfix_02_stale_outline_references.md`;
- `.kb/documenti/bugfixes/bugfix_03_multiline_yaml_policy_lists.md`.

Leggi senza salti tutti i report da
`.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md` a
`.kb/projects/slicing/slice_30/dsl_manager_slice_30_report.md`, seguendo per
ogni numero il nome completo zero-padded `slice_01` ... `slice_30`.

Usa come riferimenti di esposizione, non come corpus o procedura da copiare:

- `.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/LEGGIMI_PRIMA.md`;
- `.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl_manager_cmd_v_02.md`;
- `.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl_manager_powershell_v_02.md`;
- `.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/checklist_risultati_attesi.md`;
- `.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/matrice_fixture_attesi.md`;
- `.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/limitazioni_intenzionali.md`.

Non usare `.wb/`. Verifica nel codice e nell'help corrente ogni comando,
opzione, formato, exit code e rotta: i manuali sono una base, non una scusa per
pubblicare sintassi non collaudata.

## 2. Destinazione e nomi obbligatori

Conserva questo prompt senza sovrascriverlo in
`.kb/projects/laboratorio_orione_assistenza/dsl_manager_laboratorio_orione_assistenza_prompt_v_01.md`
e crea il progetto esclusivamente sotto
`.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/`.
Tutti i nuovi nomi controllati dal progetto devono essere lowercase
`snake_case`; le versioni devono usare `_v_01`.

Produci almeno questi file, esattamente nei percorsi indicati:

```text
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/leggimi_prima.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/database/dump_oracle_ddl.sql
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/plsql/prc_assegna_tecnico.sql
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/plsql/trg_chiudi_intervento.sql
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/forms/frm_intervento.xml
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/logs/interventi_2026.log
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/nuovi_utili/requisiti_modernizzazione_2026.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/nuovi_utili/decorrenza_servizio_2026.txt
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/nuovi_utili/manuale_operativo_2026.docx
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/nuovi_utili/matrice_stati_sla_2026.xlsx
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/nuovi_utili/calcolo_sla_macro_2026.xlsm
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/nuovi_utili/architettura_integrazioni_2026.pptx
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/vecchi_utili/accordo_sla_2025.pdf
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/vecchi_utili/procedura_assegnazione_2023.html
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/vecchi_non_utili/inventario_arredi_2022.txt
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/corpus/active/documenti/nuovi_non_utili/istruzioni_parcheggio_2026.html
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/build_orione_assistenza_fixtures.py
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/checksums.json
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/inventario_fonti.csv
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/checklist_risultati_attesi.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/matrice_fixture_attesi.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/limitazioni_intenzionali.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/guida_dsl_manager_cmd_v_01.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/guida_dsl_manager_powershell_v_01.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/laboratorio_orione_assistenza_interattivo_v_01.ps1
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/promuovi_temporalita_orione_assistenza.py
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/diario_tecnico_validazione.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/fixture_controllate/ai_response_orione_assistenza_controllata.jsonl
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/fixture_controllate/workbook_malformed_controllato.xlsx
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/fixture_controllate/workbook_partial_controllato.xlsx
```

Se il codice corrente supporta un parser o un formato di normalizzazione non
esercitato dall'elenco, aggiungi la fixture minima necessaria, con nome conforme,
e aggiornane inventario, checksum, matrice, guide e script. Non creare ZIP del
progetto: i file devono restare ispezionabili e versionabili.

## 3. Contratto del corpus

Il corpus deve essere piccolo, coerente e interamente fittizio, ma abbastanza
ricco da esercitare davvero DDL Oracle con primary/foreign key, view e
`CREATE INDEX`; procedure e trigger PL/SQL nel sottoinsieme supportato; XML
Forms con campi, pulsanti e riferimenti a tabelle; log con eventi normali,
warning ed errori; normalizzazione e chunking di Markdown, TXT, HTML, DOCX,
PDF, PPTX, XLSX e XLSM.

`matrice_stati_sla_2026.xlsx` deve includere piu' fogli con stati di visibilita'
diversi, piu' regioni, tabella, named range, merged range, stringhe, numeri,
booleani, date, errori e blank, una formula con cached value e una senza, oltre
a un external link inventariato ma mai dereferenziato.
`calcolo_sla_macro_2026.xlsm` deve contenere un `vbaProject.bin` inerte:
rilevato e hashato, mai eseguito. Le due fixture workbook controllate devono
distinguere chiaramente rifiuto malformed e risultato partial; non presentarle
come fonti operative.

Costruisci una storia verificabile, non un insieme casuale di file. Includi:

- regole tecniche conservative adatte a candidati deterministici e
  auto-review allowlisted;
- relazioni e interpretazioni che devono restare pending;
- un fatto di dominio sostenuto da due fonti indipendenti, per verificare il
  supporto multiplo senza duplicazione;
- un asserto troppo forte da correggere durante la review;
- un candidato da rifiutare, un orphan intenzionale e almeno un conflitto
  storico/corrente;
- rumore recente e storico che non deve diventare verita' di dominio;
- contenuti abbastanza discorsivi e ambigui da rendere sensato il percorso AI,
  non una parafrasi di strutture gia' estratte deterministicamente.

### Temporalita'

Copri esplicitamente: `effective_from` corrente e concordante in due fonti;
intervallo storico chiuso; intervallo aperto; date discordanti; data nel nome
del file; metadata DOCX/PPTX incoerenti col contenuto; timestamp di log con
timezone; `sources.first_seen_at` esatto; epoch ZIP OOXML. Verifica inoltre che
`mtime` e `ctime` del filesystem non siano promossi a evidenze. La guida deve
far confermare date di dominio esplicite, rifiutare metadata tecnici o
incoerenti e lasciare pending i conflitti irrisolti.

Non confondere validita' della sorgente e validita' dell'asserto: un intervallo
su `source_revision` non si propaga automaticamente a `fact` o `relation`.
Il laboratorio e' completo soltanto se l'utente puo' promuovere esplicitamente
la temporalita' su fatti e relazioni, sottoporla alla review comune e ottenere
intervalli non vuoti nel DSL v2 e spell reali nel GEXF dinamico.

Verifica prima se il contratto CLI corrente espone un leaf per questa
propagazione. Se esiste, usa e documenta quello. Se non esiste, usa il servizio
governato e gia' implementato
`dsl_mngr.core.temporal_consolidation.propagate_temporal_intervals` attraverso
il solo adapter locale
`materiale_di_supporto/promuovi_temporalita_orione_assistenza.py`. L'adapter
deve essere sottile, validare tutti gli argomenti, accettare gli ID reali del
workspace, offrire esclusivamente le policy versionate `explicit_copy`,
`intersection`, `aggregation` e `conflict`, restituire un output JSON
strutturato e non contenere SQL ne' accessi diretti al database. Deve creare
candidati `temporal_interval`, non intervalli gia' approvati: conferma o
rifiuto restano azioni umane eseguite con i normali comandi di review.

Stabilisci e usa nelle due guide e nello script questa interfaccia dell'adapter:

```text
promuovi_temporalita_orione_assistenza.py --workspace WORKSPACE --run-id RUN_ID --source-revision-id REV_ID --target-subject-type fact|relation --target-subject-id TARGET_ID --source-subject TYPE:ID [--source-subject TYPE:ID ...] --policy explicit_copy|intersection|aggregation|conflict
```

`--source-subject` deve essere ripetibile; per la prima dimostrazione usa una
`source_revision:REV_ID` il cui intervallo sia gia' stato confermato. L'output
deve riportare almeno policy, target, sorgenti, candidate record ID oppure
conflict ID ed exit code semantico. I passaggi successivi devono acquisire da
questo JSON gli ID dei candidati, mostrarli all'utente e passarli alla review.

Le guide e lo script devono mostrare almeno una promozione `explicit_copy` da
una sorgente confermata verso due fatti che saranno nodi e verso la relazione
che sara' l'arco; l'intervallo dell'arco deve essere contenuto in quelli dei
nodi estremi. Devono inoltre esercitare una `aggregation` di intervalli
disgiunti oppure una `intersection` di vincoli indipendenti, quindi mostrare
come ispezionare, confermare e materializzare i nuovi candidati. Il DSL v2
finale deve avere collezioni `intervals` non vuote; il GEXF dinamico deve
contenere almeno uno `<spell>` di nodo e uno di arco ed essere validato sia XSD
sia semanticamente. Un risultato finale con zero spell non soddisfa questo
laboratorio.

L'assenza di `temporal_interval` dallo schema dei candidati AI non va aggirata
inventando un record type: l'AI puo' individuare un'affermazione temporale, ma
la promozione descritta qui resta candidate-first attraverso il servizio
temporale governato. Se neppure l'adapter puo' raggiungere questo risultato
senza violare il contratto corrente, trattalo come blocco funzionale, fermati e
chiedi indicazioni; non simulare marcatori nel DSL o nel GEXF.

`build_orione_assistenza_fixtures.py` deve rigenerare deterministicamente i
formati binari senza rete. `checksums.json` deve coprire tutte le fonti attive e
le fixture controllate; `inventario_fonti.csv` deve indicare percorso, periodo,
utilita', tipo, azione attesa, SHA-256 e motivazione. Non includere dati
personali reali, credenziali, macro eseguibili o link di rete attivi.

## 4. Percorso deterministico e percorso AI

Le guide e lo script devono accompagnare l'utente dall'inizio alla fine usando
solo comandi pubblici e gli ID realmente restituiti, mai ID indovinati o
segnaposto eseguibili.

Il percorso deterministico deve includere: interprete configurato; directory
temporanea; `init`; `db init`; configurazione conservativa dell'allowlist;
copia byte-identica delle sole fonti attive; checksum prima e dopo; due scan
con secondo scan invariato; `batch consolidate --reconcile`; ispezione degli
artefatti di ogni parser; `run status` e, se necessario, resume da checkpoint.
Spiega che il resume crea una nuova run `retry_of` e puo' ripetere l'intera fase
fallita.

Il percorso AI deve essere autentico e governato:

1. crea e confronta piani `technical_extraction` e
   `domain_interpretation`, quindi usa `list` ed `explain` su evidenze incluse
   ed escluse;
2. costruisce il package dalla selezione interpretativa e fa leggere
   integralmente istruzioni, schema, template, contenuto e manifest;
3. durante la validazione tu stesso devi agire come AI esterna: assimila
   soltanto chunk/frammenti inclusi e produci JSONL ancorato a ID e
   `evidence_text` letterali;
4. esercita tutti i record type ammessi: `fact`, `relation`, `mapping`,
   `conflict`, `question`, includendo explicit, observed, inferred e ambiguous;
5. esegue inbox scan, import, review `show`, `confirm`, `reject`, `correct` con
   idempotency key e merge dei batch; verifica parent `superseded`, replacement
   confirmed, supporto multiplo e skip attesi dei tipi non materializzabili;
6. dimostra che importare un candidato AI non lo rende automaticamente una
   verita' e che un piano stale non va accettato silenziosamente.

Solo dopo il percorso autentico congela una risposta minima ripetibile in
`materiale_di_supporto/fixture_controllate/ai_response_orione_assistenza_controllata.jsonl`.
Etichettala sempre come replay controllato: package, inbox, import, review e
merge sono reali, ma la chiamata a un modello esterno non lo e'. Prima di
usarla, lo script deve verificare che package e riferimenti di evidenza
corrispondano; altrimenti deve proporre di generare un nuovo handoff.

Concludi entrambi i percorsi con review temporale delle sorgenti, promozione
esplicita verso fatti/relazioni, review dei candidati propagati, merge,
reconcile, render DSL schema 1 e 2, diff cross-schema, render ripetuto e
byte/hash stabili, GEXF statico e dinamico con spell verificati, caso
`--strict-orphans` atteso, export log HTML/CSV e UI locale. Per la UI usa solo
le rotte pubbliche `/`, `/runs`, `/runs/<ID>`,
`/logs`, `/rejected-candidates`, `/conflicts`, `/snapshots` e `/diff`; verifica
GET 200, POST non consentito e arresto del solo processo avviato.

## 5. Le due guide

`guida_dsl_manager_cmd_v_01.md` e
`guida_dsl_manager_powershell_v_01.md` devono essere equivalenti nel contenuto,
adatte a principianti assoluti e specifiche per Orione. Riprendi dai manuali
Aurora la chiarezza del modello mentale, del vocabolario, dei confini di
sicurezza, dei risultati attesi e della diagnosi, senza copiarne testi o
conteggi.

Per ogni fase indica: scopo, prerequisiti, comando esatto, cosa cambia, output
da conservare, come leggere l'esito, exit code attesi, errore comune e recupero.
Non inserire blocchi con ID fissi. In CMD cura quoting, delayed expansion e
percorsi con spazi; in PowerShell usa il call operator e oggetti JSON quando
possibile. Evita caratteri Unicode gratuiti nei comandi da copiare, ma conserva
correttamente l'italiano UTF-8 nei file e negli output.

## 6. Script PowerShell interattivo

`laboratorio_orione_assistenza_interattivo_v_01.ps1` deve essere la controparte
interattiva della guida PowerShell, non un autopilota. Prima di ogni azione deve
spiegare in modo conciso ma sostanziale dove si trova il processo, perche'
l'azione serve, cosa verra' eseguito e quale risultato attendersi; poi mostra il
comando esatto e offre scelte esplicite come esegui, dettagli, salta quando
sicuro, riprova, torna al menu o esci salvando lo stato.

Requisiti obbligatori dello script:

- individua la root risalendo da `$PSScriptRoot` e valida `AGENTS.md`,
  `pyproject.toml` e `.codex/config.toml`; non codificare il path assoluto della
  macchina;
- legge `PROJECT_PYTHON` da `.codex/config.toml`, risolve il path, verifica
  Python 3.12 e invoca sempre `& $project_python -m dsl_mngr ...`;
- crea sorgenti di lavoro e workspace sotto una directory temporanea univoca,
  separata dal repository; non sovrascrive o cancella una sessione esistente;
- salva nel temporaneo `session_state.json`, `diario_esecuzione.md` e
  `commands.log`, includendo timestamp, comando, stdout, stderr, exit code, ID
  estratti e decisioni dell'utente; permette di riprendere una sessione;
- usa path derivati da `$PSScriptRoot`, controlla l'esistenza di ogni input e
  mantiene una sola forma canonica dei path Windows, senza mescolare nomi 8.3
  ed espansi;
- cattura e analizza gli output strutturati quando disponibili; propaga
  dinamicamente `RUN_*`, `REV_*`, `AISEL_*`, `AIPKG_*`, `CBATCH_*`, `CREC_*` e
  `DSL_*`; non sostituisce un errore di parsing con un ID presunto;
- separa azioni read-only e mutanti, chiede conferma almeno prima delle fasi
  mutanti e non modifica mai il repository o il database con SQL diretto;
- per l'handoff AI apre o indica tutti i file del package, mette la sessione in
  pausa persistente e consente: risposta AI reale fornita dall'utente, replay
  controllato chiaramente etichettato oppure uscita e ripresa successiva;
- dopo la review temporale delle sorgenti, individua dagli output reali i fatti
  e la relazione bersaglio, spiega la policy scelta, invoca il leaf pubblico o
  `promuovi_temporalita_orione_assistenza.py`, mostra i candidati temporali
  prodotti e guida l'utente nella loro conferma/rifiuto prima del nuovo render;
- ispeziona il DSL v2 per intervalli non vuoti e il GEXF dinamico per spell di
  nodo e arco, mostrando bounds e controllo di contenimento invece di limitarsi
  a verificare che i file esistano;
- avvia la UI con `Start-Process -WindowStyle Hidden -PassThru`, conserva il PID,
  usa loopback e una porta disponibile, verifica le rotte esatte e chiude in un
  `finally` soltanto quel processo;
- emette e legge UTF-8 in modo esplicito e mantiene leggibili accenti e dati del
  corpus senza affidarsi alla code page del terminale.

Nei passaggi critici non limitarti a stampare «errore». Proponi alternative
sicure e motivate per: interprete/config mancante; checksum discordante;
workspace gia' presente; batch con checkpoint; piano AI stale; risposta AI
assente o invalida; nessun candidato pending; `--strict-orphans` intenzionale;
porta UI occupata; worker Docling lento; timeout; lock Windows transitorio.
Per Docling mostra tempo trascorso e timeout configurato: il default osservato
e' 300 s con hard maximum 600 s, ma rileggi la configurazione corrente. Offri
attesa, ispezione e resume; non aumentare automaticamente il limite. Un retry
deve essere limitato e consapevole, mai un ciclo infinito. Se nessuna alternativa
pubblica e' sicura, salva lo stato, indica gli artefatti diagnostici e termina
senza perdere il lavoro.

## 7. Validazione e consegna

Esegui il laboratorio completo in un workspace temporaneo nuovo seguendo prima
la guida e poi verificando lo script interattivo. Non usare il corpus o un
workspace Aurora. Non accedere alla rete, non eseguire macro e non adeguare gli
expected a posteriori soltanto per farli coincidere con l'output.

La validazione minima deve dimostrare: tutti i parser/formati esercitati; hash
immutati; secondo scan invariato; percorsi deterministico e AI completi; almeno
una conferma, un rifiuto e una correzione; supporto multiplo; decisioni temporali
positive, negative e pending; promozione temporale esplicita e governata su
almeno due fatti e una relazione; `intervals` DSL v2 non vuoti; spell GEXF di
nodo e arco con bounds validi; output log/UI; fallimenti intenzionali
riconosciuti come tali; ripresa di sessione e nessun path assoluto negli
artefatti pubblicati.

Compila `checklist_risultati_attesi.md` e `matrice_fixture_attesi.md` a partire
dal contratto semantico progettato, poi registra risultati reali, scostamenti e
workaround in `diario_tecnico_validazione.md`. `limitazioni_intenzionali.md`
deve distinguere limiti del corpus, limiti pubblici dell'applicazione e
simulazioni controllate.

Prima della risposta finale esegui una verifica documentale dei link relativi,
dei file elencati, dei checksum, della codifica UTF-8, della sintassi PowerShell
e del diff. Preserva ogni modifica preesistente nel worktree. Nella consegna
riporta l'albero creato, il workspace temporaneo usato, gli esiti E2E, le
limitazioni oneste e ogni blocco ancora aperto.
