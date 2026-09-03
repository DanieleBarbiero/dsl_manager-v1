# Modifica slice v2

>2026/09/03


Verifica GitHub senza effettuare push reali:\ngh auth status\ngit remote -v\ngit ls-remote origin HEAD\ngit push --dry-run origin HEAD:refs/heads/codex/github-connection-test

----

esamina i file:\n\n- <root>\.kb\documenti\documenti di design\run 2\design\_document\_v\_02.md\n- <root>\.kb\prompt\prompt\_slicing\_dsl-manager.md\n\nti spiego brevemente il mio dubbio: durante la run 1, usavo un prompt di produzione delle slice simile all'attuale in combinazione con il design\\_document\\_v\\_01.md per creare i prompt di implementazione delle singole slice. i dettagli venivano decisi durante questo processo.\n\nil design v2, invece, è stato creato con a bordo i prompt delle slice, apparentemente "completi e pronti all'uso". mi consiglieresti di procedure con il vecchio sistema (rischiando una improbabile ma comunque possibile reinterpretazione del testo) o di estrapolare direttamente le slice dal document v2 ed eseguirle?

----

# Raccomandazione

Ti consiglio di **estrarre direttamente i prompt delle slice 20–29 dal design v2 e usarli come fonte normativa**, senza rigenerarli con il vecchio prompt di slicing.

Non li eseguirei però “alla cieca”: adotterei un processo di **estrazione meccanica + verifica preliminare just-in-time**, senza riscrittura creativa. In altre parole:

1. estrarre il prompt incorporato nel design v2;
2. salvarlo nel consueto file della slice;
3. aggiungere soltanto il contesto operativo indispensabile e non ambiguo;
4. prima dell’implementazione, verificare dipendenze, report precedenti e stato corrente del worktree;
5. non reinterpretare o ampliare il perimetro funzionale già deciso dal design.

## Perché non userei il vecchio sistema

Il prompt di slicing attuale non è semplicemente un formatter: chiede al modello di **costruire un nuovo prompt** a partire dal template, dal design, dai report precedenti e dal codice corrente. Di conseguenza introduce inevitabilmente un ulteriore passaggio interpretativo.

Inoltre, allo stato attuale è ancora esplicitamente vincolato al **design v1**, non al v2.  Usarlo senza modificarlo sarebbe quindi non soltanto ridondante, ma formalmente scorretto per le slice 20–29.

Il template sul quale si appoggia è volutamente generico e contiene numerosi placeholder — capability, operazioni, persistenza, interfacce e vincoli — che devono essere nuovamente riempiti dal modello.  Questo era sensato quando il design v1 richiedeva una fase separata di concretizzazione; ora aumenterebbe soprattutto il rischio di:

- omettere un requisito già definito;
- cambiare involontariamente un confine di slice;
- spostare una funzione nella slice sbagliata;
- attenuare una condizione di fallimento;
- inventare dettagli incompatibili con il contratto complessivo;
- produrre differenze terminologiche tra design e prompt operativo.

Il passaggio generativo avrebbe ancora qualche vantaggio — soprattutto incorporare lo stato aggiornato dei report e del codice — ma quel vantaggio può essere conservato con una verifica preliminare, senza rigenerare il contenuto normativo.

# Perché il design v2 è diverso

Il design v2 dichiara esplicitamente di fornire un prompt completo per ogni slice tra i propri obiettivi. {line\_range\_start=44 line\_range\_end=55 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Soprattutto, il documento non presenta i prompt come semplici bozze:

> I prompt seguenti sono completi, pronti all’uso e costituiscono parte normativa del perimetro di ciascuna slice.

Questa qualifica è esplicita nel documento. {line\_range\_start=829 line\_range\_end=831 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md } Anche l’autoverifica certifica che tutti i prompt sono privi dei placeholder del template e pronti all’uso. {line\_range\_start=810 line\_range\_end=826 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Rigenerarli significherebbe quindi creare una **seconda versione derivata di un testo già normativo**. In caso di differenze, non sarebbe chiaro se prevalga:

- il corpo del design;
- il prompt incorporato;
- oppure il nuovo prompt prodotto dal vecchio processo.

È un’ambiguità evitabile.

## I prompt incorporati sembrano realmente operativi

Non sono semplici riassunti del piano. Per esempio, il prompt della slice 20 contiene già:

- prerequisiti documentali e operativi;
- obiettivo verticale;
- perimetro obbligatorio;
- CLI precise;
- vincoli negativi;
- test minimi;
- definition of done;
- istruzione di dichiarare i file prima di modificare il codice;
- esecuzione di test mirati e completi;
- produzione del report di slice. {line\_range\_start=833 line\_range\_end=858 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questo soddisfa sostanzialmente la funzione che nella run 1 veniva svolta dal generatore basato sul template. Il design fornisce inoltre, separatamente, una matrice di tracciabilità che associa requisiti, slice, migrazioni, test e criteri di accettazione. {line\_range\_start=677 line\_range\_end=710 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md } Quindi i prompt non sono isolati: sono collegati a un contratto verificabile.

# Procedura concreta consigliata

## 1. Estrazione fedele

Per ogni slice, estrarrei **letteralmente** il contenuto sotto:

```
### Prompt Slice NN
```

fino all’intestazione della slice seguente, salvandolo in:

```
.kb/projects/slicing/slice_NN/dsl_manager_slice_NN_prompt.md
```

Non farei parafrasi, compressioni o “miglioramenti” semantici durante l’estrazione.

## 2. Rendere esplicito il riferimento al design

Una volta separato, nel prompt della slice 20 la frase “questo documento v02” non identifica più necessariamente il file originario. Il prompt richiede infatti di leggere integralmente il design, ma usa quel riferimento contestuale. {line\_range\_start=835 line\_range\_end=837 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Aggiungerei quindi in testa una sola indicazione meccanica, per esempio:

````
Fonte normativa di questo prompt:
`.kb/documenti/documenti di design/run 2/design_document_v_02.md`

In caso di conflitto:
1. istruzioni di sistema/AGENTS.md applicabili;
2. design v02;
3. report delle slice precedenti;
4. documentazione legacy.
````

Questo non modifica il contenuto della slice: elimina soltanto un’ambiguità introdotta dall’estrazione.

## 3. Conservare il design come autorità

Il file estratto dovrebbe essere considerato una **vista operativa** del design, non una nuova specifica indipendente.

Se durante l’implementazione emerge un conflitto:

- il prompt estratto non va “aggiustato” silenziosamente;
- si verifica prima il passaggio corrispondente nel design;
- si registra l’eventuale scostamento nel report della slice;
- se la modifica è realmente una decisione progettuale, si aggiorna prima il documento normativo e poi si riestrae il prompt.

Questo evita il drift tra specifica e istruzioni operative.

## 4. Preflight just-in-time prima di ogni slice

Qui conserverei la parte migliore del vecchio processo: la verifica dello stato reale.

Prima di eseguire la slice `NN`, l’agente dovrebbe controllare:

- `AGENTS.md`;
- il design v2 completo;
- il prompt estratto;
- i report esplicitamente richiesti dal prompt;
- i report di tutte le dipendenze dirette;
- il codice e i test correnti;
- working tree e modifiche non correlate;
- disponibilità dell’interprete e delle dipendenze;
- presenza delle fixture e dei documenti nominati;
- eventuali scostamenti tra quanto previsto e quanto realmente consegnato dalle slice precedenti.

Questo è particolarmente importante perché il design stabilisce un ordine rigoroso e dipendenze specifiche tra le slice. {line\_range\_start=776 line\_range\_end=790 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md }

La verifica preliminare deve però produrre una delle seguenti conclusioni, non una riscrittura automatica:

1. **pronta** — si esegue il prompt;
2. **pronta con gap documentato** — si esegue entro il perimetro, annotando il gap;
3. **bloccata da dipendenza** — non si reinventa la dipendenza dentro la slice corrente;
4. **contraddizione normativa** — si corregge il design/prompt alla fonte prima dell’esecuzione.

## 5. Validare il prompt senza rigenerarlo

Prima di passarlo all’agente implementatore, farei un controllo deterministico:

- nessun placeholder `<...>`;
- numero slice corretto;
- percorso del report corretto;
- dipendenze nominate disponibili;
- nessuna sottoslice aggiunta;
- test obbligatori presenti;
- out-of-scope presente;
- definition of done presente;
- riferimento esplicito al design v2;
- assenza di riferimenti accidentali al design v1 come autorità prevalente, salvo quando il v1 è richiesto come baseline;
- rispetto dell’ordine delle slice.

Il design stesso afferma che la v1 rimane baseline concettuale, ma la v2 la sostituisce per review, merge eligibility, viste effettive, Excel, temporalità, DSL v2 e GEXF dinamico. {line\_range\_start=24 line\_range\_end=40 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} È quindi importante non lasciare che il vecchio generatore rimetta implicitamente il v1 al centro.

# Un punto operativo da correggere con cautela

I prompt incorporati contengono talvolta istruzioni ambientali come l’uso dell’interprete indicato da `.codex/config.toml`. Per esempio, ciò appare nel prompt della slice 20. {line\_range\_start=835 line\_range\_end=838 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Queste istruzioni non dovrebbero essere riscritte arbitrariamente al momento dell’estrazione. Devono essere interpretate sotto le regole dell’`AGENTS.md` applicabile all’ambiente corrente. Quindi:

- in VS Code/Windows si usa il `PROJECT_PYTHON` configurato;
- nell’ambiente cloud si usa il Python selezionato dal cloud;
- la regola ambientale superiore prevale sulla formulazione generica incorporata nel prompt.

Questo è un esempio di **adattamento operativo legittimo**, distinto da una reinterpretazione del perimetro funzionale.

# Decisione finale

La strategia che adotterei è:

> **Design v2 come source of truth; prompt incorporati estratti senza parafrasi; preflight contestuale prima di ogni esecuzione; nessuna rigenerazione tramite il vecchio prompt.**

Userei nuovamente un generatore di prompt soltanto in uno di questi casi:

- il design contiene solo un piano e non un prompt eseguibile;
- viene aggiunta una slice non contemplata dal design;
- una slice viene formalmente riprogettata;
- il prompt incorporato presenta placeholder o lacune sostanziali;
- il worktree reale diverge tanto dal design da richiedere una revisione progettuale esplicita.

Nel caso attuale non vedo queste condizioni: il documento dichiara esattamente dieci slice, assegna dipendenze e criteri di accettazione, e considera i prompt completi e normativi. {line\_range\_start=812 line\_range\_end=826 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Controlli eseguiti per questa valutazione

- ✅ `wc -l '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `wc -l '.kb/prompt/prompt_slicing_dsl-manager.md'`
- ✅ `rg -n '^#{1,6} ' '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `rg -n '^#{1,6} ' '.kb/prompt/prompt_slicing_dsl-manager.md'`
- ✅ `nl -ba '.kb/prompt/prompt_slicing_dsl-manager.md'`
- ✅ `nl -ba '.kb/template/template_slice.md'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '714,832p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '829,861p'`

Non sono stati modificati file: questa è stata esclusivamente un’analisi documentale, quindi non sono stati creati commit o pull request.

----

confronta una o più slice interne al design v2 con un ipotetico prompt di slice v1 (prodotto dal prompt di slicing).
\ncosa manca? se ci sono una serie di modifiche che devo eseguire sul prompt v2 prima di eseguirlo, preferirei sapere con precisione quali sono. l'obiettivo è che i prompt slice v2 si comportino funzionalmente come i prompt slice v1: non vorrei scoprire di aver lasciato indietro qualcosa quando sono alla slice 27.

----

# Valutazione sintetica

Ho confrontato i prompt v2 incorporati con diversi prompt realmente prodotti durante la run 1, in particolare:

- Slice 10, per normalizzazione Docling;
- Slice 12, per parser e persistenza di evidenza;
- Slice 16, per orchestrazione batch;
- Slice 17, per export GEXF.

La conclusione è:

> **I prompt v2 sono semanticamente più forti e più precisi dei prompt v1, ma sono meno completi come “contratto operativo di esecuzione”.**

Non sembrano mancare feature essenziali delle slice 20–29. Manca invece uno **strato comune di execution governance** che nella run 1 veniva aggiunto dal processo di slicing: lettura esplicita dei file, controllo anti-drift, regole di test, report basato sul template, `git diff --check`, stato finale, gestione delle deviazioni e verifica delle CLI pubbliche.

Quindi **non rigenererei le slice v2 con il vecchio prompt**, ma non le eseguirei nemmeno esattamente come sono. Prima aggiungerei a tutte un wrapper operativo comune e correggerei alcuni riferimenti ambigui.

---

# 1. Che cosa fornivano i prompt v1

## 1.1 Erano molto più auto-contenuti

Il prompt della Slice 10 non si limitava a indicare il risultato desiderato. Elencava esplicitamente:

- `AGENTS.md`;
- design v1;
- template del report;
- tutti i report delle slice precedenti;
- stato introdotto da ogni slice;
- comando CLI esatto;
- compatibilità con `python -m dsl_mngr`;
- file e directory suggeriti;
- artefatti attesi;
- comportamento di fallimento;
- verifiche nel database;
- vincoli;
- fixture;
- procedura finale.

Anche la conclusione era fortemente operativa: installazione editable, suite completa, diff, interprete usato, autoverifica e report costruito tramite il template.

Il prompt v2 della Slice 23 copre molto meglio la sicurezza OOXML e i casi limite tecnici, ma li condensa in pochi paragrafi. {line\_range\_start=892 line\_range\_end=906 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} È completo se l’agente legge realmente l’intero design; è meno robusto se viene trattato come prompt standalone.

## 1.2 Verificavano esplicitamente la baseline reale

I prompt v1 contenevano un riepilogo di ciò che ogni slice precedente aveva consegnato. Per esempio, la Slice 12 descriveva lo stato delle slice 1–11 e chiariva una decisione architetturale importante: non creare candidati sintetici soltanto per aggirare il vincolo di `facts.first_candidate_record_id`.

La parte finale chiedeva inoltre test end-to-end molto concreti:

- inizializzazione workspace e DB;
- esecuzione tramite CLI;
- compatibilità `python -m dsl_mngr`;
- verifica dei file;
- verifica delle righe nel registro;
- stabilità degli hash;
- idempotenza;
- assenza di regressioni.

I prompt v2 chiedono correttamente di ispezionare il worktree e i componenti interessati, ma non sempre impongono un confronto formale fra:

1. design previsto;
2. report delle dipendenze;
3. codice realmente presente;
4. test realmente presenti.

Questo è il principale rischio di scoprire un gap alla Slice 27.

## 1.3 Imponevano invarianti operativi trasversali

Per esempio, i prompt v1 prescrivevano frequentemente:

- path relativi;
- import assoluti da `dsl_mngr`;
- niente rete;
- niente contenuto sorgente lungo nei log;
- separazione fra CLI, core, worker e persistence;
- nessuna dipendenza nuova senza motivazione;
- test con `tmp_path`;
- compatibilità `python -m dsl_mngr`;
- nessuna modifica ai contratti pubblici precedenti.

La Slice 17 contiene esplicitamente questi vincoli e conclude imponendo install editable, test mirati, suite completa, `git diff --check`, diff/status nel report e autoverifica finale.

Il design v2 contiene molte di queste regole a livello globale — determinismo, assenza di rete, compatibilità legacy e suite completa — ma non le ripete sistematicamente dentro ogni prompt. {line\_range\_start=776 line\_range\_end=790 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

---

# 2. Che cosa non manca nei prompt v2

È importante distinguere omissioni operative da omissioni funzionali.

## 2.1 Perimetro funzionale

Il perimetro funzionale è coperto molto bene. Il design assegna a ogni slice:

- obiettivo;
- dipendenze;
- capacità consegnata;
- migrazione;
- fixture;
- artefatti. {line\_range\_start=90 line\_range\_end=103 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## 2.2 Tracciabilità

La matrice di tracciabilità associa requisiti, decisioni, slice, schema, test e criterio di accettazione. {line\_range\_start=677 line\_range\_end=710 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questa è persino migliore rispetto alla run 1: permette di verificare sistematicamente che nessun requisito resti senza test.

## 2.3 Test funzionali e negativi

I prompt v2 non contengono soltanto happy path. Per esempio:

- Slice 20: race, idempotenza, no-op, crash, correzione, strict merge e supporti multipli. {line\_range\_start=841 line\_range\_end=858 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}
- Slice 23: `.xlsx`, `.xlsm`, traversal, ZIP bomb, DTD, entity, relationship invalide, timeout e limiti. {line\_range\_start=894 line\_range\_end=906 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}
- Slice 26: migrazioni, temporalità, DSL v1/v2, hash, XSD, packaging, no-network e fallimento atomico. {line\_range\_start=942 line\_range\_end=958 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}
- Slice 27: conflitti, precisione, timezone, intervalli multipli, cross-schema diff, retry e fake AI. {line\_range\_start=960 line\_range\_end=976 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Non vedo quindi una feature macroscopica dimenticata che debba essere nuovamente progettata.

---

# 3. Che cosa manca davvero

Di seguito distinguo fra modifiche **obbligatorie**, **fortemente consigliate** e **specifiche di singole slice**.

# 3.1 Modifiche obbligatorie per tutte le slice 20–29

## A. Percorsi documentali espliciti

I prompt v2 usano espressioni come:

- “design v02”;
- “analisi tecnica”;
- “contratti”;
- “manuale”;
- “documento metadata chat”;
- “proposta temporale”;
- “materiale candidati”.

Quando il prompt è estratto dal design, questi riferimenti diventano ambigui.

Sostituiscili con percorsi precisi:

```
.kb/documenti/documenti di design/run 2/design_document_v_02.md
.kb/documenti/documenti di design/run 1/design_document_v_01.md
.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md
.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md
.kb/documenti/manuali/manuale_utente_dsl_manager.md
.kb/documenti/documenti di design/run 2/materiale di supporto/dsl_manager_estensione_temporalita_semantica_v_01.md
.kb/documenti/documenti di design/run 2/materiale di supporto/analisi_presenza_funzione_candidati_deterministici.md
.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_01.md
.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_02.md
.kb/documenti/chat/quanto possiamo fidarci dei metadati dei file.md
```

Questo è particolarmente necessario per la Slice 26, che cita genericamente “documento metadata chat”, “proposta temporale” e “contratti”. {line\_range\_start=942 line\_range\_end=945 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## B. Template del report

I prompt v2 ordinano di produrre un report, ma non impongono esplicitamente:

```
.kb/template/template_slice_report.md
```

I prompt v1 lo leggevano e richiedevano di usarlo.

Aggiungi a ogni prompt:

````
Leggi `.kb/template/template_slice_report.md` prima di iniziare.

Salva una copia del report finale in
`.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`,
seguendo integralmente `.kb/template/template_slice_report.md`.
````

Il semplice verbo “Produci” presente nei prompt v2 non garantisce equivalenza con la run 1.

## C. Controllo anti-drift prima di implementare

Aggiungi:

````
Prima di modificare codice, confronta:
1. il comportamento richiesto da design v02 e da questo prompt;
2. i report delle slice da cui questa slice dipende;
3. il codice corrente sotto `src/dsl_mngr`;
4. i test correnti sotto `tests`;
5. schema e migrazioni effettivamente presenti;
6. comandi e opzioni esposti dall'attuale `--help`.

I report sono contesto storico, non prova dello stato corrente.
Se report, design, codice o test divergono, considera autorevoli nell'ordine:
AGENTS.md applicabile, design v02, prompt della slice, contratti aggiornati,
codice/test correnti come stato osservato. Non colmare silenziosamente un gap
di una slice precedente dentro la slice corrente: documentalo e determina se
blocca l'obiettivo verticale.
````

Questo è coerente con il design stesso, che avverte che report e test delle slice 01–19 non provano che il worktree corrente sia verde. {line\_range\_start=28 line\_range\_end=40 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## D. Verifica esplicita delle dipendenze

Aggiungi a ogni prompt:

````
Prima dell'implementazione verifica che tutte le dipendenze dichiarate nella
matrice delle slice siano realmente presenti e funzionanti. Per ogni dipendenza
registra nel report:
- report letto;
- capacità richiesta;
- evidenza nel codice/test;
- eventuale gap;
- decisione: pronta, gap non bloccante oppure bloccata.
````

Il design stabilisce un ordine rigoroso. {line\_range\_start=776 line\_range\_end=778 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} Senza questo gate, una lacuna nella Slice 23 potrebbe emergere soltanto nella 24 o 25, e una lacuna nelle effective views potrebbe emergere nella 26–27.

## E. Procedura completa di test e chiusura

Aggiungi una sequenza standard:

````
Procedura obbligatoria:
1. mostra `git status --short --branch` prima delle modifiche;
2. dichiara i file che prevedi di toccare;
3. installa il progetto in editable mode con extra dev usando l'interprete
   previsto da AGENTS.md per l'ambiente corrente;
4. esegui un baseline test mirato prima delle modifiche, quando praticabile;
5. implementa soltanto il perimetro della slice;
6. esegui prima i test mirati della slice;
7. esegui poi l'intera suite;
8. esegui `git diff --check`;
9. mostra `git status --short` e il diff finale;
10. esegui un'autoverifica contro design, scope, non-obiettivi, test,
    tracciabilità e definition of done;
11. salva il report tramite il template, riportando comandi esatti,
    interprete, risultati, file modificati, migrazioni, gap e fuori scope.
````

Questa procedura riporta i prompt v2 al comportamento dei prompt v1. La parte relativa a test mirati, suite completa, diff e autoverifica era esplicita, per esempio, nella Slice 17.

## F. Compatibilità della CLI pubblica

Aggiungi:

````
Per ogni comando CLI nuovo o modificato:
- testa l'invocazione tramite entry point `dsl-manager`;
- testa o verifica anche l'equivalente `python -m dsl_mngr`;
- confronta esempi e opzioni con `--help`;
- non cambiare i contratti pubblici legacy salvo richiesta esplicita del design;
- verifica exit code, stdout/stderr e assenza di traceback per errori attesi.
````

La compatibilità con `python -m dsl_mngr` era quasi sistematica nei prompt v1; la Slice 17 la include direttamente nei comandi e nei test.

Nei prompt v2 questo controllo è esplicito soprattutto nella Slice 29, ma dovrebbe essere applicato fin dalla Slice 20. {line\_range\_start=996 line\_range\_end=1010 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## G. Regole trasversali su test e filesystem

Aggiungi:

````
Regole trasversali:
- i test devono usare workspace temporanei (`tmp_path`) e non dipendere dallo
  stato locale dell'utente;
- nessuna rete nei test o nel runtime per input locali;
- nessuna chiamata AI reale;
- non memorizzare path assoluti negli artefatti condivisibili o negli hash
  semantici;
- non memorizzare contenuti sorgente lunghi nei log;
- usa import assoluti da `dsl_mngr`, mai da `src`;
- mantieni separati CLI, core/service, worker, persistence e test;
- non aggiungere dipendenze runtime se non richieste o motivate;
- non aggiornare golden/fixture soltanto per rendere verde un test: ogni modifica
  deve derivare da un cambiamento di contratto esplicito;
- preserva modifiche preesistenti non correlate.
````

Il design contiene già alcune di queste invarianti globali, inclusi no-network, determinismo e path non semantici. {line\_range\_start=120 line\_range\_end=138 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}{line\_range\_start=780 line\_range\_end=790 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} Inserirle nel wrapper evita però che vengano perse quando si opera sul solo prompt estratto.

## H. Report delle deviazioni

Aggiungi:

````
Non sostituire silenziosamente dipendenze, algoritmi, versioni o formati richiesti.
Se un requisito non è implementabile:
- non introdurre un fallback non autorizzato;
- conserva gli artefatti diagnostici consentiti;
- documenta requisito, evidenza, comando riproduttivo e impatto;
- indica chiaramente se la slice è completata, parziale o bloccata.
````

Questo comportamento è già indicato per `.xlsm` nella Slice 23, ma deve essere generale. {line\_range\_start=900 line\_range\_end=906 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

---

# 3.2 Modifiche fortemente consigliate

## I. Checklist di tracciabilità per slice

Prima dell’implementazione, estrai dalla tabella di tracciabilità tutte le righe della slice corrente e copiale nel prompt o in una checklist allegata.

Per esempio, per la Slice 27 devono essere recuperate almeno:

- precisione e timezone;
- fonti multiple;
- più intervalli/spells;
- cross-schema diff;
- AI confinata all’handoff. {line\_range\_start=699 line\_range\_end=710 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Aggiungi:

````
Prima del codice, costruisci una checklist requisito → implementazione prevista
→ test previsto usando tutte le righe della sezione 17 assegnate alla slice.
Alla fine aggiorna la stessa checklist con file, test ed esito.
Una riga non verificata impedisce di dichiarare la slice completa.
````

Questa è probabilmente la misura più efficace contro il rischio specifico che temi: arrivare alla Slice 27 e scoprire una capacità dimenticata.

## J. Elenco degli artefatti contrattuali

I prompt v1 indicavano frequentemente i path esatti degli artefatti e i record DB attesi. Nei prompt v2, alcuni path sono nel design generale ma non nel prompt incorporato.

Aggiungi per ogni slice una breve tabella:

````
| Artefatto/record | Produttore | Path/tabella | Schema/versione | Hash | Caso failure |
````

Questo non deve inventare nuovi path: deve estrarli dalle sezioni normative del design.

## K. Test “nessuna regressione”

Aggiungi:

````
La suite completa deve dimostrare anche l'assenza di regressioni sulle capacità
precedenti. Non limitarti a verificare che i nuovi test passino.
````

I prompt v1 lo dicevano spesso esplicitamente; per esempio, la Slice 10 richiedeva nessuna regressione sulle slice 1–9.

## L. Verifica di packaging/installazione

Particolarmente per Slice 23, 24 e 26:

````
Esegui almeno una verifica dall'installazione editable e una verifica delle
risorse tramite `importlib.resources`; i test non devono funzionare soltanto
perché vengono eseguiti dalla root del repository.
````

La Slice 26 già richiede packaging e SHA degli XSD, ma conviene rendere esplicito che deve funzionare come pacchetto installato. {line\_range\_start=950 line\_range\_end=956 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md }

---

# 4. Correzioni specifiche per singola slice

## Slice 20

### Problema 1: istruzione sull’interprete troppo legata a un ambiente

Il prompt dice di usare l’interprete indicato da `.codex/config.toml`. {line\_range\_start=835 line\_range\_end=838 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} Questo è corretto in VS Code/Windows, ma non in Codex cloud secondo l’`AGENTS.md`.

Sostituisci con:

````
Usa Python 3.12 e l'interprete previsto da `AGENTS.md` per l'ambiente corrente:
`PROJECT_PYTHON` da `.codex/config.toml` soltanto in VS Code/Windows; il runtime
selezionato dall'ambiente in Codex cloud. Usa lo stesso interprete per install,
test e comandi di verifica.
````

### Problema 2: baseline molto ampia, ma senza esito strutturato

Leggere tutti i report 01–19 è corretto per questa slice, perché modifica il cuore del merge. Aggiungi però una tabella nel report:

````
| Area legacy | Report rilevanti | Codice verificato | Test verificati | Compatibilità |
````

In particolare: candidati, merge, DSL render, diff, GEXF, batch e migrazioni.

---

## Slice 21

Il prompt legge i report 12–14 e 20, che sono le dipendenze tecniche principali. {line\_range\_start=860 line\_range\_end=874 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} È ragionevole non leggere tutti i report 01–20 integralmente, ma aggiungerei:

````
Leggi anche i report 05 e 06 per i contratti originali di candidate import e
merge, e il report 15 per verificare che la derivazione deterministica non
entri nel percorso AI.
````

Non è necessario ampliare il perimetro; serve soltanto a verificare i confini.

---

## Slice 22

La Slice 22 è il punto nel quale il rischio di regressione è più alto perché modifica un orchestratore già introdotto dalla Slice 16.

Il prompt v2 legge correttamente report 16, 20 e 21. {line\_range\_start=876 line\_range\_end=890 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md } Aggiungerei:

````
Prima di modificare l'orchestratore:
- inventaria tutti i comandi e i core già orchestrati dalla Slice 16;
- registra i contratti di parent/sub-run, process_report e batch_report;
- verifica che i percorsi legacy restino invariati quando derive/review/reconcile
  non sono configurati;
- aggiungi test di compatibilità per almeno un batch legacy.
````

Il prompt v1 della Slice 16 proteggeva esplicitamente i contratti di normalize, chunk, parser, AI package, validation, merge, render e diff.  Il prompt v2 dovrebbe ereditare esplicitamente questa protezione.

---

## Slice 23

### Problema 1: terminologia “conversione diretta”

Il piano parla di “conversione diretta comprovata” per `.xlsm`. {line\_range\_start=734 line\_range\_end=738 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} Il prompt, correttamente, vieta conversioni e fallback e richiede l’inoltro diretto a Docling come XLSX. {line\_range\_start=898 line\_range\_end=906 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Per evitare equivoci, aggiungi:

````
Nel design, “conversione diretta” significa esclusivamente elaborazione diretta
da parte di Docling tramite stream, senza pre-conversione del file, rinomina,
LibreOffice, Excel, openpyxl come normalizzatore sostitutivo o altro fallback.
````

### Problema 2: compatibilità del percorso legacy

Aggiungi:

````
Testa che i formati già supportati da `corpus normalize` conservino il proprio
comportamento e che il nuovo routing Excel non catturi estensioni o content type
legacy.
````

### Problema 3: pubblicazione atomica

Il prompt la richiede, ma il report dovrebbe elencare esplicitamente quali artefatti possono esistere dopo ogni tipo di errore.

---

## Slice 24

Aggiungi un gate che impedisca di creare un secondo parser OOXML:

````
Prima del codice individua e documenta le API del preflight Slice 23 che saranno
riusate. Se non sono estendibili senza duplicazione, considera il problema un
gap della Slice 23 e documenta la minima correzione compatibile; non creare un
parser parallelo.
````

Il prompt lo dice già in forma breve. {line\_range\_start=910 line\_range\_end=918 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} Il gate esplicito impedisce che questa indicazione venga aggirata per comodità.

Aggiungerei inoltre:

````
Verifica roundtrip di installazione/package e checksum dei binari fixture prima
di aggiornare qualsiasi golden.
````

---

## Slice 25

Il rischio è che “fatti tecnici” diventino accidentalmente semantica di dominio.

Aggiungi una matrice obbligatoria nel report:

````
| Regola | Segnale osservabile | Candidato prodotto | Auto-policy consentita | Ambiguità → pending |
````

Per ogni regola deve essere dimostrato che:

- usa manifest/fragments, non Markdown Docling;
- conserva locator;
- non interpreta label o valori;
- non conferma automaticamente strutture ambigue.

Questi vincoli sono già nel prompt, ma una matrice verificabile rende il comportamento più simile ai prompt v1 dettagliati. {line\_range\_start=924 line\_range\_end=938 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

---

## Slice 26

Questa è la slice più densa e quella per cui il prompt v2 ha maggiore bisogno di una checklist strutturata.

Aggiungi obbligatoriamente cinque checklist separate:

1. migrazione e rollback;
2. temporal evidence/review/intervallo;
3. DSL v1/v2 e diff;
4. GEXF/XSD/semantic validation;
5. packaging/no-network/hash.

Il prompt attuale comprime tutti questi domini in una singola lista di test. {line\_range\_start=942 line\_range\_end=958 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Aggiungi inoltre:

````
Non dichiarare completa la slice se una delle cinque verticalità è soltanto
implementata unitariamente ma non provata nel percorso end-to-end:
evidenza → candidato → decisione → intervallo → DSL v2 → GEXF.
````

E:

````
Verifica esplicitamente che schema v1 e GEXF statico restino byte/semanticamente
compatibili secondo i golden legacy applicabili.
````

---

## Slice 27

Questa è la slice nella quale il tuo timore è maggiormente fondato.

### Problema 1: AI opzionale ambigua

Il prompt dice:

> “Se integri generazione AI…”

{line\_range\_start=966 line\_range\_end=974 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questo può indurre un agente a implementare una feature non necessaria oppure, al contrario, a omettere un test previsto dalla tracciabilità.

Sostituisci con:

````
L'integrazione AI è fuori dal percorso minimo e non deve essere aggiunta se non
esiste già un seam che richieda adattamento per la temporalità. In ogni caso
aggiungi un test di confinamento con fake adapter/handoff candidato, senza rete
e senza scrittura diretta nel registro autoritativo.
````

Così distingui:

- implementazione AI: opzionale/non richiesta;
- prova del confine architetturale: obbligatoria.

La matrice di tracciabilità assegna infatti alla Slice 27 il test di AI candidate handoff. {line\_range\_start=706 line\_range\_end=710 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

### Problema 2: enorme perimetro

Aggiungi sottogate interni, non nuove slice:

````
Implementa e valida nell'ordine:
A. estrattori e raw evidence;
B. correlazione/indipendenza/conflitto;
C. precisione/timezone;
D. multi-intervallo e propagation policies;
E. DSL/GEXF;
F. batch/reconcile/retry;
G. cross-schema diff;
H. golden e fake-AI boundary.

Ogni sottopasso deve lasciare test mirati verdi prima del successivo, ma non
costituisce una nuova slice e non deve essere committato o dichiarato completo
isolatamente se la verticalità finale non passa.
````

### Problema 3: dipendenze incomplete

Oltre ai report 16–17 e 26, aggiungerei almeno i report 20 e 22:

- 20 per review/effective views/reconcile;
- 22 per batch derive/review/merge;
- 26 per temporalità core.

Senza rileggere 20 e 22, la Slice 27 potrebbe integrare la temporalità in batch senza verificare i contratti originari.

---

## Slice 28

Aggiungi un inventario “prima/dopo” obbligatorio:

````
Prima di modificare il corpus, registra path, dimensione e SHA-256 di ogni
fixture binaria esistente. Dopo le modifiche, mostra la stessa tabella e spiega
ogni file aggiunto, sostituito o rimosso.
````

E:

````
Non adattare i golden a output inattesi senza prima classificare la differenza
come cambiamento previsto dal design oppure regressione.
````

Il prompt già vieta di nascondere difetti runtime dentro la slice corpus. {line\_range\_start=978 line\_range\_end=994 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

---

## Slice 29

Aggiungi:

````
Non usare soltanto i report come fonte dello stato consegnato. Per ogni capacità
documentata verifica almeno un simbolo/API/schema/comando nel codice e almeno
un test corrispondente. Se report, codice e test divergono, documenta il
comportamento realmente verificato e registra il gap.
````

Questo rafforza una regola che il prompt già suggerisce: documentare le capacità realmente consegnate, non quelle soltanto previste. {line\_range\_start=996 line\_range\_end=1010 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

---

# 5. Wrapper comune pronto da aggiungere

Questa è la modifica minima che applicherei **in coda a ogni prompt estratto**, adattando `<NN>` e l’elenco delle dipendenze.

````
## Protocollo operativo obbligatorio

### Autorità e riferimenti

Leggi integralmente e applica:
- `AGENTS.md`;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
- `.kb/template/template_slice_report.md`;
- i documenti e i report nominati nel prompt, usando i loro path completi;
- il codice corrente sotto `src/dsl_mngr`;
- i test correnti sotto `tests`.

In caso di conflitto, applica nell'ordine:
1. istruzioni di sistema e `AGENTS.md` applicabile;
2. design v02;
3. questo prompt di slice;
4. contratti e documentazione aggiornata;
5. design v01 e report storici.

Il design v01 resta baseline legacy soltanto dove il design v02 non lo
sostituisce. I report sono evidenza storica, non prova dello stato corrente.

### Preflight anti-drift

Prima di modificare codice:
1. mostra `git status --short --branch`;
2. verifica nel codice e nei test tutte le dipendenze dichiarate della slice;
3. confronta design, report delle dipendenze, schema DB, CLI `--help`,
   artefatti e test correnti;
4. compila una checklist con tutte le righe della sezione 17 del design v02
   assegnate alla Slice <NN>;
5. classifica eventuali gap come non bloccanti o bloccanti;
6. non implementare silenziosamente feature appartenenti a slice precedenti o
   successive;
7. dichiara i file che prevedi di toccare.

### Implementazione e compatibilità

- Implementa soltanto il minimo incremento verticale della Slice <NN>.
- Preserva i contratti pubblici e le modalità legacy salvo modifica
  esplicitamente richiesta dal design v02.
- Per CLI nuove o modificate verifica sia `dsl-manager` sia
  `python -m dsl_mngr`.
- Usa import assoluti da `dsl_mngr`, mai da `src`.
- Mantieni separati CLI, core/service, worker, persistence e test.
- Non salvare path assoluti o dati operativi instabili negli output semantici.
- Non effettuare rete o chiamate AI reali nei test.
- Non modificare golden o fixture soltanto per far passare i test.
- Preserva modifiche non correlate presenti nel worktree.

### Installazione e verifiche

1. usa l'interprete previsto da `AGENTS.md` per l'ambiente corrente;
2. installa il progetto con:
   `python -m pip install -e ".[dev]"`
   usando quell'interprete;
3. esegui i test mirati della Slice <NN>;
4. esegui l'intera suite;
5. verifica le CLI interessate tramite `--help`;
6. esegui `git diff --check`;
7. mostra `git status --short` e il diff finale;
8. esegui un'autoverifica contro:
   - perimetro;
   - non-obiettivi;
   - invarianti;
   - matrice di tracciabilità;
   - test obbligatori;
   - compatibilità legacy;
   - determinismo;
   - failure mode;
   - definition of done.

### Report

Salva una copia del report finale in:
`.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`

Usa integralmente:
`.kb/template/template_slice_report.md`

Il report deve includere almeno:
- stato preesistente e controllo anti-drift;
- file modificati;
- migrazioni;
- API e comandi;
- artefatti e relativi schema/hash;
- checklist di tracciabilità;
- comandi esatti eseguiti e interprete;
- esito test mirati, suite completa e `git diff --check`;
- deviazioni, gap e fallback;
- funzionalità volutamente fuori scope;
- stato finale: completata, parziale o bloccata.
````

# 6. Verdetto finale

## Puoi usare direttamente i prompt v2?

**Sì, dopo aver aggiunto il wrapper operativo.**

## Devi rigenerarli col vecchio sistema?

**No.** Il vecchio generatore reintrodurrebbe interpretazione e usa ancora esplicitamente il design v1.

## C’è una carenza progettuale grave?

**Non ne ho trovata una evidente.** Il design v2 copre perimetro, test, tracciabilità e dipendenze in modo sostanzialmente più rigoroso della run 1. La sua autoverifica dichiara esplicitamente che ogni slice dispone di perimetro, dipendenze, migrazione/schema, fixture, artefatti, test, accettazione e prompt collegato. {line\_range\_start=810 line\_range\_end=826 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Qual è il rischio reale?

Il rischio non è tanto “una feature dimenticata nel design”, quanto:

1. riferimento documentale ambiguo dopo l’estrazione;
2. mancato controllo dello stato reale delle dipendenze;
3. report non conforme al template;
4. mancata verifica sistematica della matrice di tracciabilità;
5. assenza di `git diff --check`, diff/status e autoverifica;
6. mancata verifica della compatibilità CLI e legacy;
7. interpretazione ambigua dell’AI opzionale nella Slice 27;
8. accumulo silenzioso di gap fra Slice 20, 22, 26 e 27.

Con il wrapper comune e le correzioni specifiche sopra, i prompt v2 avrebbero il contenuto normativo del nuovo design e la disciplina operativa dei prompt v1.

## Controlli documentali eseguiti

- ✅ `find .kb/projects/slicing -maxdepth 2 -type f \( -name '*_prompt.md' -o -name '*_report.md' \) | sort`
- ✅ `find .kb/projects/slicing -maxdepth 2 -type f -name '*_prompt.md' -print0 | sort -z | xargs -0 wc -l`
- ✅ `rg -n '^#{1,6} |^[0-9]+\\. |^- \\[[ xX]\\]' .kb/projects/slicing/slice_{01,10,12,15,17,19}/dsl_manager_slice_*_prompt.md`
- ✅ `nl -ba '.kb/projects/slicing/slice_10/dsl_manager_slice_10_prompt.md'`
- ✅ `nl -ba '.kb/projects/slicing/slice_12/dsl_manager_slice_12_prompt.md'`
- ✅ `nl -ba '.kb/projects/slicing/slice_16/dsl_manager_slice_16_prompt.md'`
- ✅ `nl -ba '.kb/projects/slicing/slice_17/dsl_manager_slice_17_prompt.md'`
- ✅ `rg -n 'template_slice_report|git diff|tmp_path|python -m dsl_mngr|suite completa|test mirati|autoverifica' '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `find .kb/documenti -maxdepth 4 -type f | sort`
- ✅ `find .kb/template -maxdepth 2 -type f -print | sort`

Non sono stati modificati file; di conseguenza non sono stati creati commit o pull request.

----

io ti proporrei quanto segue, poi mi dici se è okay, poi eventualmente eseguiamo.
- implementiamo tutte le modifche che hai proposto, e includiamo (non so se l'ho vista) una relativa alla produzione del report.
- io leggerei tutti i report storici, senza limitazioni. il lavoro girerà su vs code, dove l'ai dovrebbe poter beneficiare del context buider.
- la questione sull'usare questa o quella configurazione dovrebbe già essere risolta da AGENTS.md, ma mi va bene una ridondanza. però il comportamento deve essere identico a quello attuale (che ha dimostrato di funzionare), non voglio che il processo si rompa a causa di una aggiunta opzionale.
- non teniamo i prompt slice nel design v2, le salviamo su quella che è in effetti la loro destinazione finale, ossia:
- <root>\.kb\projects\slicing\slice\_<NN>\dsl\_manager\_slice\_<NN>\_prompt.md
- e nella stesso folder, a creazione avvenuta: dsl\_manager\_slice\_<NN>\_report.md
- estrai i pezzi di prompt slice dal design v2 in maniera determinista (es. uno script python), per non correre rischi. poi li modifichi in base alle tue raccomandazioni, poi salvi i prompt slice v2, creando gli appositi folder slice\\_\<NN> e poi i file.
- sotto il folder .kb, crea un file 'modifica\\_prompt\\_slice\\_v2.md' e inserisci tutte le modifiche da te proposte nella tua precedente risposta. il file ti servirà da guida e da verifica durante il processo.
- come si diceva, discutiamone, e poi si parte.

----

# Valutazione della proposta

La proposta è **corretta e migliorerebbe il processo**. Procederei in quella direzione, con alcune precisazioni per evitare tre rischi:

1. perdere la provenienza deterministica dei prompt dopo averli modificati;
2. lasciare collegamenti e dichiarazioni obsolete nel design v2;
3. trasformare le nuove regole operative in comportamenti opzionali che alterino il flusso già collaudato.

La soluzione che consiglio è:

> **estrazione deterministica del nucleo dei prompt → aggiunta deterministica di un protocollo operativo comune → aggiunte specifiche per slice → verifica automatica → rimozione dei prompt incorporati dal design → sostituzione con collegamenti ai file canonici.**

---

# 1. Implementare tutte le modifiche proposte

Sono d’accordo.

Includerei esplicitamente la parte relativa alla **produzione del report**, che nei prompt v2 attuali è presente soltanto in forma abbreviata: ogni prompt ordina di produrre il file nel percorso della slice, ma non impone di leggere e utilizzare `template_slice_report.md`. Per esempio, il prompt della Slice 20 indica il path del report, ma non il template. {line\_range\_start=833 line\_range\_end=858 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Ogni prompt 20–29 dovrà quindi contenere almeno:

````
Prima di iniziare, leggi integralmente:

- `.kb/template/template_slice_report.md`

Al termine del task, salva una copia completa del report in:

`.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`

Usa `.kb/template/template_slice_report.md` come struttura obbligatoria del report.
Non creare un report vuoto o preventivo prima dell'implementazione.

Il report deve descrivere almeno:

- stato iniziale e controllo anti-drift;
- file modificati;
- migrazioni e compatibilità;
- comandi e API introdotti o modificati;
- test mirati e suite completa;
- comando e risultato di `git diff --check`;
- interprete Python effettivamente utilizzato;
- diff e stato finale;
- checklist di tracciabilità;
- deviazioni rispetto al design;
- gap rilevati;
- funzionalità volutamente fuori scope;
- stato finale: completata, parziale o bloccata.
````

Il comportamento così torna equivalente a quello della run 1, dove il prompt richiedeva espressamente di salvare il report usando il template.

## Importante: i report non vanno creati ora

Durante la preparazione dei prompt creeremo:

```
.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md
...
.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md
```

Creeremo anche le directory `slice_20`–`slice_29`, ma **non creeremo in anticipo**:

```
dsl_manager_slice_<NN>_report.md
```

Il report dovrà essere creato dall’esecuzione della rispettiva slice, perché deve descrivere attività e risultati realmente avvenuti. Un file preventivo vuoto potrebbe essere scambiato per evidenza di una slice già iniziata o completata.

---

# 2. Leggere tutti i report storici

Sono d’accordo anche su questo.

Ogni prompt dovrà richiedere di leggere **tutti i report precedenti disponibili**, non soltanto quelli delle dipendenze immediate.

Quindi:

- Slice 20: report 01–19;
- Slice 21: report 01–20;
- Slice 22: report 01–21;
- …
- Slice 29: report 01–28.

Questo riproduce il comportamento più conservativo dei prompt v1. Per esempio, il prompt della Slice 17 elenca esplicitamente tutti i report 01–16, oltre al codice e ai test correnti.

## Come evitare che tutti quei report diventino rumore

Aggiungerei una precisa istruzione:

````
Leggi integralmente tutti i report delle slice precedenti in ordine numerico.
Usali per ricostruire la storia implementativa, le deviazioni e i gap noti.

Non assumere però che un report dimostri lo stato corrente del repository:
verifica sempre nel codice, nello schema, negli artefatti e nei test che la
capacità descritta sia ancora presente e coerente.

Prima di modificare codice, produci una sintesi interna ordinata per:
- capacità legacy rilevanti;
- contratti pubblici da preservare;
- migrazioni già applicate;
- deviazioni o gap ancora aperti;
- dipendenze dirette della slice corrente;
- rischi di regressione.
````

Questo rispetta anche l’avvertenza del design v2: i report precedenti sono storia utile, ma non dimostrano che il worktree corrente sia verde. {line\_range\_start=28 line\_range\_end=40 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Elenco esplicito, non wildcard

Per mantenere il comportamento dei prompt v1, inserirei nei prompt i path espliciti:

````
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
...
````

Non userei soltanto:

```
leggi tutti i report precedenti
```

L’elenco esplicito ha tre vantaggi:

- rende immediatamente visibile un report mancante;
- evita errori di zero-padding;
- rende il prompt autosufficiente e verificabile deterministicamente.

Lo script può generare automaticamente l’elenco appropriato per ogni slice.

---

# 3. Interprete e configurazione: nessun cambiamento di comportamento

Concordo: `AGENTS.md` deve restare l’autorità.

La ridondanza nel prompt servirà soltanto a impedire scorciatoie, non a introdurre una nuova selezione dell’interprete.

La formulazione dovrebbe essere:

````
Usa Python 3.12 e segui esattamente le regole di selezione dell'interprete
definite dall'`AGENTS.md` applicabile all'ambiente corrente.

In VS Code su Windows:
- leggi `.codex/config.toml`;
- usa `PROJECT_PYTHON` come unico interprete valido;
- usa lo stesso interprete per pip, install editable, test e comandi Python.

Non introdurre meccanismi alternativi o fallback per scegliere l'interprete.
Non usare il Python globale se `AGENTS.md` non lo consente.
````

Questo preserva il comportamento che ha già funzionato.

## Niente aggiunte opzionali nel protocollo fondamentale

Condivido pienamente questa condizione. Le attività necessarie alla disciplina della slice non saranno espresse come:

- “se opportuno”;
- “preferibilmente”;
- “quando possibile”, salvo casi realmente dipendenti dall’ambiente;
- “puoi eseguire”;
- “valuta se”.

Saranno obbligatorie:

1. lettura dei file;
2. install editable;
3. controllo anti-drift;
4. dichiarazione dei file;
5. implementazione;
6. test mirati;
7. suite completa;
8. `git diff --check`;
9. stato e diff;
10. autoverifica;
11. report.

Le sole eccezioni condizionali dovranno essere tecniche e motivate, per esempio l’uso di un hard memory limit quando la piattaforma lo supporta. Anche in quel caso il design stabilisce già il comportamento alternativo esatto. {line\_range\_start=621 line\_range\_end=625 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md }

---

# 4. Spostare i prompt fuori dal design v2

Sono d’accordo: le destinazioni canoniche devono essere:

```
.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md
...
.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md
```

e, soltanto dopo l’esecuzione:

```
.kb/projects/slicing/slice_20/dsl_manager_slice_20_report.md
...
.kb/projects/slicing/slice_29/dsl_manager_slice_29_report.md
```

## Il design v2 non deve però terminare senza riferimenti

La sezione 22 non andrebbe semplicemente cancellata. La sostituirei con una sezione breve che dichiara i file esterni canonici:

````
## 22. Prompt di implementazione

I prompt di implementazione completi costituiscono parte normativa del
perimetro delle rispettive slice e sono conservati nei seguenti file:

- [Slice 20](../../../projects/slicing/slice_20/dsl_manager_slice_20_prompt.md)
- [Slice 21](../../../projects/slicing/slice_21/dsl_manager_slice_21_prompt.md)
...
- [Slice 29](../../../projects/slicing/slice_29/dsl_manager_slice_29_prompt.md)

Il presente design resta la fonte normativa dei requisiti funzionali e degli
invarianti. I prompt esterni ne costituiscono il contratto operativo di
esecuzione. In caso di conflitto non risolvibile tramite `AGENTS.md`, prevale
il presente design.
````

I percorsi relativi andranno calcolati e verificati con attenzione in base alla posizione effettiva del design.

## Collegamenti nel piano delle slice

Le sezioni 18.1–18.10 contengono collegamenti interni come:

````
[Prompt eseguibile](#prompt-slice-20)
````

Per esempio, ciò è presente nella definizione della Slice 20. {line\_range\_start=716 line\_range\_end=720 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questi collegamenti dovranno essere aggiornati affinché puntino ai nuovi file. Non devono rimanere anchor non risolvibili.

## Aggiornamento dell’autoverifica

L’autoverifica attuale afferma che i prompt sono nel documento, senza placeholder e pronti all’uso. {line\_range\_start=810 line\_range\_end=826 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

La voce dovrebbe diventare qualcosa come:

````
- [x] Tutti i prompt esterni 20–29 sono senza placeholder, pronti all'uso,
      collegati dal design e verificati contro il rispettivo perimetro.
````

Anche l’obiettivo “fornire per ogni slice un prompt completo” resta valido; cambia soltanto la collocazione fisica. {line\_range\_start=44 line\_range\_end=55 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

---

# 5. Estrazione deterministica

La scelta di usare uno script Python è corretta.

Suggerisco di salvare lo script, almeno durante il lavoro, come:

```
.kb/prompt/extract_slice_prompts_v2.py
```

Il nome rispetta le convenzioni del progetto.

## Che cosa deve fare lo script

Lo script deve:

1. leggere il design v2 come UTF-8;
2. individuare esattamente la sezione:

   ```
   ## 22. Prompt di implementazione
   ```
3. trovare esattamente dieci intestazioni:

   ```
   ### Prompt Slice 20
   ...
   ### Prompt Slice 29
   ```
4. rifiutare:

   - slice mancanti;
   - slice duplicate;
   - slice fuori dall’intervallo 20–29;
   - ordine non crescente;
   - blocchi vuoti;
5. estrarre il testo tra un’intestazione e la successiva;
6. normalizzare esclusivamente i newline;
7. non parafrasare, riformattare o correggere il contenuto;
8. scrivere prima in una directory temporanea;
9. rileggere gli output;
10. verificare che ogni nucleo estratto corrisponda al relativo blocco sorgente;
11. pubblicare i file nelle directory finali soltanto se tutte le verifiche passano.

## Separare estrazione e arricchimento

Per rendere l’operazione realmente auditabile, userei due fasi logiche nello script:

```
extract_core_prompt(design, slice_number)
build_final_prompt(core_prompt, common_protocol, slice_amendments)
```

In questo modo potremo distinguere:

- testo estratto dal design;
- protocollo operativo comune;
- integrazioni specifiche della slice.

Il file finale potrebbe contenere commenti Markdown non visibili semanticamente:

````
<!--
Prompt core estratto deterministicamente da:
.kb/documenti/documenti di design/run 2/design_document_v_02.md
Slice: 20
-->

...prompt core...

<!-- protocollo operativo comune v1 -->
...wrapper...

<!-- integrazioni specifiche slice 20 -->
...integrazioni...
````

Non inserirei hash nel prompt finale se lo script deve essere rieseguito più volte e l’hash rischia di diventare autoreferenziale. Registrerei invece gli hash nel documento guida.

## Ordine sicuro dell’operazione

L’ordine deve essere:

1. leggere e validare il design originale;
2. estrarre i dieci nuclei;
3. calcolare gli hash dei nuclei;
4. costruire i dieci prompt finali;
5. verificare i prompt finali;
6. salvare i prompt;
7. verificare che tutti i file esistano;
8. soltanto allora rimuovere i blocchi dal design;
9. sostituire la sezione 22 con i link;
10. aggiornare i link nelle sezioni 18.1–18.10;
11. aggiornare l’autoverifica;
12. verificare nuovamente tutti i riferimenti.

Questo garantisce che non venga cancellata la fonte prima di aver verificato l’estrazione.

---

# 6. Documento guida `modifica_prompt_slice_v2.md`

Sono d’accordo con il percorso:

```
.kb/modifica_prompt_slice_v2.md
```

Il file dovrebbe essere creato **prima** della trasformazione e usato come checklist durante tutto il lavoro.

## Contenuto consigliato

Propongo questa struttura:

````
# Modifica dei prompt delle slice v2

## 1. Obiettivo

## 2. Fonti normative

## 3. Decisioni approvate

## 4. Protocollo operativo comune

## 5. Produzione del report

## 6. Lettura integrale dei report precedenti

## 7. Controllo anti-drift

## 8. Interprete e installazione editable

## 9. Test mirati, suite completa e CLI

## 10. Diff, status e autoverifica

## 11. Regole trasversali

## 12. Modifiche specifiche
### Slice 20
...
### Slice 29

## 13. Procedura di estrazione deterministica

## 14. Procedura di rimozione dal design

## 15. Checklist di verifica
- [ ] dieci nuclei estratti
- [ ] slice 20–29 presenti una sola volta
- [ ] directory create
- [ ] prompt finali creati
- [ ] nessun report creato preventivamente
- [ ] tutti i report precedenti elencati
- [ ] template report richiesto
- [ ] nessun placeholder
- [ ] design aggiornato
- [ ] link aggiornati
- [ ] autoverifica aggiornata
- [ ] `git diff --check`
- [ ] verifica finale dei file
````

Inserirei nel documento tutte le raccomandazioni della risposta precedente, ma le consoliderei eliminando ripetizioni e rendendole prescrittive.

---

# 7. Una modifica alla mia raccomandazione precedente

Cambierei un punto rispetto alla mia risposta precedente: non aggiungerei in tutti i prompt una gerarchia troppo articolata del tipo:

```
AGENTS → design → prompt → contratti → codice
```

Potrebbe creare dubbi nuovi.

Userei invece una regola più netta:

````
- `AGENTS.md` governa ambiente, processo e convenzioni;
- design v02 governa requisiti funzionali, invarianti e confini;
- il prompt della slice governa l'esecuzione operativa della slice;
- codice e test rappresentano lo stato realmente osservato, non possono
  modificare implicitamente il design;
- report e design v01 sono contesto storico, salvo richiami normativi espliciti
  del design v02.
````

In caso di contraddizione non risolvibile:

````
non scegliere silenziosamente una variante; documenta il conflitto e fermati
prima di introdurre una decisione progettuale nuova.
````

Questa formulazione è più sicura.

---

# 8. Attenzione alla directory `.kb` e a Git

C’è un aspetto operativo importante: secondo le istruzioni del progetto, `.kb` è intenzionalmente esclusa da Git.

Di conseguenza:

- i nuovi prompt;
- il documento `modifica_prompt_slice_v2.md`;
- lo script di estrazione;
- la modifica al design v2;

resteranno con ogni probabilità **ignorati da Git**.

Questo è coerente con la policy attuale, ma significa che il lavoro non produrrà normalmente:

- un commit Git;
- una pull request;
- una copia sul repository GitHub.

Prima dell’esecuzione controllerò comunque:

````
git check-ignore -v .kb/modifica_prompt_slice_v2.md
git check-ignore -v ".kb/documenti/documenti di design/run 2/design_document_v_02.md"
````

Non forzerò l’aggiunta con `git add -f`, perché la policy dice di mantenere `.kb` fuori da Git finché non viene esplicitamente cambiata.

---

# 9. Piano operativo definitivo proposto

Quando mi darai il via, procederei così:

1. leggere nuovamente `AGENTS.md`;
2. installare il progetto con il Python 3.12 corretto, come richiesto;
3. verificare lo stato Git e la policy `.gitignore`;
4. creare `.kb/modifica_prompt_slice_v2.md`;
5. riversarvi tutte le decisioni approvate;
6. creare lo script di estrazione;
7. eseguire lo script sul design originale;
8. verificare i dieci nuclei 20–29;
9. aggiungere il protocollo operativo comune;
10. aggiungere tutti i report storici precedenti a ciascun prompt;
11. aggiungere le correzioni specifiche per ogni slice;
12. creare le directory `slice_20`–`slice_29`;
13. scrivere soltanto i file prompt;
14. non creare i report;
15. verificare automaticamente:

    - numerazione;
    - zero-padding;
    - path;
    - placeholder;
    - template report;
    - elenco report;
    - test;
    - diff;
    - autoverifica;
16. rimuovere i prompt incorporati dal design;
17. sostituirli con i link ai file esterni;
18. aggiornare tutti i link “Prompt eseguibile”;
19. aggiornare l’autoverifica del design;
20. eseguire controlli testuali e `git diff --check`;
21. mostrare il diff dei file `.kb` anche se ignorati;
22. produrre un riepilogo preciso di ogni prompt creato.

# Conclusione

La tua proposta è **approvabile senza riserve sostanziali**.

Le sole precisazioni che considero necessarie sono:

- il report deve essere richiesto esplicitamente tramite il template;
- i report finali non devono essere creati ora;
- ogni prompt deve elencare tutti i report precedenti;
- il protocollo operativo deve essere obbligatorio, non opzionale;
- `AGENTS.md` deve conservare integralmente il comportamento attuale dell’interprete;
- estrazione e arricchimento devono essere due fasi distinguibili;
- il design deve conservare link e autorità normativa dopo la rimozione dei prompt;
- la cancellazione dei blocchi dal design deve avvenire soltanto dopo la verifica degli output;
- la natura Git-ignored di `.kb` deve essere rispettata.

Non ho ancora modificato alcun file: come richiesto, questa risposta conclude soltanto la fase di discussione.

----

- d'accordo per modificare design v2 in modo che la sezione dei prompt non venga cancellata ma modificata con una lista di riferimenti ai file dei prompt slice v2\n
- è più pulito usare .kb (quindi okay per la tua proposta), ma , per completezza, dovrei aver aggiornato .gitignore per usare anche .kb. in effetti, il folder .wb è stato aggiunto nello stesso commit, può darsi che tu non lo veda ancora. può darsi che AGENTS.md sia rimasto indietro: nel caso, modificalo per allinearsi allo stato del git.\n
- aggiungerei un punto alla fase E: confrontare ogni prompt slice prodotta con il template storico per il prompt di slicing v1 e verificare che siano identici dal punto di vista funzionale (leggono le stesse cose, eseguono le stesse azioni, ecc.). se poi il prompt v2 fa cose in più, meglio: ma deve fare almeno quello che faceva il v1.\n
- fai un ultimo sommario delle modifiche che hai intenzione di fare e dei successivi test di controllo, ma non avviare ancora la procedura, attendi il mio okay.

----

# Piano definitivo proposto

Non avvio ancora alcuna operazione. Al tuo “okay” eseguirò il lavoro secondo il seguente piano.

## A. Verifica preliminare del repository

Prima di modificare qualsiasi file:

1. leggerò integralmente l’`AGENTS.md` effettivamente presente;
2. controllerò branch, working tree, commit corrente e remote;
3. verificherò se `.kb` e l’eventuale `.wb`:

   - esistono;
   - sono tracciate;
   - sono ignorate;
   - risultano introdotte da commit già presenti localmente;
4. confronterò `.gitignore` con le istruzioni di `AGENTS.md`;
5. installerò il progetto in editable mode con Python 3.12 seguendo esattamente le regole dell’ambiente.

Non presumerò che `.wb` sia un refuso per `.kb`: controllerò entrambe.

### Allineamento di `AGENTS.md`

Modificherò `AGENTS.md` **soltanto se il repository dimostra una contraddizione reale**. In particolare:

- se `.kb` è ora intenzionalmente tracciata o resa tracciabile da `.gitignore`, aggiornerò la regola che attualmente la descrive come intenzionalmente esclusa da Git;
- se `.wb` è una directory distinta e ha una policy propria, la documenterò separatamente;
- non cambierò le altre istruzioni di ambiente, Python, import o naming;
- non interpreterò la sola presenza locale di file ignorati come una nuova policy: cercherò evidenza in `.gitignore`, nello stato Git e nella cronologia disponibile.

L’aggiornamento dovrà descrivere lo stato effettivo senza alterare incidentalmente le altre regole del progetto.

---

# B. Documento guida e checklist

Creerò:

```
.kb/modifica_prompt_slice_v2.md
```

Il documento conterrà:

1. obiettivo della trasformazione;
2. fonti normative;
3. decisioni approvate in questa discussione;
4. protocollo operativo comune;
5. requisiti per la produzione dei report;
6. lettura di tutti i report storici;
7. controllo anti-drift;
8. selezione dell’interprete;
9. installazione editable;
10. test mirati e suite completa;
11. verifica CLI;
12. diff, status e `git diff --check`;
13. modifiche specifiche per Slice 20–29;
14. procedura di estrazione;
15. procedura di aggiornamento del design;
16. verifica di equivalenza funzionale con i prompt v1;
17. checklist finale con stato di ogni controllo.

Il file verrà usato come checklist attiva: non sarà soltanto una copia narrativa delle raccomandazioni.

---

# C. Estrazione deterministica dei prompt

Creerò uno script Python, presumibilmente:

```
.kb/prompt/extract_slice_prompts_v2.py
```

Lo script:

1. leggerà il design v2 originale;
2. individuerà la sezione 22;
3. verificherà la presenza esatta delle Slice 20–29;
4. rifiuterà duplicati, omissioni, ordine errato e blocchi vuoti;
5. estrarrà senza parafrasi il nucleo di ciascun prompt;
6. manterrà separati:

   - nucleo originale;
   - protocollo operativo comune;
   - integrazioni specifiche;
7. genererà gli elenchi zero-padded dei report precedenti;
8. scriverà inizialmente in una directory temporanea;
9. verificherà gli output;
10. pubblicherà i file finali soltanto se tutte le verifiche superano.

Lo script userà Python 3.12 e non richiederà dipendenze aggiuntive.

---

# D. Creazione dei prompt esterni

Creerò le directory:

```
.kb/projects/slicing/slice_20/
...
.kb/projects/slicing/slice_29/
```

e i file:

```
.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md
...
.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md
```

Non creerò preventivamente i report.

Ogni prompt richiederà che, al termine dell’effettiva implementazione, venga creato:

```
.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md
```

usando obbligatoriamente:

```
.kb/template/template_slice_report.md
```

---

# E. Equivalenza funzionale con il processo v1

Aggiungo formalmente il controllo richiesto.

Ogni prompt v2 prodotto sarà confrontato sia con:

```
.kb/template/template_slice.md
```

sia con un campione rappresentativo dei prompt v1 realmente generati, non soltanto con il template astratto.

Questo secondo confronto è importante perché il template storico contiene una struttura minima — letture preliminari, scope, expected behavior, constraints, done criteria e sequenza di esecuzione — ma i prompt v1 prodotti aggiungevano ulteriori regole operative concrete.

Per esempio, i prompt v1 effettivi richiedevano anche:

- template del report;
- tutti i report precedenti;
- codice e test correnti;
- installazione editable;
- test mirati;
- suite completa;
- compatibilità `python -m dsl_mngr`;
- diff;
- `git diff --check`;
- autoverifica;
- descrizione del fuori scope;
- salvataggio del report.

## Matrice di equivalenza

Per ogni Slice 20–29 produrrò una matrice simile a:

| Area funzionale | Template v1 | Prompt v1 reali | Prompt v2 | Esito |
| --- | --- | --- | --- | --- |
| Legge `AGENTS.md` | sì | sì | sì | conforme |
| Legge design completo | sì | sì | sì | conforme |
| Legge template report | implicito/no | sì | sì | conforme+ |
| Legge tutti i report precedenti | generatore | sì | sì | conforme |
| Ispeziona codice corrente | sì | sì | sì | conforme |
| Ispeziona test correnti | sì | sì | sì | conforme |
| Controllo anti-drift | no | alcune slice | sì | estensione |
| Dichiara file previsti | sì | sì | sì | conforme |
| Install editable | tramite AGENTS | sì | sì | conforme |
| Implementa scope minimo | sì | sì | sì | conforme |
| Aggiunge/aggiorna test | sì | sì | sì | conforme |
| Test mirati | non sempre | slice mature | sì | conforme+ |
| Suite completa | sì | sì | sì | conforme |
| Verifica entry point CLI | generico | sì | sì | conforme |
| Verifica `python -m dsl_mngr` | non esplicito | sì | sì | conforme |
| `git diff --check` | no | slice mature | sì | conforme+ |
| Mostra diff/status | diff | sì | sì | conforme |
| Autoverifica finale | implicita | sì | sì | conforme |
| Report tramite template | esterno | sì | sì | conforme |
| Elenca fuori scope | sì | sì | sì | conforme |
| Documenta gap/deviazioni | no | parziale | sì | estensione |
| Matrice di tracciabilità | no | no | sì | estensione |

## Regola di accettazione

Un prompt v2 sarà accettato soltanto se:

> per ogni comportamento operativo presente nel template v1 o nei prompt v1 maturi, il prompt v2 contiene un requisito equivalente o più forte.

Le aggiunte v2 sono ammesse e desiderate, purché:

- non contraddicano il design;
- non allarghino il perimetro della slice;
- non rendano opzionali attività prima obbligatorie;
- non cambino l’interprete;
- non introducano nuovi fallback;
- non spostino feature fra slice.

## Controllo automatico e controllo semantico

La verifica avrà due livelli.

### Controllo automatico

Lo script verificherà la presenza di elementi come:

- `AGENTS.md`;
- design v2 con path completo;
- `template_slice_report.md`;
- path del report finale;
- tutti i report precedenti;
- `src/dsl_mngr`;
- `tests`;
- install editable;
- test mirati;
- suite completa;
- `python -m dsl_mngr`;
- `git diff --check`;
- diff e status;
- autoverifica;
- gap e fuori scope;
- zero placeholder;
- numero slice e path coerenti.

### Controllo semantico

Rileggerò ciascun prompt per verificare che non basti una corrispondenza testuale. Per esempio:

- non sarà sufficiente nominare `git diff --check`: dovrà essere richiesto come azione;
- non sarà sufficiente nominare il template report: dovrà essere obbligatorio usarlo;
- non sarà sufficiente citare i report: dovrà essere richiesto di leggerli integralmente;
- non sarà sufficiente nominare la suite: dovrà essere richiesto di eseguirla dopo i test mirati;
- non sarà sufficiente citare una CLI: dovranno essere controllati entry point, `python -m dsl_mngr`, exit code e `--help`;
- non sarà sufficiente citare il worktree: dovrà essere controllato prima e dopo.

Questo evita falsi positivi nel confronto.

---

# F. Protocollo operativo comune

A ogni prompt verrà aggiunto un protocollo obbligatorio che prescriverà, senza formulazioni opzionali:

1. lettura integrale di `AGENTS.md`;
2. lettura integrale del design v2;
3. lettura del design v1 dove richiesto come baseline;
4. lettura integrale del template report;
5. lettura integrale di tutti i report precedenti;
6. ispezione di `src/dsl_mngr`;
7. ispezione di `tests`;
8. verifica delle dipendenze dichiarate;
9. confronto fra design, report, codice, schema e test;
10. controllo dello stato Git;
11. dichiarazione dei file previsti;
12. installazione editable con l’interprete stabilito da `AGENTS.md`;
13. implementazione limitata alla slice;
14. test mirati;
15. suite completa;
16. verifica CLI;
17. `git diff --check`;
18. stato e diff finali;
19. autoverifica contro scope, non-obiettivi, tracciabilità e done criteria;
20. produzione del report tramite template.

Il protocollo non cambierà il comportamento dell’interprete già stabilito da `AGENTS.md`.

---

# G. Integrazioni specifiche delle Slice 20–29

Oltre al protocollo comune, inserirò le correzioni specifiche già discusse:

- **Slice 20:** interprete dipendente dall’ambiente; audit completo della baseline 01–19.
- **Slice 21:** verifica esplicita dei contratti candidati, merge e confine con AI.
- **Slice 22:** protezione dei contratti della vecchia orchestrazione batch e test legacy.
- **Slice 23:** chiarimento che “conversione diretta” significa ingresso diretto in Docling, senza pre-conversione o fallback; regressione sui formati legacy.
- **Slice 24:** gate obbligatorio sul riuso del preflight Slice 23; nessun parser OOXML parallelo.
- **Slice 25:** matrice regola → evidenza → candidato → auto-policy → pending.
- **Slice 26:** cinque checklist distinte per migrazione, temporalità, DSL, GEXF e packaging.
- **Slice 27:** sottopassi interni obbligatori; chiarimento che l’implementazione AI non è richiesta, ma il test del confine fake-AI è obbligatorio.
- **Slice 28:** inventario prima/dopo e SHA-256 delle fixture; divieto di adattare i golden a regressioni.
- **Slice 29:** verifica delle capacità nel codice e nei test, non soltanto nei report.

---

# H. Aggiornamento del design v2

Solo dopo avere creato e verificato i dieci prompt:

1. sostituirò il contenuto esteso della sezione 22 con l’elenco dei riferimenti ai prompt esterni;
2. manterrò la sezione 22 nel documento;
3. aggiornerò i collegamenti “Prompt eseguibile” delle sezioni 18.1–18.10;
4. aggiornerò l’indice se necessario;
5. aggiornerò l’autoverifica;
6. dichiarerò:

   - design v2 = autorità funzionale;
   - prompt esterno = contratto operativo;
   - `AGENTS.md` = autorità per ambiente e convenzioni;
7. verificherò che nessun anchor interno obsoleto rimanga.

Attualmente il piano di ogni slice punta a un anchor interno, per esempio la Slice 20. {line\_range\_start=714 line\_range\_end=720 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md} Questi riferimenti saranno trasformati in link ai file canonici.

---

# I. Controlli finali previsti

## Controlli Python e progetto

- `python --version` con l’interprete stabilito da `AGENTS.md`.
- `python -m pip install -e ".[dev]"`.
- `python -m pytest` dopo le modifiche, perché saranno modificati almeno documentazione, prompt e probabilmente script Python.
- Test mirati dello script di estrazione, se verranno aggiunti test automatizzati.
- Esecuzione dello script in modalità verifica/idempotenza.

## Controlli sui prompt

Per ogni Slice 20–29:

- directory corretta;
- filename zero-padded;
- numero slice corretto;
- report path corretto;
- template report presente;
- tutti i report 01–`NN-1` presenti e ordinati;
- design v2 presente con path esplicito;
- codice e test correnti richiesti;
- controllo anti-drift richiesto;
- install editable richiesta;
- test mirati richiesti;
- suite completa richiesta;
- entry point e `python -m dsl_mngr` richiesti;
- `git diff --check` richiesto;
- diff/status richiesti;
- autoverifica richiesta;
- fuori scope e gap richiesti;
- nessun placeholder;
- nessuna istruzione opzionale che indebolisca il processo;
- nessun requisito appartenente a una slice successiva;
- tutte le righe della matrice di tracciabilità coperte.

## Controlli sul design

- sezione 22 ancora presente;
- dieci riferimenti 20–29;
- tutti i link risolvibili;
- nessun vecchio anchor `#prompt-slice-NN`;
- indice coerente;
- autoverifica aggiornata;
- nessun blocco prompt residuo incorporato;
- design ancora leggibile autonomamente.

## Controlli Git

- `git status --short --branch`
- `git check-ignore -v` sui nuovi file `.kb`
- `git diff --check`
- `git diff -- .gitignore AGENTS.md`
- diff esplicito dei file `.kb`, se tracciati;
- ricerca di modifiche estranee;
- verifica finale che non siano stati creati report preventivi.

Se i file risultano tracciabili e vengono prodotti cambiamenti versionati, completerò il flusso con commit sul branch corrente e creazione della pull request. Se `.kb` risultasse ancora intenzionalmente ignorata, non forzerò il tracking senza una base esplicita nella policy aggiornata.

---

# Stato attuale

Non ho ancora:

- modificato file;
- creato directory;
- eseguito lo script;
- aggiornato `AGENTS.md`;
- aggiornato `.gitignore`;
- creato commit;
- creato pull request.

Attendo il tuo **okay** prima di avviare la procedura.