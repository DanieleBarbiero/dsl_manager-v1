# Modifica slice v2

>2026/09/02

----

esamina i file:
- <root>\.kb\documenti\documenti di design\run 2\design\_document\_v\_02.md
- <root>\.kb\prompt\prompt\_slicing\_dsl-manager.md

ti spiego brevemente il mio dubbio: durante la run 1, usavo un prompt di produzione delle slice simile all'attuale in combinazione con il design\\_document\\_v\\_01.md per creare i prompt di implementazione delle singole slice. i dettagli venivano decisi durante questo processo.
il design v2, invece, è stato creato con a bordo i prompt delle slice, apparentemente "completi e pronti all'uso". mi consiglieresti di procedure con il vecchio sistema (rischiando una improbabile ma comunque possibile reinterpretazione del testo) o di estrapolare direttamente le slice dal document v2 ed eseguirle?

----

## Raccomandazione

Ti consiglio di **estrapolare direttamente i prompt delle slice 20–29 dal design v2 ed eseguirli nell’ordine previsto**, senza rigenerarli tramite il vecchio prompt di slicing.

In questo caso, una nuova fase generativa non aggiungerebbe valore sostanziale: introdurrebbe soprattutto un ulteriore punto nel quale il testo normativo potrebbe essere riassunto, reinterpretato oppure accidentalmente contraddetto.

## Perché sceglierei l’estrazione diretta

### 1. Il design v2 dichiara esplicitamente normativi i prompt incorporati

Il documento non presenta i prompt come esempi o bozze. Dice espressamente che sono:

- completi;
- pronti all’uso;
- parte normativa del perimetro di ciascuna slice. {line\_range\_start=829 line\_range\_end=831 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Anche l’autoverifica del design afferma che tutti i prompt sono privi di placeholder e pronti per essere eseguiti. {line\_range\_start=810 line\_range\_end=825 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questo cambia la natura del workflow rispetto alla run 1: nella run 1 il prompt di slicing doveva **produrre** una specifica operativa; nella run 2 quella specifica è già stata prodotta e incorporata nel documento normativo.

### 2. Il vecchio prompt di slicing è ancora configurato per il design v1

Il prompt attuale ordina esplicitamente di leggere:

- il template generico;
- `design_document_v_01.md`;
- i report precedenti;
- il codice e i test correnti.

Non indica il design v2 come fonte primaria e non stabilisce la sua precedenza sul v1. Usarlo invariato per le slice 20–29 sarebbe quindi pericoloso: il generatore potrebbe costruire il nuovo prompt partendo dalla baseline sbagliata proprio negli ambiti in cui il v2 sostituisce il v1.

Il design v2 è molto chiaro su questa gerarchia:

- v1 rimane la baseline concettuale;
- v2 prevale per review, merge eligibility, effective views, Excel, temporalità, DSL v2 e GEXF dinamico. {line\_range\_start=24 line\_range\_end=26 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questi non sono dettagli marginali: costituiscono quasi tutto il contenuto delle slice 20–29.

### 3. I dettagli tecnici sono già stati allocati alle singole slice

Il design v2 non contiene soltanto una roadmap ad alto livello. Per ciascuna slice assegna:

- dipendenze;
- perimetro;
- migrazione o schema;
- artefatti;
- test;
- criterio di accettazione;
- prompt eseguibile collegato.

L’autoverifica dichiara esplicitamente questa copertura. {line\_range\_start=812 line\_range\_end=825 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md }

Per esempio, il prompt della slice 20 contiene già:

- obiettivo verticale;
- migrazione v7;
- API e CLI;
- concurrency e idempotenza;
- correzione e lineage;
- effective views;
- merge mixed/strict;
- backfill;
- prima regola di derivazione;
- esclusioni;
- test minimi;
- Definition of Done. {line\_range\_start=833 line\_range\_end=858 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Quindi non si tratta di brevi descrizioni da trasformare in prompt: sono già prompt operativi.

### 4. Una seconda generazione potrebbe alterare la ripartizione intenzionale del lavoro

Il design stabilisce un ordine preciso:

`20→21→22→23→24→25`, quindi 26 dopo 22, 27 dopo 26, 28 dopo 23–27 e infine 29. {line\_range\_start=776 line\_range\_end=790 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

I prompt incorporati rispettano questa scomposizione. Ad esempio:

- slice 20 introduce soltanto la prima regola DDL;
- slice 21 completa le altre regole deterministiche;
- slice 22 integra il tutto nel batch;
- slice 23 introduce l’ingest Excel ma non ancora il manifest completo;
- slice 24 costruisce manifest e frammenti;
- slice 25 deriva candidati Excel.

Rigenerare i prompt aumenta il rischio di:

- anticipare funzionalità di una slice successiva;
- perdere un’esplicita esclusione;
- duplicare componenti;
- spostare test o migrazioni;
- trasformare una dipendenza obbligatoria in un’assunzione implicita.

## Procedura che adotterei

### Fase 1 — Estrazione meccanica

Per ogni slice da 20 a 29:

1. estrarrei il testo compreso tra `### Prompt Slice NN` e il successivo heading dello stesso livello;
2. salverei il contenuto in:

   ```
   .kb/projects/slicing/slice_NN/dsl_manager_slice_NN_prompt.md
   ```

3. non parafraserei il testo;
4. non lo farei passare nuovamente attraverso il prompt generativo della run 1.

Questa dovrebbe essere una trasformazione **editoriale/meccanica**, non semantica.

### Fase 2 — Packaging minimo e uniforme

Aggiungerei, se vuoi mantenere esattamente il contratto operativo della run 1, soltanto l’istruzione standard:

```
- salva una copia del report prodotto al termine del task nel file `.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`, usando come template `.kb/template/template_slice_report.md`.
```

Il vecchio prompt richiede esplicitamente questa formulazione.

I prompt v2 indicano già il percorso del report — per esempio quello della slice 20 lo fa nella prima riga — ma non sempre specificano esplicitamente di usare `template_slice_report.md`. {line\_range\_start=833 line\_range\_end=835 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Considererei quindi lecita questa sola aggiunta, perché:

- non cambia il perimetro implementativo;
- non decide nuovi dettagli;
- uniforma solamente il formato del report;
- conserva una convenzione operativa già in uso.

### Fase 3 — Verifica prima dell’esecuzione di ogni slice

Prima di eseguire una slice farei un controllo leggero, senza riscriverne il prompt:

- la slice precedente richiesta esiste ed è completata;
- il relativo report è disponibile;
- i file/documenti nominati dal prompt esistono realmente;
- non ci sono placeholder residui;
- il worktree corrisponde alla baseline attesa;
- le dipendenze tecniche previste dalla slice precedente sono effettivamente presenti;
- il prompt estratto coincide testualmente con quello nel design v2, salvo l’eventuale istruzione standard sul template del report.

Questo è particolarmente importante perché lo stesso design avverte che i report delle slice 01–19 sono storia utile, ma non dimostrano che il worktree corrente sia verde. {line\_range\_start=28 line\_range\_end=38 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md }

### Fase 4 — Esecuzione sequenziale con feedback

Dopo ogni slice:

1. eseguire test mirati e suite completa;
2. produrre il report;
3. confrontare risultato e Definition of Done della slice;
4. risolvere eventuali scostamenti prima di passare alla successiva;
5. usare il report appena prodotto come input della slice seguente, quando richiesto.

Questo mantiene il vantaggio del vecchio processo — l’uso dello stato reale e dei report precedenti — senza rigenerare una specifica già normativa.

## Quando avrebbe senso usare ancora il vecchio sistema?

Lo userei solo se si verificasse almeno una di queste condizioni:

1. **Il prompt incorporato risultasse realmente incompleto**, per esempio citasse una sezione inesistente o lasciasse una decisione essenziale non determinata.
2. **Il worktree fosse divergente dal design** in modo tale da rendere impossibile l’esecuzione letterale.
3. **Una slice precedente avesse introdotto uno scostamento approvato**, che richiedesse di adattare formalmente quelle successive.
4. **Volessi deliberatamente rivedere il design**, anziché implementarlo.
5. **La run 2 includesse nuove slice non comprese tra 20 e 29**, perché il documento dichiara esplicitamente che il suo piano termina con la 29. {line\_range\_start=20 line\_range\_end=22 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L20-L22"}

Anche in questi casi non userei il prompt di slicing attuale così com’è. Ne preparerei una versione v2 che:

- usa `design_document_v_02.md` come fonte normativa primaria;
- usa v1 solo come baseline nei punti non sostituiti;
- legge tutti i report fino alla slice precedente;
- verifica il codice e i test correnti;
- vieta di modificare senza evidenza le decisioni già fissate nel prompt incorporato;
- produce principalmente integrazioni o chiarimenti, non una riscrittura libera.

## Conclusione

La scelta migliore è:

> **estrazione diretta dei prompt v2 + controllo meccanico + eventuale sola aggiunta dell’istruzione sul template del report + esecuzione nell’ordine previsto.**

Non passerei i prompt incorporati attraverso il vecchio generatore. Sarebbe una trasformazione da “specifica già approvata” a “nuova interpretazione della specifica”, senza un beneficio proporzionato.

In sintesi:

| Opzione | Valutazione |
| --- | --- |
| Vecchio prompt invariato | **Sconsigliata**: punta al design v1 e può reinterpretare il v2 |
| Vecchio prompt aggiornato al v2 | Utile solo in caso di gap o divergenze reali |
| Estrazione letterale dal v2 | **Consigliata** |
| Estrazione + istruzione standard sul report | **Soluzione operativa migliore** |
| Esecuzione di tutte le slice senza checkpoint intermedi | Sconsigliata |
| Esecuzione sequenziale con report e suite tra le slice | **Consigliata** |

**Verifiche eseguite**

- ✅ `find .. -name AGENTS.md -print`
- ✅ `wc -l '.kb/documenti/documenti di design/run 2/design_document_v_02.md' '.kb/prompt/prompt_slicing_dsl-manager.md'`
- ✅ `sed -n '1,240p' '.kb/prompt/prompt_slicing_dsl-manager.md'`
- ✅ `sed -n '1,1010p' '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `nl -ba '.kb/prompt/prompt_slicing_dsl-manager.md'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `git status --short` — worktree pulito; non sono state apportate modifiche, quindi non è stato creato alcun commit o pull request.

----

confronta la slice interna al design v2 con un ipotetico prompt di slice v1 (prodotto dal prompt di slicing).
cosa manca? se ci sono una serie di modifiche che devo eseguire sul prompt v2 prima di eseguirlo, preferirei sapere con precisione quali sono. l'obiettivo è che i prompt slice v2 si comportino funzionalmente come i prompt slice v1: non vorrei scoprire di aver lasciato indietro qualcosa quando sono alla slice 27.

----

# Valutazione

Sì: **i prompt incorporati nel design v2 sono tecnicamente molto più completi del template generico**, ma non sono ancora equivalenti, sul piano operativo, ai prompt v1 realmente prodotti dal processo di slicing.

La differenza principale non riguarda il contenuto funzionale delle slice. Il design v2 specifica bene feature, invarianti, migrazioni, test e confini. Ciò che manca è soprattutto il **guscio operativo comune** che nei prompt v1 obbligava l’agente a:

- leggere fonti con percorsi non ambigui;
- verificare lo stato realmente consegnato dalle slice precedenti;
- confrontare design, report, codice e test;
- rilevare e segnalare il drift prima di costruire sopra di esso;
- usare il template del report;
- mostrare `git status`, diff e `git diff --check`;
- documentare test mancanti, falliti o limitati dall’ambiente;
- chiudere esplicitamente il ciclo della slice.

Il rischio concreto non è tanto “arrivare alla slice 27 e scoprire che manca una feature descritta nel design”. Il rischio è arrivarci dopo che una slice precedente è stata **dichiarata completa senza una verifica abbastanza rigorosa del suo stato effettivo**.

---

# 1. Confronto fra i due tipi di prompt

## Prompt v1 prodotto dal processo di slicing

I prompt v1 reali erano generalmente documenti operativi autonomi. Per esempio, la slice 18 ordina esplicitamente di leggere:

- `AGENTS.md`;
- il design v1;
- il template del report;
- tutti i report precedenti;
- il codice corrente;
- i test correnti.

Il prompt esplicita poi:

- contesto implementativo corrente;
- scope;
- expected behavior;
- vincoli;
- test;
- controllo anti-drifting;
- report;
- Definition of Done;
- procedura prima e dopo il codice.

La slice 19 segue la stessa impostazione e rende particolarmente esplicito il controllo anti-drifting tra design e implementazione reale.

## Prompt incorporato nel design v2

I prompt v2 sono invece **specifiche tecniche compatte appoggiate al documento di design**. Il documento dichiara che sono completi, pronti all’uso e normativi. {line\_range\_start=829 line\_range\_end=831 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Ogni prompt v2 contiene generalmente:

1. identificazione e obiettivo della slice;
2. documenti da consultare;
3. vertical slice minima;
4. requisiti tecnici;
5. esclusioni;
6. test obbligatori;
7. Definition of Done.

Ad esempio, la slice 20 è già molto dettagliata sul perimetro funzionale. {line\_range\_start=833 line\_range\_end=858 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Quindi:

- **come specifica tecnica**, il v2 è sufficiente;
- **come protocollo operativo autonomo**, gli mancano alcuni controlli presenti nei prompt v1.

---

# 2. Cosa manca in tutti o quasi tutti i prompt v2

## 2.1 Manca il riferimento esplicito al template del report

I prompt v2 indicano il percorso del report, per esempio:

```
Produci `.kb/projects/slicing/slice_20/dsl_manager_slice_20_report.md`.
```

{line\_range\_start=833 line\_range\_end=835 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Ma non ordinano di leggere e usare:

```
.kb/template/template_slice_report.md
```

Il prompt di slicing della run 1 richiedeva esplicitamente di inserire questa istruzione.

Non è una formalità: il template richiede almeno:

- stato della slice;
- modifiche;
- diff/status;
- test e interprete;
- eventuali verifiche aggiuntive;
- elementi fuori scope o note.

E il modello dettagliato chiede anche install editable, comando di test, risultato e verifiche come `git diff --check`.

### Modifica necessaria

Aggiungere a **ogni prompt 20–29**:

```
- leggi `.kb/template/template_slice_report.md`;
- salva una copia del report prodotto al termine del task nel file
  `.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`,
  usando `.kb/template/template_slice_report.md` come template;
- nel report indica almeno stato della slice, file modificati, diff/status,
  interprete, installazione editable, test mirati, suite completa, verifiche
  aggiuntive, scostamenti e contenuto rimasto fuori scope.
```

Questa è una modifica **obbligatoria** se vuoi equivalenza operativa con le slice v1.

---

## 2.2 I riferimenti ai documenti sono descrittivi, non percorsi esatti

I prompt v2 usano espressioni come:

- “analisi tecnica”;
- “contratti”;
- “manuale”;
- “materiale di supporto candidati”;
- “documento metadata chat”;
- “proposta temporale”;
- “documentazione Aurora”.

Per esempio, la slice 20 usa quasi esclusivamente nomi descrittivi. {line\_range\_start=835 line\_range\_end=837 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

La slice 26 fa lo stesso per il documento metadata, la proposta temporale e i contratti GEXF. {line\_range\_start=940 line\_range\_end=944 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Nel repository ci sono però più documenti che possono plausibilmente corrispondere a queste descrizioni:

```
.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md
.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md
.kb/documenti/manuali/manuale_utente_dsl_manager.md
.kb/documenti/chat/formati file e temporalità semantica - produce design per marcatori temporali run 2.md
.kb/documenti/documenti di design/run 2/materiale di supporto/dsl_manager_estensione_temporalita_semantica_v_01.md
...
```

Un agente probabilmente li troverà, ma “probabilmente” non è abbastanza per una catena di dieci slice.

### Modifica necessaria

Sostituire i riferimenti descrittivi con percorsi letterali. Almeno:

```
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md`
- `.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md`
- `.kb/documenti/manuali/manuale_utente_dsl_manager.md`
- `.kb/documenti/documenti di design/run 2/materiale di supporto/analisi_presenza_funzione_candidati_deterministici.md`
- `.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_01.md`
- `.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_02.md`
- `.kb/documenti/documenti di design/run 2/materiale di supporto/dsl_manager_estensione_temporalita_semantica_v_01.md`
- `.kb/documenti/chat/formati file e temporalità semantica - produce design per marcatori temporali run 2.md`
```

Naturalmente non tutte le slice devono leggere tutti questi file: bisogna sostituire ciascun riferimento con il percorso esatto pertinente.

Questa modifica è **obbligatoria**.

---

## 2.3 Manca una regola generale e inequivocabile di precedenza delle fonti

Il design stabilisce che:

- il v1 resta baseline concettuale;
- il v2 lo sostituisce per review, merge eligibility, effective views, Excel, temporalità, DSL v2 e GEXF dinamico. {line\_range\_start=24 line\_range\_end=26 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Solo alcuni prompt, soprattutto 26 e 27, ricordano localmente una regola di precedenza. La slice 26 dice che design/prompt v2 prevalgono sulla proposta di supporto. {line\_range\_start=940 line\_range\_end=944 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Non c’è però una gerarchia completa valida per tutte le slice.

### Modifica necessaria

Aggiungere a ogni prompt:

```
Gerarchia delle fonti:
1. `AGENTS.md` e istruzioni esplicite del task;
2. prompt della presente slice e `design_document_v_02.md`;
3. contratti e documenti tecnici aggiornati;
4. stato effettivo verificato di codice e test;
5. report delle slice precedenti come storia implementativa;
6. `design_document_v_01.md` come baseline concettuale soltanto dove non è
   sostituito dal design v2.

In caso di conflitto, non scegliere silenziosamente: applica la fonte con
precedenza maggiore e documenta il conflitto e la decisione nel report.
```

Questa modifica è **obbligatoria**, soprattutto per evitare che una formulazione legacy torni a prevalere nelle slice 20, 22, 26 o 27.

---

## 2.4 Manca il controllo anti-drifting sistematico prima dell’implementazione

Nei prompt v1 più recenti il controllo era esplicito. La slice 18 ordina di confrontare il design e l’implementazione corrente e di segnalare qualsiasi deviazione.

La slice 19 lo mette addirittura nella procedura prima dell’implementazione.

Nei prompt v2 troviamo formule come:

- “ispeziona il worktree”;
- “ispeziona parser e fixture”;
- “preserva modifiche non correlate”.

Ma non è sempre richiesto di confrontare sistematicamente:

```
design v2 ↔ report precedenti ↔ codice ↔ migrazioni ↔ test
```

Questo è il punto che potrebbe davvero produrre problemi cumulativi fino alla slice 27.

### Modifica necessaria

Aggiungere a ogni prompt:

```
Controllo anti-drifting prima del codice:
- confronta il perimetro e le precondizioni della slice con il design v2;
- verifica nel codice, nelle migrazioni e nei test che le capacità richieste
  dalle slice dipendenti siano realmente presenti;
- non considerare un report prova sufficiente che il worktree sia conforme o verde;
- segnala discrepanze, implementazioni parziali e regressioni già presenti;
- se una precondizione indispensabile manca, non mascherarla implementandola
  incidentalmente fuori scope: documenta il blocco o assegna la correzione alla
  slice proprietaria;
- riporta l’esito del controllo nel report.
```

Questo è coerente anche con il design v2, che avverte esplicitamente che i report 01–19 sono storia utile, non prova che il worktree corrente sia verde. {line\_range\_start=28 line\_range\_end=38 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questa modifica è **obbligatoria**.

---

## 2.5 Non tutti i prompt chiedono di leggere codice e test correnti in modo esplicito

Il prompt di slicing v1 imponeva di leggere l’attuale codice del package e i test.

I prompt v2 spesso dicono “ispeziona il worktree”, “ispeziona parser e fixture” oppure “ispeziona dipendenze”. È ragionevole, ma meno preciso.

La slice 29 menziona esplicitamente “codice/test/report finali 20–28”; altre slice non sempre nominano entrambe le directory. {line\_range\_start=996 line\_range\_end=1000 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

### Modifica necessaria

Aggiungere sistematicamente:

```
- leggi e verifica il codice attuale sotto `src/dsl_mngr`;
- leggi i test attuali sotto `tests`, inclusi fixture e golden pertinenti;
- cerca prima componenti già esistenti e riusabili;
- non assumere che un file, una migrazione, un comando o una API non esista
  senza averlo verificato nel worktree.
```

Questa modifica è **obbligatoria**.

---

## 2.6 I report precedenti non sono sempre letti cumulativamente

Questo è un punto delicato.

I prompt v1 tendevano a leggere tutti i report precedenti. La slice 17 elenca esplicitamente i report 01–16.

La slice 18 legge tutti i report 01–17.

I prompt v2 leggono invece una selezione mirata:

- slice 21: report 12–14 e 20;
- slice 22: report 16, 20 e 21;
- slice 23: report 10–11 e 22;
- slice 24: report 11–14 e 23;
- slice 25: report 20–24;
- slice 26: report 17 e 20–25;
- slice 27: report 16–17 e 26;
- slice 28: report 23–27;
- slice 29: report 20–28.

Questa selezione è sensata per ridurre rumore, ma perde parte della funzione storica del vecchio processo.

Il caso più rischioso è la slice 27: se legge solo i report 16–17 e 26, potrebbe non vedere uno scostamento importante introdotto nelle slice 20–25, pur dipendendo indirettamente da review, batch, Excel e candidate infrastructure. {line\_range\_start=960 line\_range\_end=976 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

### Modifica raccomandata

Non obbligherei necessariamente ogni slice a rileggere integralmente tutti i report 01–NN, perché a quel punto il contesto può diventare eccessivo. Userei questa regola:

```
- leggi integralmente i report esplicitamente indicati come pertinenti;
- consulta inoltre tutti i report dalla Slice 20 fino alla precedente almeno
  per stato, scostamenti, test, problemi aperti e fuori scope;
- se un report segnala regressioni, blocchi o contratti divergenti, leggi
  integralmente anche quel report e quelli da cui dipende;
- i report non sostituiscono la verifica del codice e dei test correnti.
```

Per le slice più integrative userei invece lettura cumulativa completa:

- **slice 22:** report 20–21 completi;
- **slice 25:** report 20–24 completi;
- **slice 26:** report 20–25 completi;
- **slice 27:** report 20–26 completi;
- **slice 28:** report 20–27 almeno per scostamenti; 23–27 integralmente;
- **slice 29:** report 20–28 integralmente.

Questa modifica è **fortemente raccomandata**, soprattutto per 26–29.

---

## 2.7 Manca una gestione uniforme delle precondizioni mancanti

La slice 23 contiene una buona regola specifica: se Docling non supporta realmente `.xlsm`, la slice deve fallire esplicitamente senza introdurre fallback non autorizzati. {line\_range\_start=892 line\_range\_end=906 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

La slice 28 contiene un’altra buona regola: se il corpus rivela un difetto runtime appartenente a una slice precedente, bisogna fermarsi e assegnarlo alla slice proprietaria, anziché espandere il perimetro in modo nascosto. {line\_range\_start=978 line\_range\_end=994 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questa politica dovrebbe essere comune a tutte le slice, non limitata a 23 e 28.

### Modifica necessaria

Aggiungere:

```
Se durante l’implementazione emerge che una precondizione di una slice precedente
manca o viola il contratto:
- non dichiarare la slice completata;
- non introdurre silenziosamente una correzione fuori scope;
- identifica la slice proprietaria del difetto;
- applica una correzione soltanto se è minima, indispensabile e compatibile,
  documentandola esplicitamente;
- altrimenti dichiara la slice bloccata/parziale con evidenza riproducibile;
- non adattare test o golden per nascondere la deviazione.
```

Questa modifica è **obbligatoria** per prevenire accumulo di debito nascosto.

---

## 2.8 Manca una politica uniforme per test falliti, non eseguiti o limitati

La slice 18 v1 specifica che un timeout storico non deve essere nascosto e richiede di riportare:

- comando;
- interprete;
- durata;
- test coinvolto;
- verifica alternativa.

I prompt v2 chiedono test mirati e suite completa, ma non sempre specificano cosa fare quando:

- la suite fallisce per regressione preesistente;
- manca una dipendenza;
- un test va in timeout;
- l’ambiente non può garantire un limite hard;
- una feature esterna non è supportata.

Il design dà indicazioni specifiche per Excel memory limits e `.xlsm`, ma manca una regola generale.

### Modifica necessaria

Aggiungere:

```
Non dichiarare un test passato se non è stato eseguito. Per ogni test fallito,
saltato, interrotto o non eseguibile riporta:
- comando esatto;
- interprete e versione;
- esito/exit code;
- causa osservata;
- se il problema è preesistente, introdotto dalla slice o dovuto all’ambiente;
- verifica mirata alternativa eventualmente eseguita;
- impatto sulla Definition of Done.

La suite completa deve passare per dichiarare la slice completata, salvo un limite
ambientale dimostrato e chiaramente separato da un difetto del codice.
```

Questa modifica è **obbligatoria**.

---

## 2.9 Manca `git diff --check` come gate esplicito

I prompt v1 più maturi richiedevano `git diff --check`; per esempio la slice 17 lo include nella Definition of Done.

Nei prompt v2 si chiede di mostrare diff e risultato dei test, ma non sempre di eseguire:

```
git diff --check
```

### Modifica necessaria

Aggiungere a ogni prompt:

```
Verifiche finali obbligatorie:
- `git status --short`
- `git diff --check`
- `git diff --stat`
- revisione del diff completo pertinente alla slice
```

E aggiungere:

```
Non includere modifiche non correlate e non sovrascrivere cambi preesistenti
dell’utente.
```

I prompt v2 già chiedono spesso di preservare modifiche estranee, ma conviene uniformare il gate finale.

Questa modifica è **obbligatoria** per equivalenza con il workflow v1 maturo.

---

## 2.10 Mancano criteri uniformi per path, log, artifact e separazione architetturale

I prompt v1 dettagliati ripetevano spesso vincoli trasversali come:

- import assoluti da `dsl_mngr`;
- non importare `src`;
- path relativi al workspace;
- evitare contenuti sorgente lunghi nei log;
- mantenere separate CLI, core, persistence e test;
- non aggiungere ORM o dipendenze senza necessità;
- mantenere artifact e report deterministici.

Per esempio, la slice 18 contiene esplicitamente import rules, path rules, separazione del core e divieti infrastrutturali.

Il design v2 copre molte di queste proprietà globalmente, specialmente determinismo, no-network, tracciabilità e compatibilità. {line\_range\_start=776 line\_range\_end=790 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Ma i prompt singoli non le ripetono sempre.

### Modifica raccomandata

Aggiungere un blocco comune:

```
Vincoli trasversali:
- usa import assoluti da `dsl_mngr`; non importare `src` come package;
- mantieni separate CLI, core/domain, persistence, worker e test;
- non introdurre ORM, servizi esterni o dipendenze runtime non previste;
- motiva nel report qualsiasi nuova dipendenza o migrazione;
- usa path relativi al workspace e `/` negli artifact condivisibili;
- non inserire path assoluti, timestamp operativi o ID di run negli hash semantici;
- non salvare contenuti sorgente lunghi o sensibili nei log/report;
- conserva compatibilità pubblica e leggibilità degli artifact storici;
- non modificare migrazioni già applicate; aggiungi migrazioni append-only.
```

Parte di ciò è già in `AGENTS.md` o nel design, quindi la modifica è **raccomandata**, ma è utile per rendere il prompt davvero autonomo.

---

# 3. Problema specifico dell’interprete

Il prompt della slice 20 dice di usare l’interprete indicato in `.codex/config.toml`. {line\_range\_start=835 line\_range\_end=837 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Questa istruzione è valida in VS Code/Windows, ma non in Codex cloud, dove `AGENTS.md` prescrive di usare il runtime cloud e ignorare `.codex/config.toml`.

Non è un difetto del contenuto tecnico, ma rende il prompt meno portabile.

## Modifica necessaria

Sostituire le varianti attuali con una sola formulazione uniforme:

```
Usa Python `>=3.12,<3.13` e il corretto interprete di progetto secondo
`AGENTS.md`:
- in Codex VS Code/Windows, leggi `PROJECT_PYTHON` da `.codex/config.toml`;
- in Codex cloud, usa il runtime Python selezionato dall’ambiente e ignora
  `.codex/config.toml`.

Prima di modificare il codice esegui con tale interprete:

`python -m pip install -e ".[dev]"`

Dopo ogni modifica esegui con lo stesso interprete:

`python -m pytest`
```

Questa modifica è **obbligatoria** per evitare istruzioni contraddittorie tra ambienti.

---

# 4. Modifiche specifiche per alcune slice

## Slice 20

È il prompt v2 più completo. Mancano però:

- percorso letterale di ogni documento;
- template report;
- anti-drift esplicito;
- gestione uniforme dei test falliti;
- `git diff --check`;
- regola di precedenza completa;
- verifica esplicita di codice e test correnti.

Il suo perimetro funzionale, invece, non richiede una nuova generazione: è già sufficientemente specifico. {line\_range\_start=833 line\_range\_end=858 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Slice 21

Aggiungerei esplicitamente:

- lettura del report 20 e verifica nel codice che importer, review service, migration v7 e validator siano realmente presenti;
- controllo che la slice 21 non aggiunga accidentalmente logica batch;
- inventario iniziale delle strutture prodotte dai parser 12–14;
- matrice finale `rule → input schema → evidence locator → candidate type → default review state → policy`.

Il design richiede regole versionate, importer comune, ordinamento, deduplica e rifiuto dei placeholder, quindi la sostanza c’è già. {line\_range\_start=860 line\_range\_end=874 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Slice 22

Aggiungerei un controllo precondizioni esplicito:

```
prima di modificare l’orchestratore, dimostra che le API pubbliche delle slice
20 e 21 esistono e sono coperte dai test;
```

Inoltre farei riportare nel report:

- state transition per ciascuna fase;
- checkpoint persistiti;
- tabella degli exit code;
- confronto degli effective hash fra retry.

Il prompt contiene già il comportamento centrale e i test di crash/retry. {line\_range\_start=876 line\_range\_end=890 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Slice 23

Questa ha già una buona politica di blocco per `.xlsm`. Aggiungerei:

- percorso letterale delle fonti ufficiali o istruzione di usare le URL fissate nella sezione 20;
- registrazione nel report della versione Docling effettivamente importata;
- registrazione del risultato del test reale `.xlsm`;
- distinzione fra hard memory limit e monitored limit;
- checksum dei fixture usati;
- prova esplicita che il path non viene riaperto.

Il design riconosce correttamente che nessuna fonte garantisce da sola il supporto `.xlsm`; il test reale è un gate. {line\_range\_start=792 line\_range\_end=808 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Slice 24

Aggiungerei:

- verifica iniziale che il preflight della slice 23 sia completo e riusabile;
- schema JSON concreto o riferimento esatto alle linee/sezione normativa;
- inventario degli artifact che devono essere pubblicati;
- controllo che i fixture binari non vengano rigenerati accidentalmente;
- report dei checksum prima e dopo.

La slice ha già requisiti tecnici e test molto estesi. {line\_range\_start=908 line\_range\_end=922 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md }

## Slice 25

Aggiungerei nel report una matrice esplicita:

```
regola | input strutturale | evidence locator | candidate type |
auto-review consentita? | ragione
```

Questo rende verificabile il divieto di trasformare celle in semantica di dominio.

Il prompt già vieta fatti di dominio e l’uso di `normalized.md` come fonte primaria. {line\_range\_start=924 line\_range\_end=938 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Slice 26

È una slice molto grande e ad alto rischio. Prima di eseguirla aggiungerei obbligatoriamente:

- verifica completa dello stato delle slice 20–25;
- percorsi esatti per documento metadata, proposta temporale e contratti;
- SHA, URL, commit e licenze delle risorse XSD copiati direttamente nel prompt oppure riferimento inequivocabile alla tabella/sezione;
- inventario delle modifiche consentite a schema v1 e schema v2;
- prova byte-for-byte che snapshot v1 preesistenti non cambiano;
- matrice di compatibilità `schema version × render × diff × export × allow-incomplete`;
- stop condition se review/effective views delle slice 20–22 non corrispondono al contratto.

Il prompt è già ricco, ma comprime DSL v2, persistenza, hashing, temporalità e GEXF dinamico nella stessa slice. {line\_range\_start=940 line\_range\_end=958 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Slice 27

Questa è quella per cui condivido maggiormente la tua preoccupazione.

Il prompt dovrebbe leggere non soltanto 16–17 e 26, ma almeno:

- report 20;
- report 22;
- report 23;
- report 24;
- report 25;
- report 26;

perché integra:

- common review;
- candidate handoff;
- batch;
- reconcile;
- manifest Excel;
- temporal core;
- DSL v2;
- GEXF dinamico.

Il prompt attuale menziona solo report 16–17 e 26. {line\_range\_start=960 line\_range\_end=976 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L960-L976"}

Aggiungerei inoltre una matrice finale obbligatoria:

```
source type
→ raw evidence
→ correlation group
→ candidate
→ review state
→ validated interval
→ effective view
→ DSL v2
→ GEXF spell
```

E chiederei esplicitamente test end-to-end separati per:

- conflitto non promosso;
- segnali correlati non contati due volte;
- timezone unknown;
- intervalli multipli;
- retry in ordine differente;
- AI fake adapter candidate-only.

Questa è la modifica specifica più importante.

## Slice 28

Aggiungerei:

- inventario iniziale di tutti i file Aurora;
- checksum iniziali e finali;
- mappatura fixture → requisito → expected output;
- divieto di aggiornare un golden prima di aver spiegato semanticamente il cambiamento;
- verifica che ogni expected sia derivato dal contratto, non dall’output corrente;
- report dei difetti runtime trovati, con slice proprietaria.

La regola di non correggere clandestinamente runtime appartenente a slice precedenti è già presente ed è molto buona. {line\_range\_start=978 line\_range\_end=994 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Slice 29

Aggiungerei:

- elenco preciso dei documenti da aggiornare;
- controllo automatico dei link;
- cattura effettiva di `--help` per tutti i comandi documentati;
- matrice documentazione → codice/test che prova la capacità;
- ricerca di riferimenti obsoleti;
- divieto di descrivere come completata una capacità non provata;
- verifica finale di coerenza tra migrazioni v7–v10, CLI, result catalog e manuale.

Il prompt già richiede di documentare gap anziché dichiarare capacità inesistenti. {line\_range\_start=996 line\_range\_end=1010 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

---

# 5. Patch comune che applicherei a ogni prompt

Ti suggerisco di non riscrivere ogni prompt da zero. Estrarrei il testo normativo e aggiungerei questo **preambolo comune**:

```
## Istruzioni operative comuni

Prima di modificare qualsiasi file:

1. leggi integralmente:
   - `AGENTS.md`;
   - `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
   - i documenti elencati per questa slice, usando i percorsi letterali;
   - `.kb/template/template_slice_report.md`;
   - i report pertinenti delle slice precedenti;
   - il codice attuale sotto `src/dsl_mngr`;
   - i test, fixture e golden pertinenti sotto `tests`;

2. tratta il prompt della presente slice e il design v2 come fonti normative;
   usa il design v1 soltanto come baseline concettuale nei punti non sostituiti
   dal v2;

3. esegui un controllo anti-drifting fra:
   - design v2;
   - report delle slice precedenti;
   - schema e migrazioni correnti;
   - codice corrente;
   - test e golden correnti;

4. non assumere che un report dimostri che il worktree sia conforme o verde;

5. segnala prima del codice:
   - precondizioni mancanti;
   - regressioni già presenti;
   - divergenze fra documenti e implementazione;
   - file che prevedi di modificare;

6. preserva modifiche non correlate già presenti nel worktree e non
   sovrascrivere lavoro dell’utente.

In caso di conflitto fra fonti, applica la fonte con precedenza maggiore e
documenta il conflitto nel report. Non risolvere silenziosamente ambiguità che
modificano il contratto.

Usa Python `>=3.12,<3.13` e il corretto interprete secondo `AGENTS.md`.
Prima del codice installa il progetto in editable mode con extra dev; dopo le
modifiche esegui test mirati e suite completa con lo stesso interprete.
```

E questo **epilogo comune**:

```
## Chiusura obbligatoria

Prima di dichiarare la slice completata:

1. esegui i test mirati richiesti dalla slice;
2. esegui la suite completa;
3. esegui:
   - `git status --short`
   - `git diff --check`
   - `git diff --stat`
4. revisiona il diff pertinente alla slice;
5. verifica che nessuna funzionalità fuori scope sia stata aggiunta;
6. verifica che artifact, report, hash e ordinamenti siano deterministici dove
   richiesto;
7. salva una copia del report finale in
   `.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`,
   usando `.kb/template/template_slice_report.md`.

Nel report indica almeno:
- stato reale della slice: completata, parziale o bloccata;
- esito del controllo anti-drifting;
- file modificati;
- migrazioni, comandi, artifact e contratti aggiunti;
- interprete e versione Python;
- comando di installazione editable;
- tutti i comandi di test/verifica e relativi risultati;
- test falliti, saltati, interrotti o non eseguiti;
- scostamenti dal design;
- problemi preesistenti;
- correzioni appartenenti a slice precedenti;
- elementi rimasti fuori scope.

Non dichiarare la slice completata se la suite completa non passa, salvo una
limitazione ambientale dimostrata e distinta da un difetto del codice. Non
aggiornare fixture o golden per mascherare una deviazione semantica.
```

---

# 6. Elenco preciso delle modifiche da fare prima dell’esecuzione

## Obbligatorie per tutte le slice 20–29

1. **Estrarre il prompt senza parafrasarlo.**
2. **Aggiungere il percorso esatto del design v2.**
3. **Sostituire ogni nome descrittivo di documento con il percorso reale.**
4. **Aggiungere lettura esplicita di `src/dsl_mngr` e `tests`.**
5. **Aggiungere lettura di `template_slice_report.md`.**
6. **Aggiungere l’istruzione esatta per salvare il report.**
7. **Aggiungere la gerarchia delle fonti.**
8. **Aggiungere il controllo anti-drifting prima del codice.**
9. **Aggiungere la gestione delle precondizioni mancanti.**
10. **Aggiungere la policy per test falliti/non eseguiti.**
11. **Uniformare la selezione dell’interprete secondo `AGENTS.md`.**
12. **Aggiungere `git status --short`, `git diff --check` e `git diff --stat`.**
13. **Imporre che il report dichiari stato reale, scostamenti e fuori scope.**
14. **Imporre che i golden non vengano aggiornati per nascondere divergenze.**

## Fortemente raccomandate

15. Leggere almeno gli stati e gli scostamenti di tutti i report dalla 20 alla precedente.
16. Leggere integralmente tutti i report intermedi nelle slice di consolidamento.
17. Aggiungere i vincoli trasversali su import, path, artifact, log e separazione architetturale.
18. Richiedere una matrice di tracciabilità locale nel report di ogni slice.
19. Richiedere verifica esplicita delle API/precondizioni consegnate dalla slice precedente.

## Specifica indispensabile per la slice 27

20. Cambiare l’elenco dei report da `16–17 e 26` a **20–26**, mantenendo 16–17 se utili.
21. Richiedere verifica end-to-end dell’intera catena temporale.
22. Richiedere matrice sorgente → evidenza → candidato → review → intervallo → DSL/GEXF.
23. Verificare esplicitamente che il batch della 22, Excel della 23–25 e common review della 20 siano realmente integrati.

---

# Conclusione

Non vedo la necessità di rigenerare il contenuto tecnico delle slice v2. Vedo invece la necessità di **irrobustire tutti i prompt v2 con un protocollo operativo comune**.

La formula corretta è quindi:

> **prompt normativo v2 invariato + preambolo operativo comune + percorsi esatti + controllo anti-drift + report template + gate test/diff + integrazioni specifiche per le slice di consolidamento.**

Con queste aggiunte, i prompt v2 si comporteranno funzionalmente come i prompt v1 più maturi, ma conserveranno il vantaggio fondamentale del v2: le decisioni tecniche non verranno rigenerate o reinterpretate.

## Verifiche eseguite

- ✅ `wc -l .kb/projects/slicing/slice_{01..19}/dsl_manager_slice_*_prompt.md`
- ✅ `nl -ba .kb/projects/slicing/slice_17/dsl_manager_slice_17_prompt.md`
- ✅ `nl -ba .kb/projects/slicing/slice_18/dsl_manager_slice_18_prompt.md`
- ✅ `nl -ba .kb/projects/slicing/slice_19/dsl_manager_slice_19_prompt.md`
- ✅ `nl -ba .kb/template/template_slice_report.md`
- ✅ `rg -n '^### Prompt Slice|^Implementa solo|^Leggi integralmente|^Obiettivo verticale minimo|^Non |^Test obbligatori|^Test minimi obbligatori|^Done:|^La slice è finita' '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `find .kb/documenti -type f -print | sort`
- ✅ `git status --short` — nessuna modifica apportata; pertanto non sono stati creati commit o pull request.

----

io ti proporrei quanto segue, poi mi dici se è okay, poi eventualmente eseguiamo.
- implementiamo tutte le modifche che hai proposto, e includiamo (non so se l'ho vista) una relativa alla produzione del report.
- io leggerei tutti i report storici, senza limitazioni. il lavoro girerà su vs code, dove l'ai dovrebbe poter beneficiare del context buider.
- la questione sull'usare questa o quella configurazione dovrebbe già essere risolta da AGENTS.md, ma mi va bene una ridondanza. però il comportamento deve essere identico a quello attuale (che ha dimostrato di funzionare), non voglio che il processo si rompa a causa di una aggiunta opzionale.
- non teniamo i prompt slice nel design v2, le salviamo su quella che è in effetti la loro destinazione finale, ossia:
- <root>\.kb\projects\slicing\slice\_<NN>\dsl\_manager\_slice\_<NN>\_prompt.md
- e nella stesso folder, a creazione avvenuta: dsl\_manager\_slice\_<NN>\_report.md
- estrai i pezzi di prompt slice dal design v2 in maniera determinista (es. uno script python), per non correre rischi. poi li modifichi in base alle tue raccomandazioni, poi salvi i prompt slice v2, creando gli appositi folder slice\\_\<NN> e poi i file.
- sotto il folder .wb, crea un file 'modifica\\_prompt\\_slice\\_v2.md' e inserisci tutte le modifiche da te proposte nella tua precedente risposta. il file ti servirà da guida e da verifica durante il processo.
- come si diceva, discutiamone, e poi si parte.

----

# Valutazione

La proposta è **corretta** e, con alcune precisazioni, è più robusta sia dell’estrazione pura sia della rigenerazione tramite il vecchio prompt di slicing.

L’impostazione che approverei è:

1. usare i prompt incorporati nel design v2 come **sorgente normativa iniziale**;
2. estrarli deterministicamente;
3. applicare un wrapper operativo uniforme;
4. salvare i prompt finali nelle directory `slice_20`–`slice_29`;
5. rimuovere dal design v2 le copie integrali dei prompt;
6. lasciare nel design soltanto i riferimenti ai file canonici;
7. leggere tutti i report storici precedenti per ogni slice;
8. produrre il report della slice solo durante la futura implementazione, non ora.

Ci sono però alcuni dettagli che conviene decidere prima di partire.

---

# 1. Tutte le modifiche proposte: sì

Sono d’accordo nell’applicare a ogni prompt v2 tutte le modifiche operative discusse:

- percorsi letterali dei documenti;
- gerarchia delle fonti;
- lettura di codice, test, fixture e golden correnti;
- lettura dei report storici;
- controllo anti-drifting;
- verifica delle precondizioni consegnate dalle slice precedenti;
- comportamento in caso di precondizione mancante;
- preservazione delle modifiche estranee;
- installazione editable;
- test mirati;
- suite completa;
- gestione trasparente dei test non eseguiti, falliti, interrotti o limitati dall’ambiente;
- `git status --short`;
- `git diff --check`;
- `git diff --stat`;
- revisione del diff;
- regole su artifact, path, determinismo, migrazioni e dipendenze;
- Definition of Done uniforme;
- produzione del report.

La parte tecnica specifica di ciascuna slice rimarrà quella del design v2. Non dovremo reinterpretarla, soltanto trasformarla in un prompt operativo autonomo.

---

# 2. Produzione del report: sì, va resa esplicita

La modifica relativa al report era inclusa nella proposta precedente, ma conviene renderla ancora più netta.

Ogni prompt finale dovrà:

1. ordinare di leggere:

   ```
   .kb/template/template_slice_report.md
   ```
2. ordinare di salvare il report in:

   ```
   .kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md
   ```
3. imporre che il report includa almeno:

   - stato reale: `completata`, `parziale` o `bloccata`;
   - esito del controllo anti-drifting;
   - precondizioni verificate;
   - file modificati;
   - migrazioni e schema;
   - comandi e interfacce aggiunte;
   - artifact prodotti;
   - interprete Python usato;
   - comando di installazione editable;
   - test mirati;
   - suite completa;
   - `git status`, diff stat e `git diff --check`;
   - test falliti, non eseguiti o limitati;
   - regressioni preesistenti;
   - scostamenti dal design;
   - modifiche appartenenti a slice precedenti;
   - elementi lasciati fuori scope.

Questo è coerente con il template esistente, che già richiede stato, modifiche, diff/status e test.  Il template contiene inoltre sezioni dedicate a interprete, installazione editable, suite e verifiche aggiuntive.

Userei nel prompt la formulazione richiesta dal vecchio processo:

```
- salva una copia del report prodotto al termine del task nel file
  `.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`,
  usando come template `.kb/template/template_slice_report.md`.
```

Questa era anche l’istruzione esplicitamente imposta dal prompt di slicing originale.

## Importante: i report non verranno creati ora

Durante questo lavoro creeremmo:

```
.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md
...
.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md
```

Non creeremmo invece report vuoti o placeholder. Il file:

```
dsl_manager_slice_<NN>_report.md
```

deve nascere solo quando la relativa slice viene effettivamente implementata, perché deve attestare uno stato reale.

---

# 3. Lettura di tutti i report storici: sono d’accordo

Se il processo verrà eseguito in VS Code con context builder, leggere tutti i report precedenti è una scelta ragionevole.

Per ciascuna slice `NN`, il prompt dovrebbe richiedere:

```
tutti i report esistenti delle slice da 01 a NN-1
```

Quindi:

- slice 20: report 01–19;
- slice 21: report 01–20;
- slice 22: report 01–21;
- …
- slice 27: report 01–26;
- …
- slice 29: report 01–28.

Questo replica il comportamento dei prompt v1 più maturi. Per esempio, il prompt della slice 17 elencava tutti i report 01–16.  La slice 18 richiedeva tutti i report fino alla 17.

Propongo però una frase di salvaguardia:

```
Leggi integralmente tutti i report esistenti delle slice 01–<precedente>.
Usali come storia implementativa, elenco di scostamenti e registro delle
verifiche eseguite, ma non considerarli prova sufficiente che il worktree
corrente sia conforme o che la suite corrente sia verde: verifica sempre codice,
migrazioni, artifact e test attuali.
```

Questa precisazione è importante perché il design v2 dice esplicitamente che i report 01–19 sono storia utile, ma non prova che il worktree corrente sia verde. {line\_range\_start=28 line\_range\_end=38 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

## Percorsi espliciti

Per evitare interpretazioni, preferirei che ciascun prompt elencasse concretamente i percorsi, come facevano alcuni prompt v1:

```
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
...
```

Questo è più lungo, ma ha diversi vantaggi:

- non richiede espansione mentale di pattern;
- riduce il rischio di saltare una slice;
- rende il prompt autonomo;
- rende evidente quali report devono già esistere;
- funziona bene con il context builder.

Per le slice future, lo script di generazione può produrre deterministicamente anche questa lista.

---

# 4. Configurazione Python: ridondanza sì, cambiamento no

Sono d’accordo con la tua osservazione: `AGENTS.md` contiene già la politica corretta e non dobbiamo introdurre una seconda logica concorrente.

La soluzione migliore non è duplicare tutta la regola, ma rinviare esplicitamente ad `AGENTS.md`:

```
Usa Python `>=3.12,<3.13` e determina l’interprete esclusivamente secondo le
regole environment-specific di `AGENTS.md`. Non introdurre una selezione
alternativa dell’interprete.

Prima di modificare codice, installa il progetto in editable mode con extra dev
usando tale interprete. Dopo le modifiche, usa lo stesso interprete per test
mirati e suite completa.
```

Nel tuo ambiente VS Code, sarà quindi `AGENTS.md` a imporre:

1. lettura di `.codex/config.toml`;
2. lettura di `PROJECT_PYTHON`;
3. uso esclusivo di quell’eseguibile;
4. installazione editable;
5. test con lo stesso interprete.

Questo mantiene il comportamento già collaudato.

## Correzione specifica della slice 20

Il prompt interno della slice 20 dice direttamente di usare l’interprete indicato da `.codex/config.toml`. {line\_range\_start=835 line\_range\_end=837 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Lo sostituirei con il rinvio ad `AGENTS.md`, non con una nuova procedura. In questo modo:

- in VS Code continuerà a comportarsi esattamente come oggi;
- non nasceranno due fonti potenzialmente divergenti;
- la logica resta centralizzata.

Quindi: **ridondanza dichiarativa, non ridondanza normativa**.

---

# 5. Spostamento dei prompt fuori dal design v2: sì, ma bisogna aggiornare il design

Sono d’accordo nel rendere canonici questi file:

```
.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md
...
.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md
```

E nel non mantenere una seconda copia completa nel design.

Questo evita:

- duplicazione;
- drift fra prompt embedded e prompt eseguito;
- incertezza su quale versione sia canonica;
- necessità di aggiornare due copie in caso di correzione.

## Il design non può però limitarsi a perdere la sezione 22

Il design contiene diversi link come:

```
[Prompt eseguibile](#prompt-slice-20)
```

Per esempio, il piano della slice 20 punta al prompt incorporato. {line\_range\_start=714 line\_range\_end=720 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Inoltre l’autoverifica afferma che i prompt sono presenti e pronti all’uso. {line\_range\_start=810 line\_range\_end=825 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}

Se rimuoviamo la sezione 22 senza altri aggiornamenti, produrremmo link rotti e una dichiarazione non più precisa.

## Modifica corretta del design

### Nel piano delle slice

Sostituirei i link interni con collegamenti relativi ai file canonici, per esempio:

```
[Prompt eseguibile](../../../projects/slicing/slice_20/dsl_manager_slice_20_prompt.md)
```

Il percorso relativo esatto andrà calcolato e verificato dal file del design.

### Nell’autoverifica

Sostituirei:

```
Tutti i prompt sono senza placeholder di template e pronti all’uso.
```

con qualcosa come:

```
I prompt canonici delle slice 20–29 sono salvati nelle rispettive directory
`.kb/projects/slicing/slice_<NN>/`, sono privi di placeholder e pronti all’uso;
il design mantiene collegamenti verificati verso tali file.
```

### Nella sezione 22

Non eliminerei completamente la sezione. La trasformerei in un indice canonico:

```
## 22. Prompt di implementazione

I prompt di implementazione non sono duplicati in questo documento. Le copie
canoniche, complete e pronte all’uso sono:

- [Slice 20](../../../projects/slicing/slice_20/dsl_manager_slice_20_prompt.md)
- [Slice 21](../../../projects/slicing/slice_21/dsl_manager_slice_21_prompt.md)
...
- [Slice 29](../../../projects/slicing/slice_29/dsl_manager_slice_29_prompt.md)

I prompt costituiscono parte normativa del perimetro delle rispettive slice.
In caso di modifica, deve essere aggiornata la tracciabilità del design senza
reintrodurre copie duplicate.
```

Questa è preferibile a rimuovere del tutto la sezione perché conserva:

- navigazione;
- tracciabilità;
- dichiarazione normativa;
- punto di ingresso unico;
- assenza di duplicazione.

---

# 6. Estrazione deterministica: impostazione approvata

Sono d’accordo nell’usare uno script Python anziché copiare manualmente i blocchi.

## Procedura proposta

Lo script dovrebbe:

1. leggere il design v2 come UTF-8;
2. individuare esattamente:

   ```
   ### Prompt Slice 20
   ...
   ### Prompt Slice 29
   ```
3. usare gli heading come delimitatori;
4. richiedere che ciascun numero 20–29 compaia esattamente una volta;
5. fallire se:

   - manca una slice;
   - una slice è duplicata;
   - l’ordine non è 20–29;
   - un blocco è vuoto;
   - resta un placeholder come `<NN>` o `<slice_number>`;
   - il numero interno non coincide con quello dell’heading;
6. calcolare e mostrare SHA-256 dei dieci blocchi estratti;
7. salvare inizialmente l’estrazione in memoria o in una directory temporanea;
8. applicare deterministicamente preambolo, lista report, percorsi e chiusura;
9. creare le directory `slice_20`–`slice_29`;
10. scrivere i prompt con UTF-8 e newline LF;
11. rileggere i file;
12. verificare presenza delle istruzioni obbligatorie;
13. verificare che ogni prompt abbia il report path corretto;
14. verificare che ogni prompt legga esattamente i report 01–`NN-1`;
15. verificare che non esistano placeholder;
16. solo dopo, aggiornare il design v2 rimuovendo le copie embedded.

## Script persistente o temporaneo?

Dato che lo scopo è una migrazione una tantum e che i prompt embedded verranno rimossi, **non vedo grande valore nel mantenere lo script come componente permanente**.

La scelta che suggerisco è:

- usare uno script Python temporaneo, mostrato nel log operativo;
- salvare nel documento guida:

  - algoritmo;
  - delimitatori;
  - hash delle estrazioni originali;
  - controlli eseguiti;
- eliminare lo script temporaneo al termine.

In alternativa, si potrebbe salvarlo sotto `.kb` come tool di manutenzione, ma diventerebbe inutilizzabile dopo la rimozione dei prompt embedded. Quindi preferisco non conservarlo.

## Conservazione della prova di estrazione

Nel file guida registrerei una tabella:

| Slice | Heading sorgente | SHA-256 blocco originale | File destinazione | Verifica |
| --- | --- | --- | --- | --- |
| 20 | `### Prompt Slice 20` | … | `slice_20/...prompt.md` | pass |
| … | … | … | … | … |
| 29 | `### Prompt Slice 29` | … | `slice_29/...prompt.md` | pass |

Questo rende l’estrazione verificabile anche dopo che i prompt originali sono stati rimossi dal design.

---

# 7. Il file guida: un solo punto da chiarire

Hai scritto:

```
sotto il folder .wb, crea un file 'modifica_prompt_slice_v2.md'
```

Nel repository e nelle istruzioni esiste `.kb`, non `.wb`. Presumo quindi che `.wb` sia un refuso e che il percorso desiderato sia:

```
.kb/modifica_prompt_slice_v2.md
```

Oppure, se vuoi mantenerlo vicino ai prompt:

```
.kb/projects/slicing/modifica_prompt_slice_v2.md
```

La seconda posizione è, secondo me, più ordinata perché il documento governa precisamente il processo di slicing.

## Mia raccomandazione

Userei:

```
.kb/projects/slicing/modifica_prompt_slice_v2.md
```

con queste sezioni:

1. scopo;
2. fonti;
3. problemi individuati nei prompt embedded;
4. modifiche comuni obbligatorie;
5. modifiche specifiche per slice;
6. algoritmo di estrazione deterministica;
7. matrice dei report storici;
8. gerarchia delle fonti;
9. protocollo anti-drifting;
10. protocollo installazione/test;
11. protocollo report;
12. protocollo diff/status;
13. matrice di verifica dei prompt 20–29;
14. SHA-256 dei blocchi originali;
15. esito finale;
16. eventuali scostamenti dalla proposta iniziale.

Il file dovrà includere tutte le raccomandazioni della risposta precedente, non soltanto un riassunto.

---

# 8. Attenzione alla politica Git del repository

C’è un aspetto operativo importante: `AGENTS.md` stabilisce che `.kb` è intenzionalmente ignorata da Git e deve restare fuori dal repository finché tale politica non venga cambiata esplicitamente.

Tutti i file che proponiamo di modificare si trovano sotto `.kb`:

- design v2;
- documento guida;
- prompt 20–29;
- future directory delle slice.

Pertanto, nel lavoro successivo:

- i file potranno essere creati e modificati localmente;
- non dovrebbero essere aggiunti forzatamente a Git;
- non dovrebbe essere modificato `.gitignore` per includerli;
- salvo un tuo cambiamento esplicito della policy, non ci sarà una modifica versionabile da committare.

Questo non impedisce il lavoro, ma significa che l’esito sarà un aggiornamento della knowledge base locale, non una patch Git ordinaria.

---

# 9. Ordine esatto che proporrei per l’esecuzione

Quando mi darai il via, seguirei questo ordine:

## Fase A — Inventario e baseline

1. verificare `AGENTS.md`;
2. verificare `git status`;
3. verificare le directory `slice_01`–`slice_19`;
4. verificare esistenza dei report storici;
5. inventariare tutti i documenti nominati dal design;
6. leggere integralmente design v2, template report e prompt v1 rappresentativi.

## Fase B — Documento guida

7. creare `modifica_prompt_slice_v2.md`;
8. inserire tutte le modifiche comuni;
9. inserire le modifiche specifiche 20–29;
10. inserire checklist di estrazione e verifica.

## Fase C — Estrazione

11. eseguire script Python deterministico;
12. validare heading 20–29;
13. estrarre i blocchi;
14. calcolare SHA-256;
15. conservare temporaneamente gli originali estratti.

## Fase D — Produzione dei prompt

16. aggiungere preambolo operativo comune;
17. aggiungere percorsi documentali letterali;
18. aggiungere tutti i report storici richiesti per ciascuna slice;
19. mantenere invariato il nucleo normativo specifico;
20. aggiungere modifiche specifiche per slice;
21. aggiungere protocollo report;
22. aggiungere chiusura, test, diff e anti-drift;
23. creare directory `slice_20`–`slice_29`;
24. scrivere i dieci prompt.

## Fase E — Verifica

25. verificare zero placeholder;
26. verificare numeri e path;
27. verificare lista report completa;
28. verificare template report;
29. verificare gerarchia delle fonti;
30. verificare install editable e suite;
31. verificare anti-drift;
32. verificare `git diff --check`;
33. verificare modifiche specifiche 20–29;
34. registrare l’esito nella guida.

## Fase F — Aggiornamento del design

35. sostituire i prompt embedded con indice dei file canonici;
36. aggiornare i link dal piano delle slice;
37. aggiornare navigazione e autoverifica;
38. verificare che non rimangano link `#prompt-slice-NN`;
39. verificare che ogni link relativo punti a un file reale;
40. verificare che nessun contenuto normativo sia andato perso.

---

# 10. Decisioni che considero già definite

In base alla tua proposta, assumerei come approvate queste scelte:

- prompt canonici esterni al design;
- nessuna doppia copia;
- estrazione deterministica;
- tutte le raccomandazioni operative;
- lettura di tutti i report storici precedenti;
- context builder come supporto, senza ridurre le fonti;
- comportamento Python governato da `AGENTS.md`;
- report prodotto dalla futura esecuzione della slice;
- nessun report placeholder;
- directory `slice_20`–`slice_29` create ora;
- design v2 aggiornato per puntare ai prompt esterni.

Rimane soltanto da confermare il percorso del documento guida:

- **raccomandato:** `.kb/projects/slicing/modifica_prompt_slice_v2.md`;
- oppure `.kb/modifica_prompt_slice_v2.md`;
- oppure, se `.wb` era intenzionale, `.wb/modifica_prompt_slice_v2.md`.

# Conclusione

La proposta va bene ed è, a mio giudizio, il workflow più sicuro.

La sola correzione concettuale che aggiungerei è:

> Non “cancellare semplicemente” i prompt dal design; sostituirli con un indice di link ai prompt canonici e aggiornare tutti i riferimenti e l’autoverifica.

E la sola ambiguità da risolvere prima di partire è `.wb` contro `.kb`. La mia scelta consigliata è:

```
.kb/projects/slicing/modifica_prompt_slice_v2.md
```

## Verifiche su cui si basa questa valutazione

- ✅ `nl -ba .kb/projects/slicing/slice_17/dsl_manager_slice_17_prompt.md`
- ✅ `nl -ba .kb/projects/slicing/slice_18/dsl_manager_slice_18_prompt.md`
- ✅ `nl -ba .kb/projects/slicing/slice_19/dsl_manager_slice_19_prompt.md`
- ✅ `nl -ba .kb/template/template_slice_report.md`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `find .kb/documenti -type f -print | sort`
- ✅ `git status --short` — nessuna modifica eseguita in questa fase di discussione.

- d'accordo per modificare design v2 in modo che la sezione dei prompt non venga cancellata ma modificata con una lista di riferimenti ai file dei prompt slice v2
- è più pulito usare .kb (quindi okay per la tua proposta), ma , per completezza, dovrei aver aggiornato .gitignore per usare anche .kb. in effetti, il folder .wb è stato aggiunto nello stesso commit, può darsi che tu non lo veda ancora. può darsi che AGENTS.md sia rimasto indietro: nel caso, modificalo per allinearsi allo stato del git.
- aggiungerei un punto alla fase E: confrontare ogni prompt slice prodotta con il template storico per il prompt di slicing v1 e verificare che siano identici dal punto di vista funzionale (leggono le stesse cose, eseguono le stesse azioni, ecc.). se poi il prompt v2 fa cose in più, meglio: ma deve fare almeno quello che faceva il v1.
- detto questo, se sei d'accordo, per me si può partire.

----

PREMESSA: non dobbiamo eseguire codice di dsl-managar, perciò puoi ignorare la creazione dell'ambiente. il codice python che ti serve lo puoi creare nel tuo workspace. detto questo:
- d'accordo per modificare design v2 in modo che la sezione dei prompt non venga cancellata ma modificata con una lista di riferimenti ai file dei prompt slice v2\n- è più pulito usare .kb (quindi okay per la tua proposta), ma , per completezza, dovrei aver aggiornato .gitignore per usare anche .kb. in effetti, il folder .wb è stato aggiunto nello stesso commit, può darsi che tu non lo veda ancora. può darsi che AGENTS.md sia rimasto indietro: nel caso, modificalo per allinearsi allo stato del git.\n- aggiungerei un punto alla fase E: confrontare ogni prompt slice prodotta con il template storico per il prompt di slicing v1 e verificare che siano identici dal punto di vista funzionale (leggono le stesse cose, eseguono le stesse azioni, ecc.). se poi il prompt v2 fa cose in più, meglio: ma deve fare almeno quello che faceva il v1.\n- detto questo, se sei d'accordo, per me si può partire.

----

### Summary

- Estratti deterministicamente i prompt normativi delle Slice 20–29 e salvati nei rispettivi file canonici sotto `.kb/projects/slicing/slice_<NN>/`. Ogni prompt conserva integralmente il nucleo tecnico del design v2 e aggiunge il protocollo operativo comune.
- Rafforzati tutti i prompt con lettura integrale dei report storici precedenti, verifica di codice/test/fixture/golden, controllo anti-drifting, gerarchia delle fonti e verifica delle precondizioni reali.
- Mantenuta la selezione dell’interprete sotto il controllo esclusivo di `AGENTS.md`, aggiungendo in modo ridondante ma non concorrente i comandi logici per installazione editable e suite completa.
- Aggiunta a ogni prompt una chiusura uniforme con test mirati, suite completa, controlli Git, confronto funzionale con template e prompt v1 e produzione obbligatoria del report attraverso `template_slice_report.md`.
- Resa cumulativa la lettura dei report: per esempio la Slice 27 elenca esplicitamente tutti i report dalla Slice 01 alla Slice 26.
- Creato il documento guida con tutte le modifiche comuni e specifiche, la procedura deterministica, gli SHA-256 dei blocchi originali e la checklist di equivalenza funzionale v1.
- Sostituiti nel design v2 i prompt duplicati con l’indice dei dieci file canonici, mantenendone esplicitamente il valore normativo. {line\_range\_start=829 line\_range\_end=844 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md}
- Allineato `AGENTS.md` allo stato Git attuale: `.kb` e `.wb` sono ora entrambe descritte come directory versionate, con responsabilità distinte.
- Non sono stati creati report vuoti per le Slice 20–29; la guida stabilisce che nasceranno soltanto durante l’effettiva implementazione delle rispettive slice.
- Commit creato: `2fa7f29 Add operational prompts for slices 20 through 29`.
- Creata la richiesta di pull request con titolo **“Extract and harden implementation prompts for slices 20–29”**.

**Testing**

- ✅ Script Python di verifica deterministica — confrontati i dieci nuclei estratti con il design v2 presente nel commit di partenza e verificati gli SHA-256 registrati.
- ✅ Script Python di equivalenza funzionale — verificati per ogni prompt: fonti v1, report completi `01–NN-1`, codice e test, install editable, test mirati, suite completa, anti-drifting, controlli Git, report e gestione del fuori scope.
- ✅ Script Python di verifica riferimenti — tutti i percorsi `.kb` letterali presenti nei prompt puntano a file esistenti, esclusi correttamente i report futuri.
- ✅ Script Python di verifica design — ciascun prompt canonico è collegato due volte dal design e non rimangono link obsoleti `#prompt-slice-NN`.
- ✅ Script Python di verifica report — confermata l’assenza di report placeholder nelle directory `slice_20`–`slice_29`.
- ✅ `git diff --cached --check`
- ✅ `git diff --cached --stat`
- ✅ `git status --short` — worktree pulito dopo il commit.
- ✅ `git log -1 --oneline`
- ⚠️ `python -m pytest` non eseguito: come richiesto, non è stato eseguito codice DSL Manager perché la modifica riguarda esclusivamente documentazione e prompt.
- ⚠️ `/opt/codex/mcp/.venv/bin/python -m pip install 'mcp[cli]>=1.0,<2'` — tentativo infrastrutturale non necessario alla codebase fallito per indisponibilità di rete/proxy; non ha modificato il repository né influito sulla validazione.