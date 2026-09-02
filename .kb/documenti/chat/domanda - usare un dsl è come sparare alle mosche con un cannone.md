**Puoi ripetermi, con grounding web, perché è utile avere un DSL in una modernizzazione? Potrei dover spiegare ai colleghi che non stiamo sparando alle mosche con un cannone, ma dovrei esserne convinto anch'io.**

----

## La risposta onesta

**Un DSL può essere “un cannone per sparare alle mosche”. Ma non necessariamente. Nel vostro caso, il valore non sta tanto nell’inventare un nuovo linguaggio: sta nel creare una rappresentazione semantica, verificabile e indipendente dalla tecnologia del sistema legacy.**

Anzi, internamente lo presenterei meno come *«costruiamo un DSL»* e più come:

> **Costruiamo un modello canonico e machine-readable di ciò che il sistema fa, da cui possiamo derivare analisi, decisioni e artefatti della modernizzazione.**

Questa impostazione non è particolarmente esotica. L’OMG ha sviluppato il **Knowledge Discovery Metamodel**, specificamente nell’ambito dell’Architecture-Driven Modernization, per rappresentare software esistente, relazioni, ambienti operativi e diversi livelli di astrazione, creando un formato comune utilizzabile da strumenti differenti. ([OMG][1])

## Nel vostro progetto, che cos’è davvero il DSL?

La pipeline descritta nella guida è:

```text
fonti eterogenee
    ↓
evidenze verificabili nel registry
    ↓
fatti, relazioni, conflitti e domande
    ↓
snapshot DSL versionato
    ↓
diff, grafi e altri artefatti
```

Inoltre avete stabilito che **il registry SQLite è la fonte primaria**, mentre DSL, diff e grafo sono viste derivate. Questo è molto importante: significa che non state creando un secondo documento da mantenere manualmente e destinato inevitabilmente a diventare obsoleto. 

Tecnicamente, quindi, quello che chiamate DSL è soprattutto:

* un **modello di dominio formalizzato**;
* una **rappresentazione intermedia semantica**;
* una **proiezione serializzabile** in JSON, YAML e Markdown;
* potenzialmente, un input per generatori e controlli automatici.

Non deve necessariamente diventare un linguaggio sofisticato, con editor speciale, compilatore e sintassi proprietaria.

---

# Perché è utile in una modernizzazione

## 1. Separa ciò che il sistema fa da come è implementato

In un legacy, la stessa regola può essere distribuita fra:

* una tabella Oracle;
* un trigger;
* una procedura PL/SQL;
* un campo o pulsante della form;
* una condizione nell’applicazione;
* un manuale operativo;
* un comportamento osservabile nei log.

Il codice non contiene necessariamente tutto il significato del sistema. I documenti non sono necessariamente aggiornati. Il database mostra la struttura, ma non sempre l’intento. I log mostrano ciò che accade, ma non spiegano perché.

Il DSL raccoglie il risultato della ricostruzione in termini come:

```yaml
entity: PraticaPrestito

properties:
  importo_massimo:
    values:
      - value: 50000
        source: manuale_2012
      - value: 60000
        source: requisiti_correnti
    status: conflict

states:
  - BOZZA
  - IN_VALUTAZIONE
  - APPROVATA
  - RESPINTA
```

A quel punto non siete più obbligati a ragionare continuamente in termini di `TB_PRAT`, trigger `TRG_X` o item Oracle Forms. Potete ragionare sul concetto **PraticaPrestito** e poi decidere come rappresentarlo nel nuovo sistema.

JetBrains descrive precisamente questo vantaggio: il modello contiene la conoscenza del dominio, mentre il generatore contiene la conoscenza della tecnologia di destinazione. Cambiando piattaforma può cambiare il generatore senza dover ricostruire da zero il significato del dominio. ([JetBrains][2])

## 2. Evita che la nuova architettura sia una copia cosmetica del legacy

Senza uno strato semantico intermedio, una modernizzazione tende facilmente a diventare:

```text
tabella Oracle → entity Java
procedura PL/SQL → service Java
form Oracle → pagina web
```

Il risultato può essere tecnologicamente nuovo ma concettualmente identico al legacy, compresi:

* accoppiamenti storici;
* nomi incomprensibili;
* confini sbagliati;
* regole duplicate;
* responsabilità mescolate;
* strutture nate per limiti tecnologici che non esistono più.

Microsoft raccomanda l’analisi del dominio proprio per identificare bounded context e confini dei servizi, anziché derivare automaticamente i microservizi dalla struttura tecnica del monolite. Un modello di dominio deve rappresentare regole, comportamento, linguaggio di business e vincoli del contesto considerato. ([Microsoft Learn][3])

Il DSL diventa quindi una specie di **camera di decompressione**:

```text
legacy concreto
    ↓
significato ricostruito
    ↓
nuova architettura
```

È molto più sicuro di:

```text
legacy concreto
    ↓
nuova architettura
```

## 3. Rende espliciti conflitti e incertezze

Supponiamo che troviate:

* manuale storico: importo massimo €50.000;
* procedura recente: importo massimo €60.000;
* form: validazione a €50.000;
* log: pratiche da €55.000 approvate.

Senza un modello intermedio, questa contraddizione resta sparsa fra quattro fonti e può essere scoperta durante il collaudo o, peggio, dopo il rilascio.

Nel vostro sistema può invece diventare un oggetto esplicito:

```yaml
conflict:
  subject: PraticaPrestito.importo_massimo
  alternatives:
    - 50000
    - 60000
  evidence:
    - manuale
    - procedura
    - form
    - log
  resolution: pending
```

Questo cambia la natura del problema: non è più una discrepanza nascosta, ma una decisione da assegnare, discutere e chiudere.

La modernizzazione richiede precisamente una fase di discovery affidabile delle applicazioni e delle dipendenze. AWS raccomanda strumenti di discovery programmatici per validare dipendenze e traffico, e considera l’assessment una base necessaria per produrre piani di migrazione ad alta confidenza. ([AWS Documentation][4])

## 4. Dà tracciabilità alle decisioni

Una frase come:

> «Una pratica sopra €50.000 richiede l’approvazione manuale.»

non vale molto se non sapete:

* da quale fonte proviene;
* quale revisione della fonte;
* se è una frase letterale o un’interpretazione;
* se esistono fonti discordanti;
* chi l’ha accettata;
* in quale snapshot è entrata.

Nel vostro processo, invece, il fatto può conservare:

```text
fact
 → candidate
   → chunk o fragment
     → source revision
       → file originale
```

Questo è utile durante:

* review con gli esperti di dominio;
* analisi di anomalie;
* collaudo;
* audit;
* discussioni sull’origine di una regola;
* modifiche successive.

La tracciabilità è particolarmente importante quando entra un’AI nella pipeline: l’AI non viene trattata come autorità, ma come **proponente di ipotesi vincolate a evidenze verificabili**.

## 5. Consente di automatizzare senza affidarsi al testo libero

Da documenti e codice grezzo è difficile generare in maniera affidabile:

* contratti API;
* schemi dati;
* casi di test;
* matrici di migrazione;
* diagrammi;
* controlli di completezza;
* report di impatto.

Da un modello strutturato, invece, potete chiedere deterministicamente:

```text
Mostrami tutte le entità senza identificatore.
Mostrami tutte le relazioni verso entità non definite.
Genera test per ogni transizione di stato.
Trova tutte le regole che dipendono da una fonte obsoleta.
Genera un contratto OpenAPI preliminare.
Confronta il dominio prima e dopo una decisione.
```

È lo stesso principio architetturale sfruttato da strumenti come OpenRewrite: il codice viene trasformato in un albero semantico strutturato, sul quale vengono eseguite ricerche e trasformazioni controllate, per poi ristampare il codice con modifiche minime. Il vostro DSL non è un AST e non dovrebbe fingere di esserlo, ma il vantaggio dello **strato semantico intermedio** è analogo. ([OpenRewrite Docs][5])

## 6. Permette una modernizzazione incrementale

Un modello versionato consente di produrre:

```text
DSL_000001
DSL_000002
DSL_000003
```

e vedere non soltanto che un file è cambiato, ma che:

```text
+ aggiunto lo stato SOSPESA
~ importo massimo: 50000 → 60000
- rimossa relazione Cliente → FilialeStorica
+ aggiunta relazione PraticaPrestito → ValutazioneRischio
```

Questo è importante perché una modernizzazione affidabile raramente è una singola grande riscrittura. Il pattern Strangler Fig, per esempio, riduce il rischio sostituendo progressivamente parti del sistema e facendo convivere temporaneamente legacy e nuovo. ([AWS Documentation][6])

Il DSL può funzionare da contratto semantico durante questa convivenza: rende visibile quale parte del dominio è stata compresa, validata, migrata o rimane ancora legacy.

## 7. Riduce la libertà pericolosa dell’AI

Un LLM lasciato libero di analizzare documenti e produrre direttamente codice può:

* cambiare terminologia;
* inventare relazioni plausibili;
* fondere concetti distinti;
* ignorare contraddizioni;
* trasformare ipotesi in fatti;
* produrre risultati diversi a ogni esecuzione.

Un DSL piccolo e vincolato riduce lo spazio delle risposte ammissibili:

```text
record_type deve essere uno di…
confidence deve essere uno di…
source_revision_id deve esistere…
evidence_text deve essere letterale…
una relazione deve avere source e target…
```

Un recente approfondimento pubblicato sul sito di Martin Fowler osserva che DSL piccoli e vincolati possono rendere più affidabile l’uso degli LLM, perché l’output può essere validato e corretto automaticamente. Lo stesso articolo sottolinea però che esiste un costo reale nella progettazione e manutenzione del modello semantico: il beneficio rimane finché il DSL resta abbastanza piccolo e circoscritto. ([martinfowler.com][7])

---

# Dove sarebbe davvero il “cannone”

Il DSL diventerebbe sovraingegneria se:

1. **Il sistema fosse piccolo e ben documentato.**
   Un’unica applicazione CRUD, poche tabelle e una sola sorgente autorevole difficilmente richiedono una lingua o un metamodel complesso. Anche Microsoft osserva che per un bounded context molto semplice potrebbe essere sufficiente un modello dati elementare, senza introdurre pattern DDD più sofisticati. ([Microsoft Learn][8])

2. **Il modello venisse mantenuto manualmente.**
   Avreste codice, documenti e DSL che divergono fra loro.

3. **Il DSL non avesse consumatori concreti.**
   Se nessuno lo usa per generare, validare, confrontare, interrogare o decidere qualcosa, è soltanto documentazione costosa.

4. **Tentaste di descrivere tutto.**
   Ogni bottone, query, variabile locale, procedura tecnica e dettaglio dell’interfaccia non merita necessariamente un concetto di dominio.

5. **Costruiste subito un linguaggio sofisticato.**
   Parser proprietario, editor visuale, type system, plugin IDE e code generator completo sarebbero probabilmente prematuri. Fowler segnala esplicitamente che il beneficio delle DSL deve essere confrontato con il costo di progettare il linguaggio e costruire gli strumenti necessari. ([martinfowler.com][9])

6. **Il modello precedesse la scoperta.**
   Prima si osservano e consolidano i concetti; poi si stabilizza il linguaggio. Progettare a priori un DSL e costringere il dominio a entrarci è un rischio noto. ([martinfowler.com][10])

---

# Il criterio economico più semplice

Un concetto dovrebbe entrare nel DSL solo quando serve ad almeno una di queste cose:

* prendere una decisione di modernizzazione;
* evidenziare un conflitto;
* generare o validare un artefatto;
* identificare una dipendenza;
* definire un confine;
* produrre un test;
* mantenere la tracciabilità di una regola.

Per esempio:

| Informazione                       | Probabilmente nel DSL? | Motivo                           |
| ---------------------------------- | ---------------------: | -------------------------------- |
| `PraticaPrestito` è un’entità      |                     Sì | Serve alla struttura del dominio |
| Una pratica può essere `APPROVATA` |                     Sì | Regola comportamento e test      |
| Il limite è €50.000 o €60.000      |                     Sì | Conflitto da risolvere           |
| Il trigger è alla riga 417         |      No, come concetto | Rimane nella tracciabilità       |
| Il pulsante è largo 120 pixel      |                     No | Dettaglio UI legacy              |
| Il pulsante avvia l’approvazione   |                     Sì | Comportamento di dominio         |
| Il file era in `C:\old_app`        |              Quasi mai | Metadato tecnico, non dominio    |

Il DSL non deve essere un inventario universale del legacy. Deve essere una **compressione utile** del sistema: conserva ciò che serve per capirlo e trasformarlo, scartando il rumore accidentale.

---

# Nel vostro caso specifico

Io vedo una giustificazione concreta perché avete contemporaneamente:

* fonti documentali;
* DDL;
* PL/SQL;
* Oracle Forms;
* log;
* versioni storiche e correnti;
* regole discordanti;
* estrazione assistita da AI;
* necessità di audit delle affermazioni;
* snapshot e diff;
* possibilità di più destinazioni future.

Il costo maggiore della modernizzazione non sarà probabilmente scrivere una classe Java o creare una tabella nuova. Sarà determinare con sufficiente sicurezza:

> **Qual è il comportamento che dobbiamo preservare, quale è obsoleto, quale è sbagliato e quale vogliamo deliberatamente cambiare?**

Il DSL serve a rendere questa risposta esplicita, strutturata e versionabile.

## La condizione decisiva

**Diff e grafo, da soli, non giustificano il DSL.** Sono visualizzazioni utili, ma non bastano a ripagare il modello.

Il DSL diventa davvero conveniente quando viene usato come input per almeno alcuni risultati operativi:

```text
DSL
 ├─ decisioni sui confini dei servizi
 ├─ matrice legacy → target
 ├─ test di caratterizzazione
 ├─ contratti API preliminari
 ├─ regole di trasformazione dati
 ├─ controlli di completezza
 ├─ report dei conflitti
 └─ analisi di impatto
```

Più questi consumatori crescono, più il costo iniziale del modello viene ammortizzato.

---

# Come lo spiegherei ai colleghi

> Non stiamo costruendo un linguaggio alternativo all’applicazione. Stiamo costruendo una rappresentazione intermedia, verificabile e indipendente dalla tecnologia, del comportamento che dobbiamo modernizzare. Oggi quel comportamento è distribuito tra database, codice, form, documenti e log. Il modello ci permette di riconciliare le fonti, rendere visibili i conflitti, collegare ogni affermazione all’evidenza originale e produrre in modo ripetibile analisi, test e artefatti per il sistema nuovo. Se si limita a duplicare la documentazione è sovraingegneria; se diventa il punto di passaggio fra discovery e trasformazione, riduce il rischio della migrazione.

## Il mio verdetto

**Terrei l’approccio, ma manterrei il DSL deliberatamente modesto.**

Le regole sane sarebbero:

```text
Il registry è la fonte primaria.
Il DSL è sempre generato.
Nessuno modifica manualmente gli snapshot.
Ogni fatto importante è tracciabile.
Le incertezze restano incertezze.
Ogni nuovo costrutto deve avere un uso concreto.
Il modello descrive il dominio, non ogni dettaglio del legacy.
I generatori sono separati dal modello.
```

In sostanza: **non state costruendo un cannone; state costruendo una mappa.** Diventa un cannone soltanto se iniziate a decorare la mappa invece di usarla per attraversare il territorio.

[1]: https://www.omg.org/technology/kdm/?utm_source=chatgpt.com "Knowledge Discovery Metamodel (KDM)"
[2]: https://www.jetbrains.com/mps/concepts/?utm_source=chatgpt.com "How Does MPS Work? - Concepts | MPS by JetBrains"
[3]: https://learn.microsoft.com/en-us/azure/architecture/microservices/model/domain-analysis?utm_source=chatgpt.com "Use Domain Analysis to Model Microservices"
[4]: https://docs.aws.amazon.com/prescriptive-guidance/latest/application-portfolio-assessment-guide/detailed-application-assessment.html?utm_source=chatgpt.com "Detailed application assessment"
[5]: https://docs.openrewrite.org/?utm_source=chatgpt.com "OpenRewrite Docs: OpenRewrite by Moderne | Large Scale ..."
[6]: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html?utm_source=chatgpt.com "Strangler fig pattern - AWS Prescriptive Guidance"
[7]: https://martinfowler.com/articles/llm-and-dsls.html?utm_source=chatgpt.com "DSLs Enable Reliable Use of LLMs"
[8]: https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/microservice-domain-model?utm_source=chatgpt.com "Designing a microservice domain model - .NET | Microsoft Learn"
[9]: https://martinfowler.com/articles/languageWorkbench.html?utm_source=chatgpt.com "Language Workbenches: The Killer-App for Domain Specific Languages?"
[10]: https://martinfowler.com/bliki/DslMigration.html?utm_source=chatgpt.com "Dsl Migration"
