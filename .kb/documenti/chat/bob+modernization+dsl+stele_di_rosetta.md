> **2026/04/12**
>
> Questo testo fa riferimento a:
> - bob+moderniization+mappa_relazioni_database.ms
> - bob+modernization+visualizzazione_grafo_sql.md
> - bob+modernization+modello_dsl.md

----
----

# Summary

Il documento definisce una strategia per costruire un sistema Python modulare di modernization per applicazioni legacy Oracle Forms + Oracle DB, basato non su diagrammi, ma su un DSL / knowledge graph canonico: una “fonte vera” tipizzata, versionabile, testabile e arricchita da provenienza, evidenze, confidenza e tempo. Da questo modello si generano poi viste diverse: Gephi/GEXF, Mermaid, DBML, Structurizr/C4, viste per IBM Bob. 

In pratica:

* il DSL è il cuore del sistema;
* Oracle DB, Oracle Forms XML e documentazione “sporca” sono fonti di ingestion;
* i fatti certi, le inferenze e le evidenze documentali vanno separati;
* i moduli Python devono scambiarsi artefatti versionati, non chiamarsi direttamente;
* serve una “stele di rosetta” comune: contratti, tipi, stati, naming, schema version;
* lo scambio tra moduli dovrebbe usare file per i payload e SQLite come registry operativo;
* ChatGPT serve soprattutto per progettare e revisionare, Codex per implementare nel repo, con `AGENTS.md` e documenti canonici come guardrail; questa parte è coerente anche con la documentazione ufficiale Codex su `AGENTS.md` come file di istruzioni di progetto. ([OpenAI Developers][1])

In breve:

**stai progettando una base di conoscenza eseguibile per modernizzare legacy Oracle, costruita come grafo canonico modulare, validabile e riusabile; Bob e i diagrammi non sono la fonte, sono consumatori del modello.**

[1]: https://developers.openai.com/codex/guides/agents-md?utm_source=chatgpt.com "Custom instructions with AGENTS.md – Codex"


----
----

sei il mio esperto di database design, oracle, dsl, c4, ibm project bob, modernization, oracle forms.

esamina i file allegati ma non prendili giusto come guida / punto di partenza.

in una delle nostra discussioni che adesso non riesco a ritrovare neanche per salvarmi la vita aveva elaborato una complessa risposta riguardo alla possibilità di estrarre data da una database (ma non solo, fra poco ci arriviamo) e metterli in relazioni in un modello DSL che facesse da base (e da "source of truth", se non capito male) per la produzione di diverse viste - il tutto per costruire una base date per un processo di modernizzazione di una applicazione da realizzare con ibm project bob.

non solo, in teoria questo modo modello avrebbe potuto essere ulteriormente arricchito con i dati provenienti dalla versione .xml di file .fmb di oracle forms, anch'essi proveniente dall'applicazione che stiamo andando a modernizzare.

non solo, di nuovo, ma in questo modello sarebbe stato possibile integrare anche un livello di documentazione "sporca", ovvero non strutturata, come manuali utente, ticket, change request, ecc. - questo non avrebbero toccato la verità canonica ma queste informazioni sarebbere stati disponibili come 'evidence layer', come supporto al core principale di dati.

alla fine, l'idea era quella di una grafo di relazioni (esportabile a blocchi relativi ai singoli domini come schema per gephi), costruito sull'idea principale era che le relazioni sarebbero state basate sull'evidenza dei fatti, mentre altre informazioni meno accertabili sarebbero state trattate per l'appunto con un'ottica 'questa parte di manuale / ticket / mail sostiene che il campo x è legato alla tabella y' ma non come verità assolute.

una parte della concettulizzazione prevedeva anche di integrare nelle informazioni l'età del dato, se dsponibile, in modo da ricostruire una timeline o comunque avere un'idea di quanto obsoleta era l'informazione.

tutto bello, e... non so dov'è finito. quindi sarei a chiederti se, sulla base di quel poco che ti fornisco, puoi ricostruire la teoria del modello DSL come l'avevi concepita quella volta. confido che, se la teoria alla base è nota e condivisa, il risultato non sia troppo differente.

l'idea generale è di avere una teoria che poi ci permetta di scrivere del codice python che (attraverso diverse ingestion pipeline) vada a costruire il modello DSL in question. l'idea è anche che questo codice preveda la possibilità per il modello DSL di autotestarsi, per verificare se l'aderenza ai dati originari è solida o se ci sono discrepanza.

ma non scrivere il codice subito, vorrei prima vedere se possiamo recuperare il ragionamento originario.

pensaci attentamente, passo per passo.

----
----

Sì. E credo che il ragionamento originario fosse questo: **non costruire un diagramma**, ma **costruire un modello di conoscenza tipizzato, versionabile, testabile e con provenienza esplicita**, da cui poi generare tutte le viste utili alla modernizzazione. Nei file allegati questa idea c’è già in embrione: “DSL custom = fonte vera”, mentre Mermaid, DBML e Structurizr sono viste generate; inoltre il modello viene già spezzato in layer distinti per form, navigazione, comportamento e data lineage.  

Quindi la teoria, ricostruita in modo pulito, è questa.

1. Il DSL non è un formato di diagramma: è il **modello canonico**
   Mermaid sa fare flowchart ed ER diagram; Structurizr DSL definisce un modello architetturale testuale con viste separate; DBML è un DSL open source per descrivere schema e relazioni del database. Tutti e tre sono utili, ma nessuno dei tre, da solo, è abbastanza ricco per rappresentare bene insieme Oracle Forms, navigazione, trigger, parametri, globali, routine, oggetti DB e documentazione sporca. Per questo il “vero” source of truth deve stare un gradino sopra, in un tuo DSL di dominio, e quelle sintassi devono essere soltanto proiezioni generate.   ([mermaid.js.org][1])

2. Il nucleo del modello è un **grafo semantico tipizzato**
   Il DSL originario, secondo me, non andava pensato come “YAML con campi”, ma come **grafo di entità e relazioni con semantica esplicita**. Nei tuoi allegati questo si vede già nella separazione in quattro layer e nell’idea che Python non debba “indovinare dai nomi”, ma conoscere almeno i tipi di oggetto e il significato delle relazioni. Il passo successivo naturale è quindi: ogni cosa importante diventa un nodo tipizzato, ogni collegamento diventa un arco tipizzato, e ogni arco porta con sé provenienza, attendibilità e tempo.   

3. I layer veri, secondo me, erano in realtà cinque
   Nei file allegati i layer espliciti sono quattro: **Form inventory**, **Interaction / navigation**, **Behavior / procedures**, **Data lineage**. Io li terrei, ma aggiungerei formalmente un quinto layer ortogonale: **Evidence / provenance**. È lì che finiscono manuali, ticket, change request, mail, note di analisi, ipotesi umane e deduzioni da parsing non certo. Così il modello distingue in modo netto tra “fatto canonico estratto da una fonte strutturata” e “affermazione supportata da un documento ma non ancora promossa a verità”. Questo pezzo non lo vedo formalizzato nei file, ma è la prosecuzione più coerente del loro impianto.   

4. La regola d’oro è: **fatto, inferenza, evidenza** non vanno mescolati
   Qui sta la parte più importante del modello.

Un fatto canonico è qualcosa che Oracle o Forms ti dicono direttamente: per esempio una dipendenza in `ALL_DEPENDENCIES`, una foreign key ricostruita da `ALL_CONSTRAINTS` + `ALL_CONS_COLUMNS`, un trigger in `ALL_TRIGGERS`, l’uso di colonne in `ALL_TRIGGER_COLS`, il sorgente in `ALL_SOURCE`, il DDL in `DBMS_METADATA`, o l’albero di dipendenza in `DEPTREE`. Oracle documenta sia il tracciamento automatico delle dipendenze tra oggetti, sia le viste e gli strumenti che le espongono. Questo è il materiale da cui derivare il core canonico del DSL. ([Oracle Docs][2])

Un’inferenza è una relazione che il sistema ricava, ma non osserva in modo esplicito: per esempio “questa routine probabilmente scrive su questa tabella” perché il parser ha visto una `UPDATE`, oppure “questa form è un login” perché convergono campi, trigger e routine di autenticazione. Le inferenze possono essere utilissime, ma devono essere etichettate come tali.

Un’evidenza, infine, è una fonte documentale che sostiene qualcosa: “il ticket CR-184 dice che `CUSTOMER.STATUS` pilota la visibilità del bottone X”. Questo non diventa subito verità canonica: entra come claim con fonte, data, autore e confidenza. È esattamente il meccanismo che ti serve per integrare la documentazione sporca senza contaminare il core.

5. Le entità del DSL, ricostruite bene, sarebbero queste
   Non scrivo il DSL in sintassi, ma la tassonomia sì.

Al livello applicativo:

* `application`, `domain`, `bounded_context`, `module_suite`
* `form_module`, `menu_module`, `object_library`

Al livello Forms:

* `window`, `canvas`, `block`, `item`, `lov`, `record_group`
* `trigger`, `program_unit`, `form_parameter`, `global_variable`, `alert`

Al livello logico/comportamentale:

* `use_case`, `navigation_action`, `business_rule`, `outcome_code`

Al livello database:

* `table`, `view`, `column`, `constraint`, `index`, `sequence`
* `db_trigger`, `package`, `procedure`, `function`, `synonym`

Al livello documentale:

* `manual_section`, `ticket`, `change_request`, `email_note`, `analysis_note`

E ogni nodo dovrebbe avere almeno: identità stabile, tipo, nome, owner/schema se applicabile, sorgente di estrazione, versioni osservate, e stato di risoluzione.

6. Le relazioni del grafo sono il vero linguaggio del modello
   Anche qui la chiave è il tipo esplicito. Alcuni archi canonici:

* `contains`: form → block, block → item
* `displays`: window/canvas → item o block
* `navigates_to`: form → form
* `opens_block`: trigger/outcome → block
* `passes_parameter`: source_item → target_form_parameter
* `sets_global`: source_item/trigger → global_variable
* `invokes`: trigger/program_unit → routine
* `depends_on`: object → object
* `reads`, `writes`, `validates_with`, `looks_up`: routine/form → oggetto DB
* `implemented_by`: business_rule → trigger/routine
* `described_by`: entity/relation → evidence node
* `supports_claim`: evidence node → claim/relation

Questa parte è coerente sia con i file che mi hai dato, sia con le strutture che Oracle espone davvero. Nei tuoi allegati, per esempio, `GCC001 -> GCC002` via `CALL_FORM`, con `prm_user` e `GLOBAL.USER_CONNECTED`, è già un edge tipizzato molto più ricco di una semplice freccia.  

7. La timeline non è un extra: è un asse del modello
   La tua idea dell’“età del dato” è ottima e ha perfettamente senso. Io la formalizzerei così:

* `observed_at`: quando questa informazione è stata estratta
* `source_date`: data del documento o del ticket che la sostiene
* `valid_from` / `valid_to`: se nota
* `first_seen_in_release` / `last_seen_in_release`: se riesci a ricostruire le versioni
* `staleness_score`: calcolo derivato, non dato sorgente

Questo permette due cose: capire quanto un fatto sia fresco o sospetto, e costruire viste temporali. Dal lato export, GEXF supporta attributi tipizzati e anche grafi dinamici con timestamp o intervalli, quindi la timeline nel grafo non è una fantasia: è tecnicamente esportabile verso Gephi. ([docs.gephi.org][3])

8. Le ingestion pipeline non scrivono direttamente viste: scrivono **claim normalizzati**
   Anche qui, secondo me, il ragionamento originario era molto vicino a questo:

* **pipeline Oracle DB**: estrae oggetti, dipendenze, DDL, source, statements, constraint, trigger, ecc.
* **pipeline Oracle Forms XML**: parte da `frmf2xml` / Forms2XML e ricava blocchi, item, trigger, built-in, `CALL_FORM`, `OPEN_FORM`, parameter list, globali, program units
* **pipeline documentale**: spezza manuali/ticket/mail in frammenti, estrae riferimenti e genera claim con provenienza

Oracle documenta il tool Forms2XML da riga di comando per `.fmb`, `.mmb` e `.olb`, e documenta anche le varie viste del data dictionary che servono per costruire il grafo applicativo e database. ([Oracle Docs][4])

La cosa importante è che ogni pipeline non “scrive direttamente il DSL finale”, ma produce prima osservazioni o claim normalizzati: “ho osservato X in fonte Y con confidenza Z”. Poi un motore di consolidamento promuove alcune osservazioni a fatti canonici e lascia le altre nel layer evidenziale.

9. Il DSL dovrebbe essere progettato per **autotestarsi**
   Questo l’hai ricordato bene, ed è giustissimo. I test non devono verificare solo il parser Python: devono verificare il modello.

Io li dividerei così.

**Test di coerenza interna**
Ogni relazione deve puntare a nodi esistenti; nessun parametro può essere passato a una form inesistente; nessun `reads/writes` può riferire un oggetto DB non risolto senza che sia marcato `unresolved`.

**Test di aderenza alla fonte**
Se una form XML contiene 12 item e il DSL ne ha 11, è un errore. Se `ALL_DEPENDENCIES` dichiara una dipendenza e nel grafo manca, è un errore o almeno un warning. Se `DBMS_METADATA` cambia hash e il nodo no, il modello è stantio.

**Test di conflitto**
Se la fonte canonica dice `read` e un ticket dice `write`, il sistema non deve “scegliere a caso”: deve aprire un conflitto tra fatto e evidenza.

**Test di risoluzione**
Le routine nominate nelle form ma non trovate nel DB devono risultare come `unresolved_reference`, non sparire.

**Test di generazione**
Il modello deve riuscire a generare viste valide: Mermaid renderizzabile, Structurizr DSL coerente, DBML coerente, GEXF importabile.

10. Il rapporto con C4 / Structurizr era probabilmente questo
    C4 non serve per modellare il dettaglio di Oracle Forms. Serve per **proiettare il dettaglio su viste architetturali leggibili**. Structurizr definisce esplicitamente il concetto di workspace come insieme di modello, viste e documentazione, e supporta viste dinamiche e filtered views sopra il medesimo modello. Quindi, nel ragionamento originario, Structurizr non era il luogo dove mettere il fatto fine-grained; era il posto dove generare viste architetturali pulite a partire dal DSL canonico. ([Structurizr][5])

Tradotto: il tuo DSL sta sotto; sopra generi, per esempio, una vista C4 di dominio che mostra “suite di form”, database, package principali e sistemi esterni, senza trascinarti dietro ogni item o trigger.

11. Il rapporto con IBM Bob era probabilmente questo
    IBM Bob oggi viene presentato sia come AI coding agent per modernization sia come strumento capace di analizzare e documentare repository esistenti. Questo si sposa benissimo con un DSL versionato in repo: Bob non dovrebbe dedurre l’applicativo ogni volta da zero, ma lavorare su un artefatto intermedio stabile, diffabile e rigenerabile. In altre parole, Bob diventa molto più utile se gli dai in pasto non solo codice legacy, ma anche un knowledge layer coerente che rappresenta moduli, dipendenze, viste e documentazione. ([IBM][6])

12. La teoria ricostruita, in una formula sola
    Secondo me il modello originario era, in sostanza, questo:

**un knowledge graph tipizzato, versionabile e provenance-aware, con core canonico basato su estrazione strutturata, layer evidenziale separato per fonti sporche, asse temporale per età e validità del dato, e generatori verso viste specializzate come Mermaid, DBML, Structurizr e GEXF/Gephi.**

Se vuoi la versione ancora più secca:

**il DSL non descrive diagrammi; descrive fatti, relazioni, fonti, incertezze e tempo. I diagrammi sono solo viste.**

13. La forma minima del meta-modello
    Per non lasciarla troppo astratta, io la definirei così, concettualmente:

* `Entity`

  * `id`
  * `kind`
  * `name`
  * `qualified_name`
  * `owner/schema`
  * `source_system`
  * `canonical: true|false`

* `Relation`

  * `type`
  * `from`
  * `to`
  * `canonical: true|false`
  * `confidence`
  * `derived_by`
  * `first_seen`
  * `last_seen`

* `Evidence`

  * `id`
  * `source_type`
  * `source_ref`
  * `source_date`
  * `excerpt`
  * `author`
  * `reliability`

* `Claim`

  * `subject`
  * `predicate`
  * `object`
  * `supported_by: [evidence]`
  * `status: asserted | inferred | canonical | disputed`

Questa, per me, è la parte che nei file era implicita ma non ancora completamente formalizzata.

14. In pratica, cosa terrei e cosa correggerei dei file allegati
    Terrei senza esitazioni:

* l’idea del **DSL custom come fonte vera**;
* la separazione tra **Mermaid/DBML/Structurizr come output**;
* i layer **inventory / navigation / behavior / data lineage**;
* l’idea del **manifest dichiarativo** per le estrazioni invece di euristiche sui nomi.   

Correggerei o estenderei:

* aggiunta formale di **provenienza/evidenza**;
* aggiunta formale di **tempo/staleness**;
* distinzione netta tra **fatto canonico**, **inferenza** e **claim documentale**;
* definizione di un set ristretto ma rigoroso di **relation types** e **quality checks**.

Questa, a mio avviso, è la ricostruzione più fedele del ragionamento che avevamo impostato: non un semplice “linguaggio per fare mappe”, ma una **base di conoscenza eseguibile** per la modernizzazione, con cui poi Python costruisce il modello e Bob lavora su artefatti solidi invece che su impressioni sparse.  

[1]: https://mermaid.js.org/syntax/flowchart.html?utm_source=chatgpt.com "Flowcharts Syntax | Mermaid"
[2]: https://docs.oracle.com/en/database/oracle/oracle-database/19/adfns/schema-object-dependency.html?source=%3Aso%3Atw%3Aor%3Aawr%3Aana%3A%3A%3A%2C%3Aso%3Atw%3Aor%3Aawr%3Aana%3A%3A%3A&utm_source=chatgpt.com "27 Understanding Schema Object Dependency"
[3]: https://docs.gephi.org/desktop/User_Manual/Import/GEXF_File_Format/?utm_source=chatgpt.com "GEXF | Gephi Desktop Documentation"
[4]: https://docs.oracle.com/cd/E14373_01/migrate.32/e13368/appmgr_forms.htm?utm_source=chatgpt.com "Converting an Oracle Forms Application"
[5]: https://docs.structurizr.com/workspaces?utm_source=chatgpt.com "Workspaces"
[6]: https://www.ibm.com/products/ai-coding-agent?utm_source=chatgpt.com "AI Coding Agent"

----
----

Esistono link, tutorial, best practices per quanto stiamo discutendo? Non vorrei stessimo reinventando la ruota quando magari esistono altri sentieri già esplorati. È qualcosa che viene generalmente fatto in ambito modernization?

----
----

Sì: **non state reinventando la ruota nel principio**, ma state probabilmente costruendo una **versione su misura** di qualcosa che in modernization esiste già da anni sotto nomi diversi. Il riferimento formale più vicino a quello che stiamo discutendo è **OMG KDM (Knowledge Discovery Metamodel)**, nato nell’ambito **Architecture-Driven Modernization**: è un meta-modello pensato proprio per rappresentare software esistente, elementi, associazioni e ambienti operativi come rappresentazione intermedia scambiabile fra tool. ([omg.org][1])

Quello che cambia, nella pratica, è che **molti team non usano KDM “puro” fino in fondo**: usano invece una combinazione di **discovery**, **inventory**, **dependency mapping**, **assessment** e poi un **modello intermedio** più pragmatico, spesso interno. Questa non è una stranezza: oggi i percorsi di modernization dei vendor grossi parlano esplicitamente di discovery e dependency mapping come fase iniziale o come acceleratore chiave. AWS Transform parla di *application discovery and dependency mapping*; Azure Migrate parla di dependency analysis e portfolio assessment; IBM descrive la fase iniziale come discovery intelligente, mapping delle dipendenze e technical assessment. ([Amazon Web Services, Inc.][2])

Quindi la risposta secca alla tua domanda è: **sì, è assolutamente qualcosa che viene fatto in ambito modernization**. Non sempre con un DSL dichiarato e bello ordinato come quello che stiamo ipotizzando, ma quasi sempre con gli stessi ingredienti: estrazione degli asset, mappa delle dipendenze, classificazione dei componenti, analisi d’impatto, generazione di viste diverse per stakeholder diversi. IBM Redbooks parla esplicitamente di inventory, resource usage, dependency visualization e information flow come acceleratori della modernization, e IBM stessa lega l’AI alla visibilità sulle applicazioni legacy e sulle loro dipendenze. ([redbooks.ibm.com][3])

Nel tuo caso specifico, la parte **Oracle Forms + Oracle DB** ha già un sentiero abbastanza chiaro e ufficiale. Oracle documenta l’uso di **Forms2XML** (`frmf2xml`) per convertire `.fmb`, `.mmb`, `.olb` in XML, e documenta anche i mattoni del catalogo Oracle che servono per ricostruire il grafo: `ALL_DEPENDENCIES` per le dipendenze fra procedure/package/function/trigger, `ALL_TRIGGERS` e `ALL_TRIGGER_COLS` per trigger e colonne coinvolte, `ALL_ARGUMENTS` per gli argomenti delle routine, e `DBMS_METADATA` per recuperare metadata come XML o DDL. In altre parole: la materia prima per fare un modello intermedio serio **non ve la state inventando**, è già prevista dal prodotto. ([Oracle Docs][4])

La parte dove state facendo qualcosa di più maturo della media è questa: **separare il core canonico dal layer evidenziale**. Qui non ho trovato uno “standard industriale unico” che dica esattamente “fai così con manuali, ticket e change request”, ma il principio è perfettamente allineato ai modelli seri di modernization: tenere distinta la conoscenza estratta con certezza dalle fonti strutturate dalle affermazioni sostenute da documenti o analisi. In questo senso, il vostro DSL non mi sembra una ruota reinventata; mi sembra piuttosto una **intermediate representation moderna e pragmatica** costruita sopra sentieri già battuti. Il parallelo più vicino, lato architettura, è Structurizr: un **workspace** contiene **modello**, **viste** e anche **documentazione/ADR**, cioè separa chiaramente sorgente concettuale e diagrammi renderizzati. ([Structurizr][5])

Anche l’idea di esportare il grafo verso Gephi con attributi, confidenza e timeline è sensata e non fuori standard. Gephi documenta GEXF come formato con attributi su nodi e archi e supporto ai grafi dinamici nel tempo; quindi persino l’idea di portarsi dietro “età del dato”, `first_seen`, `last_seen` o periodi di validità ha un contenitore già pronto. ([Gephi Documentazione][6])

Quindi, in pratica, io la vedrei così.

1. **Il sentiero standard/formale** è: **OMG KDM / ADM**. È il riferimento più vicino a un “DSL standard per modernization” e ti dà anche la legittimazione concettuale per dire: *stiamo costruendo una rappresentazione intermedia del legacy*. ([omg.org][1])

2. **Il sentiero industriale/pragmatico** è: **discovery → dependency mapping → assessment → target views**. È quello che oggi si vede nei tool di modernization veri, anche quando non espongono un DSL elegante all’utente. ([Amazon Web Services, Inc.][2])

3. **Il sentiero operativo per voi** è: **Oracle metadata + Forms2XML + intermediate model custom + viste generate**. Qui il pezzo custom non è un capriccio: è il modo per rendere interoperabili Oracle Forms, Oracle DB, documentazione sporca e Bob. ([Oracle Docs][4])

Se devo dirtela in una frase: **l’idea generale è mainstream nella modernization; la vostra implementazione concreta è custom, ma in modo sensato**. La cosa più “classica” che forse vi manca come parola chiave, per cercare materiale già esplorato, è proprio questa: **Architecture-Driven Modernization / KDM / application discovery and dependency mapping / intermediate representation / legacy knowledge model**. ([omg.org][7])

Per andare a colpo sicuro, questi sono i riferimenti che leggerei davvero:

* **OMG KDM / ADM** — standard più vicino al vostro ragionamento: KDM overview e spec. ([omg.org][8])
* **Oracle Forms2XML** — base ufficiale per estrarre la semantica dei moduli Forms. ([Oracle Docs][4])
* **Oracle dependency metadata** — `ALL_DEPENDENCIES`, `ALL_TRIGGERS`, `ALL_TRIGGER_COLS`, `ALL_ARGUMENTS`, `DBMS_METADATA`, schema object dependency. ([Oracle Docs][9])
* **Structurizr DSL** — ottimo per la logica “single model, multiple views”. ([Structurizr][10])
* **SchemaCrawler** — utile come sentiero già esplorato per discovery/documentazione/schema comprehension lato DB. ([schemacrawler.com][11])
* **Gephi / GEXF** — utile se volete davvero fare grafo con attributi e tempo. ([Gephi Documentazione][6])
* **Materiale modernization vendor-side** per vedere come il settore parla oggi di discovery e dependency mapping: IBM, Azure, AWS. ([IBM][12])

[1]: https://www.omg.org/spec/KDM/1.4/About-KDM?utm_source=chatgpt.com "About the Knowledge Discovery Metamodel Specification ..."
[2]: https://aws.amazon.com/documentation-overview/transform/?utm_source=chatgpt.com "AWS Transform Documentation - Amazon.com"
[3]: https://www.redbooks.ibm.com/redbooks/pdfs/sg248532.pdf?utm_source=chatgpt.com "Mainframe Application Modernization Patterns for Hybrid ..."
[4]: https://docs.oracle.com/cd/E14373_01/migrate.32/e13368/appmgr_forms.htm?utm_source=chatgpt.com "Converting an Oracle Forms Application"
[5]: https://docs.structurizr.com/workspaces?utm_source=chatgpt.com "Workspaces"
[6]: https://docs.gephi.org/desktop/User_Manual/Import/GEXF_File_Format/?utm_source=chatgpt.com "GEXF | Gephi Desktop Documentation"
[7]: https://www.omg.org/cgi-bin/doc?ptc%2F10-12-11.pdf=&utm_source=chatgpt.com "Knowledge Discovery Meta-Model (KDM)"
[8]: https://www.omg.org/technology/kdm/?utm_source=chatgpt.com "Knowledge Discovery Metamodel (KDM)"
[9]: https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_DEPENDENCIES.html?utm_source=chatgpt.com "ALL_DEPENDENCIES"
[10]: https://docs.structurizr.com/dsl?utm_source=chatgpt.com "DSL"
[11]: https://www.schemacrawler.com/?utm_source=chatgpt.com "SchemaCrawler - Free database schema discovery and ..."
[12]: https://www.ibm.com/think/insights/reimagining-application-modernization-migration-agentic?utm_source=chatgpt.com "Reimagining the application migration and modernization ..."

----
----

puoi creare un modello "finto" GEFX con metadati? in una precedente discussione avevi sollevato il fatto che probabilmente in un grafo destinato alla visualizzazione non finiscono tutti i dati disponibili, e solo quelli principali vengono visualzzati, gli altri vengono espressi come metadati. vorrei vedere come vengono visualizzati.

----
----

Sì: ti ho preparato un **GEXF finto** con metadati realistici da modernization, scaricabile qui:

[fake_modernization_graph.gexf](sandbox:/mnt/data/fake_modernization_graph.gexf)
[fake_modernization_graph_README.txt](sandbox:/mnt/data/fake_modernization_graph_README.txt)

Il punto chiave è questo: **GEXF può contenere sia struttura del grafo sia attributi tipizzati sia metadata di visualizzazione**, e supporta anche grafi dinamici nel tempo. In pratica, quindi, nello stesso file puoi mettere nodi/archi, confidence, provenance, evidence, status, date di validità, e anche colore/dimensione/posizione. ([Gephi Documentation][1])

Nel file che ti ho creato ci sono:

* 2 form (`F_GCC001`, `F_GCC002`)
* 1 routine (`R_AUTH`)
* 1 tabella (`T_USERS`)
* 1 ticket come evidenza (`E_DOC_184`)
* 1 claim non canonico (`C_PASSWORD_POLICY`)

e ci sono anche:

* archi **canonici** come `navigates_to`, `invokes`, `reads`
* archi **non canonici / evidenziali** come `supports_claim`, `possible_dependency`
* attributi statici come `kind`, `canonical`, `confidence`, `evidence_ref`, `status`
* attributi dinamici come `staleness_score`
* metadata visuali `viz:color`, `viz:size`, `viz:position`

Un estratto del file, giusto per farti vedere la logica, è questo:

```xml
<attributes class="node" mode="static">
  <attribute id="n0" title="kind" type="string"/>
  <attribute id="n2" title="canonical" type="boolean"/>
  <attribute id="n4" title="confidence" type="double"/>
  <attribute id="n5" title="evidence_ref" type="string"/>
  <attribute id="n8" title="status" type="string"/>
</attributes>

<attributes class="node" mode="dynamic">
  <attribute id="nd0" title="staleness_score" type="double"/>
</attributes>

<node id="F_GCC001" label="Form GCC001" start="2018-01-01">
  <attvalues>
    <attvalue for="n0" value="form_module"/>
    <attvalue for="n2" value="true"/>
    <attvalue for="n4" value="1.0"/>
    <attvalue for="n5" value="forms:GCC001.xml"/>
    <attvalue for="n8" value="active"/>
    <attvalue for="nd0" value="0.10" start="2024-01-01" end="2024-12-31"/>
    <attvalue for="nd0" value="0.25" start="2025-01-01"/>
  </attvalues>
  <viz:color r="70" g="130" b="180"/>
  <viz:size value="28"/>
  <viz:position x="0" y="0" z="0"/>
</node>
```

Come si “vede” davvero in Gephi:

**Sul grafo**, di solito, vedi soprattutto il fronte visuale: nodi, archi, label e proprietà `viz` come colore, dimensione e posizione. Questo dipende dal fatto che GEXF distingue tra **attributes** e **visualization metadata**, e il modulo `viz` serve proprio a styling e layout. ([Gephi Documentation][1])

**I metadati ricchi** non vengono normalmente “stampati tutti addosso al nodo”, perché servono più come dati interrogabili che come etichette grafiche. In Gephi diventano utili soprattutto per filtri, trasformazioni e lavorazioni sui dati; la documentazione GEXF/Gephi tratta esplicitamente gli attributi come dati associati, e Gephi usa gli attributi nelle pipeline di filtro. ([Gephi Documentation][1])

**La parte temporale** la vedi come intervalli/timestamp nel lato dati e nella timeline. Gephi documenta che nei grafi longitudinali compare la rappresentazione del tempo, e per gli intervalli puoi vedere o costruire una colonna di tipo `Time Interval`. ([Gephi Documentation][2])

Quindi, semplificando molto:

* **sul canvas**: vedi il “manifesto” del nodo
* **nei dati/filtri**: vedi il “retro tecnico” del nodo
* **nella timeline**: vedi il “quando”

Per il tuo caso modernization, questo è perfetto, perché ti consente di tenere nel file molte più informazioni di quelle che mostri nel diagramma. Il nodo può apparire come “Form GCC001”, ma dietro può portarsi `canonical=true`, `confidence=1.0`, `evidence_ref=forms:GCC001.xml`, `status=active`, `staleness_score`, `owner`, `tags`, e così via. Questo è esattamente il motivo per cui in un grafo serio la visualizzazione è solo una proiezione del modello, non il modello intero. ([Gephi Documentation][1])

Una nota pratica importante, se poi vorrai generarlo via Python/NetworkX: alcuni nomi di attributo sono riservati dal formato GEXF, per esempio `id`, `pid`, `label`, quindi conviene evitare di usarli come normali metadati custom. ([NetworkX][3])

La lettura più corretta del file che ti ho preparato è questa:

* `meta` in alto = metadati globali del file
* `attributes class="node"` = schema dei metadati dei nodi
* `attributes class="edge"` = schema dei metadati degli archi
* `attvalues` = valori effettivi dei metadati
* `viz:*` = cose che si vedono direttamente nel grafo
* `start/end` e attributi dinamici = tempo e obsolescenza

In altre parole: **quello che “si vede” nel grafico è solo una piccola parte; il resto vive come attributi, filtri, colonne e timeline**. Ed è proprio il comportamento che, nel tuo scenario, vuoi ottenere.

[1]: https://docs.gephi.org/desktop/User_Manual/Import/GEXF_File_Format/ "GEXF | Gephi Desktop Documentation"
[2]: https://docs.gephi.org/desktop/User_Manual/Import_Dynamic_Data/ "Import Dynamic Data | Gephi Desktop Documentation"
[3]: https://networkx.org/documentation/stable/reference/readwrite/generated/networkx.readwrite.gexf.write_gexf.html "write_gexf — NetworkX 3.6.1 documentation"

----
----

sei il mio esperto di python, ai, oracle e oracle forms, modernization, database design. ti faccio una domanda ad ampio spettro, e forse un po' ambiziosa.

sono sempre un po' restio a fare hard-coding di strutture dati in un app, anche per programmi piccoli e "usa e getta" posso farlo. in questo caso si tratta di un progetto grosso e complesso.

mi chiedevo: dobbiamo fargli ingerire una quantità piuttosto diversificata di dati. a parte le differenti pipeline di ingestion specializzate (oracle form, info non strutturate, ecc.), anche i dati in arrivo da oracle sono piuttosto differenti, e ognuno con il suo formato (tabelle, procedure, trigger, dipendenze, ecc.).

ha senso (e nel caso, c'è modo) di costruire dei template a partire dai dati oracle? template che puoi il programma usa per interpretare i dati in arrivo dal database?

lo chiedo perché 1) così potrei sottoporre al programma i dati una volta, e lui si costruirebbe i templati per interpretarli, 2) il programma sarebbe resistente ad eventuali cambiamenti nel dataset e idealmente potrebbe essere riutilizzato per un'altra modernization di un'altra app con un database diverso, e non necessariamente oracle.

non occorre che scrivi codice, vorrei solo la teoria, al momento.

pensaci attentamente, passo per passo.

----
----

Sì, ha senso. Però la formulazione che ti consiglio è leggermente diversa: **non “template costruiti dai dati” come se il programma dovesse imparare tutto da solo**, ma **template/contratti generati o bootstrap-pati dai metadata**, poi revisionati, versionati e usati come strato stabile tra sorgenti diverse e modello canonico. È molto coerente con la direzione che avevamo già imboccato nei file allegati: DSL canonico come fonte vera, viste generate, manifest dichiarativi e separazione fra layer strutturati ed evidenziali.   

La risposta più netta è questa: **sì, puoi costruire template a partire dai dati Oracle; no, non conviene far dipendere l’architettura da template “autoappresi” in modo cieco dal primo dataset che passa**. Oracle espone parecchi metadata affidabili: oggetti in `ALL_OBJECTS`, colonne in `ALL_TAB_COLUMNS`, vincoli in `ALL_CONSTRAINTS` e `ALL_CONS_COLUMNS`, dipendenze fra oggetti in `ALL_DEPENDENCIES`, trigger in `ALL_TRIGGERS`, argomenti di routine in `ALL_ARGUMENTS`, testo sorgente in `ALL_SOURCE`, e DDL/XML tramite `DBMS_METADATA`. Per le Forms, Oracle documenta anche `frmf2xml`/Forms2XML per convertire `.fmb`, `.mmb` e `.olb` in XML. Quindi la materia prima per generare un primo set di contratti c’è davvero. ([Oracle Docs][1])

Io la imposterei in quattro strati.

**Primo strato: reflection/adapters.**
Qui non hard-codi i dati dell’applicazione, ma solo gli adapter per le famiglie di sorgenti. Per Oracle DB l’adapter interroga data dictionary e metadata API; per Oracle Forms usa XML da Forms2XML; per i documenti sporchi usa parser separati. Se vuoi portabilità verso altri database, conviene tenere un adapter generico basato su reflection e uno o più adapter di arricchimento vendor-specific. In Python, SQLAlchemy Inspector esiste proprio come interfaccia coerente di reflection con caching, quindi è un buon “substrato comune” per la parte cross-database; sopra ci metti l’enrichment Oracle-specifico dove serve. ([SQLAlchemy][2])

**Secondo strato: template/contratti logici.**
Qui “template” non vuol dire file di esempio, ma **schema logico atteso** per ogni famiglia di entità. Per esempio: `table`, `column`, `constraint`, `foreign_key`, `trigger`, `routine`, `routine_argument`, `dependency`, `form`, `block`, `item`, `navigation_relation`, `evidence_claim`. Questi template li puoi esprimere benissimo come schemi dichiarativi; JSON Schema è uno standard nato proprio per descrivere struttura, vincoli, tipi e interoperabilità dei documenti JSON. In altre parole: il template vero non descrive il database sorgente, descrive **come deve apparire il record canonico una volta normalizzato**. ([JSON Schema][3])

**Terzo strato: mapping template.**
Questo è quello che più assomiglia alla tua idea iniziale. Dal metadata Oracle puoi generare automaticamente un “profilo sorgente” che dica: quali oggetti esistono, quali chiavi identificano una riga, quali colonne ci sono, quali relazioni sono ufficiali, quali oggetti sono incompleti, quali campi mancano. Però il mapping template deve restare **esplicito**. Cioè: il sistema può generarti una prima bozza del tipo “questa estrazione corrisponde a `constraint`, chiave = owner+constraint_name, campo `R_CONSTRAINT_NAME` = reference target”, ma poi quel contratto va salvato e versionato, non ricostruito ogni volta in modo opaco. Così ottieni sia bootstrap automatico sia governabilità. ([Oracle Docs][4])

**Quarto strato: modello canonico / IR / DSL.**
Questo è il punto più importante. I template non dovrebbero servire a “interpretare al volo” tutto il legacy dentro il programma; dovrebbero servire a popolare un **modello intermedio canonico**, che resta la tua source of truth. In pratica: gli adapter leggono la sorgente, i mapping template la normalizzano, il modello canonico conserva entità, relazioni, provenienza, confidenza e tempo. Da lì poi generi viste, grafi, documentazione, export per Gephi, DBML, Mermaid, quello che ti pare. Questo è esattamente l’approccio che rende il sistema riusabile su un’altra modernization senza dover riscrivere la logica ogni volta.   

Quindi: **che cosa hard-coderei comunque?**
Io hard-coderei solo l’**ontologia** del sistema, non i dati del progetto. Cioè: i tipi di entità, i tipi di relazione, le regole di merge, i livelli di confidenza, i test di coerenza, e quali campi minimi servono per considerare valido un oggetto canonico. Non hard-coderei invece i nomi delle tabelle reali, delle package reali, delle colonne dei CSV, degli owner, delle form, o dei package PL/SQL del progetto. Quelli dovrebbero vivere nei mapping template o nei manifest generati/curati. È il compromesso giusto: l’app sa **che cos’è** una constraint, ma non deve sapere in anticipo **quale** constraint vedrà nel progetto X. Questa parte è pienamente compatibile con un approccio metadata-driven e reflection-based. ([SQLAlchemy][2])

C’è però un limite importante: **non tutto è inferibile bene dai metadata**. Oracle gestisce e traccia automaticamente molte dipendenze tra oggetti, ma non tutto quello che ti interessa per una modernization è visibile in modo completo via reflection. SQLAlchemy stessa avverte che la reflection ricrea solo ciò che è realmente rappresentato nel database, e non può ripristinare aspetti che non sono archiviati lì. Inoltre Oracle documenta il dynamic SQL come SQL generato ed eseguito a runtime quando il testo completo non è noto a compile time: questo è esattamente il tipo di zona grigia che sfugge ai template “costruiti dai metadata” se non aggiungi parsing, PL/Scope o analisi del source. ([Oracle Docs][5])

Per Oracle, infatti, io aggiungerei un livello di arricchimento molto prezioso: **PL/Scope**. Oracle lo descrive come uno strumento compiler-driven che raccoglie identificatori PL/SQL e SQL e uso delle SQL statements dal source PL/SQL, esponendoli poi nelle viste `*_IDENTIFIERS` e `*_STATEMENTS`. Questo è perfetto per costruire template più intelligenti sulle routine, perché ti dà una base migliore del semplice parsing testuale di `ALL_SOURCE`. Non elimina il problema del dynamic SQL, ma alza parecchio la qualità dell’estrazione statica. ([Oracle Docs][6])

Sul tema della riusabilità verso database non Oracle, quindi, la teoria sana è: **core canonico agnostico, adapter specifici per sorgente**. Il core dovrebbe parlare di concetti come `table`, `column`, `constraint`, `routine`, `dependency`, `ui_form`, `evidence`, non di `ALL_TAB_COLUMNS` o `DBA_DEPENDENCIES`. Quelli sono dettagli dell’adapter Oracle. Se domani il backend è PostgreSQL o SQL Server, cambi adapter e mapping template, ma non butti via il DSL. SQLAlchemy reflection aiuta proprio perché offre un’interfaccia unificata sui metadati di molti database, ma per package, trigger, peculiarità procedurali e Forms devi comunque avere plugin o enrichers specifici. ([SQLAlchemy][2])

In pratica, i “template” che farei nascere dai dati Oracle sarebbero tre.

1. **Source profile template**: descrive che cosa una sorgente contiene davvero.
2. **Mapping template**: dice come quella sorgente si mappa sui tipi canonici.
3. **Validation template**: definisce i campi obbligatori e i vincoli del record canonico.

Il programma può generare automaticamente il primo e una bozza del secondo; il terzo, invece, dovrebbe essere molto più stabile e vicino al modello di dominio. JSON Schema è una base ottima per il validation layer, mentre il mapping layer può stare in YAML/JSON tuo. ([JSON Schema][3])

Il vantaggio vero, lato progetto grosso, è che così **non stai facendo hard-coding delle strutture del legacy**, stai facendo hard-coding solo del **metamodello**. È una differenza enorme. Il legacy cambia? Rigeneri source profile e mapping template. Cambia il vendor DB? Cambi adapter. Cambia la semantica del tuo knowledge model? Aggiorni il DSL e i validatori, non mille if sparsi nel codice. E lato Bob, questo approccio è molto più forte di un parsing opportunistico: IBM Bob viene presentato sia come agente di modernization sia come strumento che analizza repo e produce documentazione; un artefatto canonico, versionato e testabile gli dà un appiglio molto più solido del semplice “vai a scavare in tutto il legacy ogni volta”. ([IBM][7])

Quindi, in sintesi:

* **sì**, ha senso costruire template a partire dai dati Oracle;
* **no**, non li farei “self-learning” e basta;
* li farei diventare **contratti espliciti, bootstrap-pati dai metadata e poi versionati**;
* il sistema buono non è “template-driven” in senso stretto, ma **metadata-driven + canonical-model-driven**;
* per essere davvero riusabile su altre modernization, devi separare **adapter di sorgente** da **ontologia canonica**. ([Oracle Docs][5])

La formula più utile, per me, è questa:

**metadata sorgente → source profile → mapping template → modello canonico → viste/test/export**

Se la imposti così, il programma non “indovina” il dataset: lo **riconosce, lo profila, lo normalizza e lo valida**.

[1]: https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_DEPENDENCIES.html?utm_source=chatgpt.com "ALL_DEPENDENCIES"
[2]: https://docs.sqlalchemy.org/en/latest/core/reflection.html?utm_source=chatgpt.com "Reflecting Database Objects — SQLAlchemy 2.1 ..."
[3]: https://json-schema.org/?utm_source=chatgpt.com "JSON Schema"
[4]: https://docs.oracle.com/en/database/oracle/oracle-database/18/refrn/ALL_CONSTRAINTS.html?utm_source=chatgpt.com "ALL_CONSTRAINTS"
[5]: https://docs.oracle.com/en/database/oracle/oracle-database/19/adfns/schema-object-dependency.html?utm_source=chatgpt.com "27 Understanding Schema Object Dependency"
[6]: https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/PLSCOPE_SETTINGS.html?utm_source=chatgpt.com "PLSCOPE_SETTINGS"
[7]: https://www.ibm.com/products/ai-coding-agent?utm_source=chatgpt.com "AI Coding Agent"

----
----

sei il mio esperto di python, ai, oracle e oracle forms, modernization, database design, ibm project bob e progetti che ti scoppiano in mano. ti faccio una domanda ad ampio spettro, e forse un po' ambiziosa.

forse vedi le altre chat di questo progetto, ma sembra che stia andando in una direzione per cui le cose potrebbero complicarsi un po'. cerca di spiegarmi al meglio delle mie possibilità.

- io immagino un programma python "a moduli", e ce ne potrebbero già essere un po': pipeline di ingestion per oracle form, pipeline per documentazione "sporca", pipeline per database oracle suddivisio in parti, generatore del dsl, gestore degli adapter per i vari (eventuali) altri database, esportatore verso gephi, esportatore di viste del dsl adattato a bob - e queste sono solo le prime che mi vengono in mente.

- perché separare? intanto perché penso sia una buona idea, e ho la sensazione che la penserai anche tu così. ma il motivo è molto più pragmatico: sarai tu a dover scrivere questo codice, e per come funzionano le cose adesso, c'è il rischio (comune a tutte le ai) che tu esaurisca la context view e cominci a driftare. non puoi tenere tutta questa roba in memoria. generando un modulo alla volta, siamo un po' più flessibili. c'è un bug in un modulo? si sistema quello, invece di dover rigenerare tutto il progetto (cosa che potrebbe causare allucinazioni e inesattezze).

- questo vuol dire però che serve un (ulteriore) sistema, uno per l'interscambio di dati e istruzioni tra i vari moduli. quando un modulo ha finito un lavoro, deve "avvertire" il modulo successivo che i dati sono pronti e che può fare il suo lavoro. la pipeline ingestion finisce di assimilare il dataset di oracle, dichiara che è pronto (in forma di dati intermedi, suppongo) per essere usato dal generatore dsl.

- qui arriva la mia domanda (più di una, in realtà): qual'è un buon sistema, best practices e tutto, per cui una app python sia composta da moduli indipendenti con un "linguaggio" comune, tale per cui un modulo può essere sganciato e sostituito con un altro con gli stessi in e out senza che le altre parti se ne accorgano?

- sarebbe possibile per te stabilire fin da subito una "stele di rosetta" per tutti i moduli, in modo che io possa farti generare codice per ogni modulo in diverse chat, sapendo che saranno interoperanti grazie al sistema di interscambio?

- baseresti il sistema di scambio su file che vengono sorvegliati (es. via watchdog) o un mini database (es. SQLAlchemy) locale, che tiene traccia di tutte le operazioni e che tutti i moduli possono consultare? o troveresti qualche altro sistema?

non occorre che scrivi codice, al momento. pensa attentamente alla teoria, passo per passo.

----
----

Sì. E la risposta netta è: **serve una piccola architettura**, non una collezione di script.

La forma giusta, per non impazzire e per potermi far generare i pezzi in chat diverse senza driftare, è questa:

**moduli indipendenti + contratti dati versionati + registry locale delle esecuzioni + artefatti su disco + orchestrazione esplicita**.

È anche coerente con la direzione che avevamo già impostato nei file di progetto: DSL canonico come fonte vera, viste generate, export multipli, manifest esplicito e separazione dei layer.   

### 1) Il principio corretto non è “moduli che si parlano”, ma “moduli che leggono e scrivono artefatti contrattualizzati”

Se vuoi sostituire un modulo senza toccare gli altri, i moduli **non devono dipendere l’uno dalle classi interne dell’altro**. Devono dipendere solo da:

* un **contratto di input/output** stabile;
* un **catalogo di tipi di artefatto**;
* un **protocollo di stato** minimo;
* un **registry** comune che dica cosa esiste, dove si trova, in che versione è, e se è valido.

In Python, questa idea si sposa molto bene con **structural typing via `Protocol`** e con modelli dati tipizzati/validati. Il linguaggio ha supporto esplicito ai `Protocol`, cioè interfacce basate sulla forma invece che sulla parentela di classe, e Pydantic può validare i payload e generare JSON Schema standardizzati dai modelli. ([Python documentation][1])

Tradotto: il modulo “Oracle Forms ingestion” non deve conoscere il modulo “DSL builder”. Deve solo produrre, per esempio, un artefatto di tipo `forms.analysis_bundle.v1`. Il builder del DSL consumerà **quel tipo**, non quel modulo.

### 2) La “stele di rosetta” si può fissare subito, e secondo me va fissata prima del codice

Sì, si può fare fin da ora. Anzi: è la cosa più sensata da fare.

La stele di rosetta non è un framework. È un piccolo **contratto costituzionale** del progetto. Io la farei di 5 pezzi.

#### a) Vocabolario canonico

Una lista chiusa di **tipi di artefatto** e **tipi di nodo/relazione** del dominio.

Esempio, lato artefatti:

* `oracle.forms.xml_bundle`
* `oracle.forms.analysis_bundle`
* `oracle.db.catalog_snapshot`
* `oracle.db.code_analysis`
* `docs.evidence_bundle`
* `dsl.graph_fragment`
* `dsl.graph_snapshot`
* `export.gephi.gexf`
* `export.bob.view_bundle`
* `quality.validation_report`

Esempio, lato dominio:

* entity kinds: `form`, `block`, `item`, `trigger`, `routine`, `table`, `view`, `constraint`, `package`, `procedure`, `document_evidence`
* relation kinds: `contains`, `invokes`, `reads`, `writes`, `navigates_to`, `depends_on`, `supports_claim`

Questo evita la deriva lessicale del tipo “in una chat lo chiamiamo X, in un’altra Y”.

#### b) Envelope comune per ogni artefatto

Ogni modulo deve produrre un envelope standard, indipendentemente dal payload.

Minimo sindacale:

* `artifact_id`
* `artifact_type`
* `schema_version`
* `producer_module`
* `run_id`
* `created_at`
* `content_ref`
* `content_hash`
* `source_refs`
* `depends_on`
* `quality_status`
* `provenance`

Qui Pydantic è molto adatto: modelli tipizzati, validazione, serializzazione, generazione JSON Schema Draft 2020-12. La parte chiave è che il contratto non resta “nella nostra testa”: diventa schema esplicito, versionabile e verificabile. ([Pydantic Docs][2])

#### c) Lifecycle comune delle esecuzioni

Per evitare ambiguità tra moduli, servono stati standard.

Io userei qualcosa del genere:

* `declared`
* `queued`
* `running`
* `produced`
* `validated`
* `failed`
* `superseded`

Questa è la parte che permette al modulo successivo di sapere davvero se può partire, invece di “guardare se è comparso un file”.

#### d) Contratto dei check

Ogni modulo deve poter pubblicare check standardizzati, non solo output.

Esempio:

* `check_id`
* `artifact_id`
* `check_type`
* `severity`
* `passed`
* `details`

Il modello concettuale è molto vicino ai sistemi asset-based moderni: Dagster, per esempio, tratta gli output come asset con dipendenze esplicite e supporta asset checks come verifiche di proprietà dell’asset. ([Dagster Docs][3])

#### e) Capability declaration del modulo

Ogni modulo dichiara:

* cosa consuma;
* cosa produce;
* che versione di schema supporta;
* che check esegue;
* se è idempotente;
* se può fare merge, append o full rebuild.

Questa è la parte che rende davvero sostituibile un modulo.

### 3) Per i moduli sostituibili: interfaccia a protocolli, plugin discovery, e niente accoppiamento diretto

Qui io terrei separati due livelli.

Primo livello: **interfaccia Python minima**, definita con `Protocol` o ABC leggere.
Secondo livello: **registrazione plugin**, così un modulo può essere scoperto e montato senza hardcode.

Per la registrazione hai due strade sane:

* **`pluggy`**, che è nato proprio come sistema di plugin e hook ben definiti;
* **entry points** via `importlib.metadata`, che in Python sono il modo standard per esporre componenti installati e scoprirli a runtime.

`pluggy` è molto adatto quando vuoi definire hook spec chiari e far convivere più implementazioni; `importlib.metadata` è perfetto per scoprire plugin installati tramite entry points. ([pluggy.readthedocs.io][4])

Quindi, in soldoni:

* **contratti dati**: Pydantic
* **contratti di comportamento**: `Protocol`
* **plugin loading**: `pluggy` oppure entry points
* **payload e run registry**: storage separato

### 4) File sorvegliati o mini database? La mia risposta è: **ibrido**, ma con il database al centro

Fra le due opzioni che proponi, io **non baserei il sistema principale su file watch**.

`watchdog` fa il suo mestiere: monitora eventi del filesystem. Quindi è utile per rilevare “è apparso/modificato un file”. Ma quello è un fatto fisico, non un fatto semantico. Un file può comparire mentre è ancora incompleto, può essere riscritto, può esistere ma non essere validato, può essere il risultato di un run fallito. `watchdog` vede eventi di file system, non “artefatto semanticamente pronto”. ([Watchdog][5])

Per questo io farei così:

**A. Artefatti su disco**
XML, JSON, YAML, CSV, MD, GEXF, dump SQL, report: stanno su filesystem, con path stabile e hash.

**B. Registry / journal in SQLite**
Lo stato vive in un piccolo DB locale: run, artifact, dependency, check, lock, error, lineage. SQLite è perfetto per questo scenario perché è embedded, serverless, zero-configuration e transazionale; con WAL guadagni anche migliore concorrenza locale. ([SQLite][6])

**C. SQLAlchemy come access layer, non come religione**
SQLAlchemy va benissimo come layer di accesso al registry, specie per transazioni e per non spargere SQL grezzo ovunque. Le sue docs trattano sia la gestione delle transazioni sia le particolarità di SQLite. ([SQLAlchemy Documentation][7])

Questa soluzione ti dà il meglio dei due mondi:

* filesystem per i payload pesanti e ispezionabili;
* SQLite per sapere **che cosa esiste davvero**, **in che stato è**, **chi l’ha prodotto**, **da cosa dipende**.

### 5) Quindi: come “avverte” il modulo successivo?

Non con un file buttato in una cartella e speriamo bene.

Il modulo produttore deve fare, in ordine:

1. scrivere il payload su disco;
2. calcolare hash e metadata;
3. registrare l’artefatto nel registry;
4. marcare lo stato del run come `produced`;
5. eseguire i check minimi;
6. marcare `validated` oppure `failed`.

Il consumatore successivo non guarda il filesystem: guarda il registry e parte solo se trova un artefatto compatibile:

* del tipo giusto;
* della versione giusta;
* in stato `validated`;
* non superseded;
* con dipendenze risolte.

Questa è la differenza fra un progetto che “sembra andare” e uno che regge davvero.

### 6) La scelta pratica: niente broker adesso

Ci sarebbe una terza famiglia di soluzioni: message broker, code, eventi veri e propri. Ma qui, onestamente, sarebbe quasi certamente overkill.

Per una pipeline locale/modulare di modernization:

* **watchdog da solo**: troppo fragile
* **broker tipo Rabbit/Kafka**: troppo pesante adesso
* **filesystem + SQLite registry**: giusto equilibrio

Più avanti, se il progetto diventa multi-worker o multi-macchina, quel registry può diventare Postgres e l’orchestrazione può salire di livello. Ma adesso non ne hai bisogno.

### 7) Orchestratore custom o framework tipo Dagster / Prefect?

La mia risposta pratica è questa:

* **adesso**: orchestratore tuo, semplice, basato sul registry;
* **design**: ispirato ai concetti giusti dei framework moderni;
* **migrazione eventuale**: possibile, senza buttare via il lavoro.

Perché lo dico:

* **Dagster** è molto forte se ragioni in termini di **asset** con dipendenze, lineage, observability e checks. È praticamente il modello mentale più vicino a quello che stai descrivendo. ([Dagster Docs][8])
* **Prefect** è molto forte per flow/task orchestration, tracking degli stati, scheduling ed eventi/deployment trigger. ([Prefect][9])

Però introdurre subito Dagster o Prefect in un progetto che deve ancora trovare il proprio vocabolario può appesantire inutilmente. Meglio prendere da loro i concetti giusti:

* asset / artifact
* dependency graph
* checks
* runs
* events
* retries
* lineage

…e tenerli in un tuo orchestratore locale leggero.

### 8) La mia raccomandazione precisa: architettura in 4 strati

#### Strato 1 — Domain contracts

Qui stanno solo:

* modelli Pydantic;
* JSON Schema esportati;
* enum canonici;
* versioni di schema;
* tipi di artifact, check, relation, status.

Questo è il tuo **latinorum ufficiale**.

#### Strato 2 — Module interface / plugin layer

Qui stanno:

* `Protocol` dei moduli;
* dichiarazione di capability;
* registrazione plugin;
* loader dei moduli.

Questo è il tuo **sistema di innesti**.

#### Strato 3 — Runtime shared services

Qui stanno:

* artifact store;
* registry SQLite;
* locking;
* hashing;
* config;
* logging;
* tracing.

Per tracing e osservabilità, OpenTelemetry è oggi lo standard di fatto lato traces/metrics/logs. Non è obbligatorio al giorno uno, ma è la direzione giusta se vuoi poter seguire una run attraverso i moduli. ([OpenTelemetry][10])

#### Strato 4 — Business modules

Qui vivono davvero i moduli:

* ingestion Oracle Forms
* ingestion Oracle DB
* ingestion documentazione sporca
* graph merge / DSL builder
* gephi export
* Bob view export
* quality / reconciliation

Ogni modulo è stupido nel senso buono: consuma artefatti, produce artefatti, pubblica check.

### 9) La “rosetta” che fisserei da subito, in forma quasi contrattuale

Io fisserei immediatamente queste convenzioni, e da lì in poi non si discute più.

#### Naming

* artifact types in lower snake o dotted namespace: `oracle.forms.analysis_bundle`
* module names stabili: `oracle_forms_ingest`, `oracle_db_ingest`, `dsl_builder`, `gephi_exporter`
* schema version in semver: `1.0.0`

#### Envelope obbligatorio

Ogni payload, senza eccezioni, ha:

* `schema_version`
* `artifact_type`
* `producer_module`
* `run_id`
* `content_hash`

#### Output immutabile

Un artefatto prodotto non si modifica “in place”.
Se cambia, si genera una nuova versione o un nuovo artifact id.

#### Check obbligatorio

Ogni modulo deve pubblicare almeno:

* check di struttura;
* check di compatibilità schema;
* check di completezza minima.

#### Idempotenza dichiarata

Ogni modulo dichiara se a parità di input produce lo stesso output.

#### Merge policy dichiarata

Per ogni artifact type deve essere chiaro se il consumer:

* sostituisce;
* mergea;
* accoda;
* materializza una snapshot.

Questa roba sembra pedante, ma è quella che ti salva quando il progetto diventa grosso e ti “scoppia in mano”.

### 10) La scelta concreta fra le tue opzioni

La mia scelta, senza troppi giri, sarebbe questa:

**non watchdog come motore principale**
**non database unico per contenere tutto il payload**
**sì a SQLite come run/artifact registry**
**sì a filesystem come artifact store**
**sì a contratti Pydantic + JSON Schema come lingua comune**
**sì a Protocol/pluggy per rendere i moduli sostituibili**

In formula:

**artifact store su file + registry SQLite + moduli plugin + contratti versionati**

### 11) La parte più importante per lavorare bene “modulo per modulo” in chat diverse

Per evitare che io driftando ti generi moduli incompatibili, i moduli futuri devono tutti essere scritti contro **lo stesso pacchetto contratti**.

In pratica, prima ancora di scrivere il modulo Oracle Forms o il modulo Gephi, va stabilito un piccolo nucleo condiviso:

* `artifact envelope`
* `run status`
* `check result`
* `capability declaration`
* `canonical enums`
* `schema versions`

Una volta bloccato quel nucleo, i moduli si possono davvero generare in chat separate, perché ciascuno targetta la stessa “costituzione”.

### 12) Conclusione operativa

Quindi sì:

* **un sistema modulare del genere ha assolutamente senso**;
* **la separazione in moduli è una buona idea tecnica e anche una buona idea anti-drift**;
* **si può stabilire da subito una stele di rosetta comune**;
* **io baserei lo scambio su un sistema ibrido, con SQLite al centro e file come payload**;
* **watchdog lo userei al massimo come comodità locale, non come semaforo ufficiale**.

La forma mentale giusta è questa:

**i moduli non si passano chiamate; si passano artefatti.
gli artefatti non valgono perché esistono; valgono perché sono registrati, versionati e validati.
il registry non contiene il mondo; contiene la verità operativa sul mondo.**

Ed è, per inciso, molto allineato con la linea che avevamo già tracciato nei file del progetto: modello canonico unico, generatori di viste, export specializzati, e niente fiducia cieca nella magia del naming.   

[1]: https://docs.python.org/3/library/typing.html?utm_source=chatgpt.com "typing — Support for type hints"
[2]: https://docs.pydantic.dev/latest/concepts/json_schema/?utm_source=chatgpt.com "JSON Schema - Pydantic Validation"
[3]: https://docs.dagster.io/api/dagster/assets?utm_source=chatgpt.com "assets"
[4]: https://pluggy.readthedocs.io/?utm_source=chatgpt.com "pluggy — pluggy 0.1.dev96+gfd08ab5 documentation"
[5]: https://python-watchdog.readthedocs.io/?utm_source=chatgpt.com "Watchdog — watchdog 2.1.5 documentation"
[6]: https://sqlite.org/about.html?utm_source=chatgpt.com "About SQLite"
[7]: https://docs.sqlalchemy.org/en/latest/orm/session_transaction.html?utm_source=chatgpt.com "Transactions and Connection Management"
[8]: https://docs.dagster.io/?utm_source=chatgpt.com "Dagster Docs: Overview"
[9]: https://docs.prefect.io/v3/get-started?utm_source=chatgpt.com "Prefect Docs"
[10]: https://opentelemetry.io/docs/languages/python/?utm_source=chatgpt.com "Python"

----
----

sei il mio esperto di chatgpt, in particolare di chatgpt 5.4 thinking. vorrei che prendessi questo progetto che abbiamo analizzato fino a qui e teorizzassi qual è il modo più sicuro e affidabile di realizzarlo con te.

io ho in mente due strade:

* opzione 1: rileggi le chat relative al sistema di scrittura di coral hart: sostanzialmente, si tratta di una serie di prompt che, partendo da un progetto di massimo iniziale, vanno ad affinarne successivamente (e iterativamente) le diverse sezioni, usando dei file comuni, salvati nella directory di progetto, come guida e come sistema di controllo per tenere la generazione sui binari.

* opzione 2: codex. che però ammetto di non conoscere abbastanza per sapere se fa un lavoro affidabile.

* opzione 3..n: altro che non saprei dire e che casomai ti chiedo di suggerire nel caso penso possa funzionare meglio delle altre opzioni.

pensaci attentamente, passo per passo.

----
----

La strada più sicura non è scegliere **ChatGPT Project** oppure **Codex**. È usarli in modo diverso:

**ChatGPT 5.4 Thinking = architetto / revisore / generatore di specifiche.**
**Codex = esecutore sul repository / implementatore / runner di test.**
**Git + file canonici = memoria vera del progetto.**

Il motivo è semplice: i Projects di ChatGPT possono usare chat, file caricati e istruzioni del progetto come contesto condiviso; Codex invece è fatto per lavorare direttamente su un repo, modificare file ed eseguire comandi/test nel progetto. Quindi il metodo “Coral Hart” è ottimo per progettare e controllare la direzione, ma Codex è più adatto quando il codice diventa un sistema reale. ([OpenAI Help Center][1])

### Verdetto

Io farei così:

**Opzione migliore: ibrida.**

Non:

* solo prompt iterativi in ChatGPT;
* solo Codex “vai e costruisci tutto”.

Ma:

1. **ChatGPT Project** per definire teoria, architettura, contratti, DSL, manifest, naming, ADR, test strategy.
2. **Repository Git** come fonte reale di verità.
3. **Codex CLI / Codex app** per implementare moduli piccoli, uno alla volta, dentro il repo.
4. **AGENTS.md** come equivalente tecnico dei “file di controllo” del metodo Coral Hart.
5. **test automatici + golden files** come guardrail contro drift e regressioni.

Codex legge `AGENTS.md` prima di lavorare e può usare istruzioni stratificate globali/progetto; le best practice ufficiali dicono proprio di trattarlo come un teammate configurato nel tempo, con contesto stabile, workflow e istruzioni durevoli. ([OpenAI Developers][2])

### Perché non basta ChatGPT Project

ChatGPT Project è eccellente per:

* ragionare;
* progettare;
* documentare;
* confrontare alternative;
* costruire prompt e specifiche;
* mantenere coerenza concettuale.

Ma per un progetto Python modulare grosso ha un limite naturale: la chat non è il filesystem vivo del progetto. Può leggere file caricati o connettori, ma la forma più robusta per un codice che evolve resta un repo con test, diff, commit e istruzioni di progetto. ChatGPT può collegarsi a GitHub e leggere repo/contenuti, ma Codex è lo strumento pensato per modificare codice ed eseguire comandi nel progetto. ([OpenAI Help Center][3])

### Perché non userei Codex da solo

Codex è forte quando il task è chiaro: “implementa questo modulo”, “aggiungi questi test”, “rifattorizza questa classe”, “correggi questo bug”. È meno ideale come unico luogo dove decidere la teoria generale del sistema.

Nel tuo caso il rischio non è solo scrivere codice sbagliato. È costruire il sistema con concetti incoerenti: oggi `artifact`, domani `dataset`, dopodomani `bundle`, poi `snapshot`, e in due settimane hai Frankenstein col badge aziendale.

Per questo prima serve una **costituzione del progetto**.

### La struttura che userei

Nel repo metterei subito questi file canonici:

```text
/AGENTS.md
/docs/PROJECT_CHARTER.md
/docs/ARCHITECTURE.md
/docs/ROSETTA_STONE.md
/docs/DSL_SPEC.md
/docs/ARTIFACT_CONTRACTS.md
/docs/MODULE_CONTRACTS.md
/docs/TEST_STRATEGY.md
/docs/ADR/
```

Il file più importante è `ROSETTA_STONE.md`: contiene vocabolario, tipi di artefatto, stati, naming, schema version, relation types, regole di compatibilità.

`AGENTS.md` invece dice a Codex come deve comportarsi sempre: non rigenerare tutto, non cambiare contratti senza ADR, non rompere API pubbliche, aggiungere test, aggiornare docs solo dove richiesto, usare CMD quando si scrivono istruzioni Windows.

### Metodo operativo consigliato

Ogni modulo nasce con questa sequenza:

1. **Spec in ChatGPT**

   * scopo del modulo;
   * input artifact;
   * output artifact;
   * errori;
   * test;
   * casi limite;
   * cosa non deve fare.

2. **Contratto nel repo**

   * schema Pydantic / JSON Schema;
   * esempio minimo;
   * golden input/output.

3. **Task Codex**

   * implementa solo quel modulo;
   * non modificare contratti non correlati;
   * esegui test;
   * aggiorna report.

4. **Review in ChatGPT**

   * controllo architetturale;
   * controllo drift;
   * controllo naming;
   * controllo coerenza con `ROSETTA_STONE.md`.

5. **Commit piccolo**

   * un modulo;
   * una responsabilità;
   * test associati.

### Prompt pattern da usare con me

Per progettazione:

```text
Usa i file PROJECT_CHARTER.md, ROSETTA_STONE.md, ARTIFACT_CONTRACTS.md e MODULE_CONTRACTS.md come vincoli. Progetta il modulo X senza scrivere codice. Produci: scopo, input, output, errori, test, casi limite, impatto sui contratti.
```

Per Codex:

```text
Read AGENTS.md first. Implement module X according to docs/MODULE_CONTRACTS.md and docs/ARTIFACT_CONTRACTS.md. Do not change public contracts unless explicitly required. Add tests and golden files. Run the test suite. Report changed files and remaining risks.
```

Per revisione:

```text
Confronta l’implementazione del modulo X con ROSETTA_STONE.md, ARTIFACT_CONTRACTS.md e TEST_STRATEGY.md. Cerca incoerenze, naming drift, accoppiamenti indebiti, test mancanti e rischi di regressione.
```

### La parte anti-drift

Il vero antidoto al drift non è “avere una chat più lunga”. È avere file piccoli, autoritativi e testabili.

Quindi:

* nessuna chat deve essere la memoria finale;
* nessuna risposta deve diventare codice senza passare dal repo;
* nessun modulo deve essere accettato senza test;
* nessun contratto deve cambiare senza ADR;
* nessun export deve essere considerato valido senza golden file.

Qui Codex aiuta perché può lavorare nel repo, eseguire test e proporre modifiche verificabili; ChatGPT aiuta perché ragiona meglio sulla coerenza complessiva. Codex cloud può anche lavorare in sandbox isolata e produrre codice da rivedere/mergiare, ma per questo progetto lo userei sempre con compiti piccoli e controllati. ([OpenAI Help Center][4])

### La roadmap più affidabile

Fase 1: **fondamenta**

* repo vuoto;
* `AGENTS.md`;
* rosetta;
* contratti artefatti;
* struttura package;
* test harness.

Fase 2: **vertical slice minima**

* ingestion finta Oracle DB;
* artifact registry minimale;
* DSL graph minimale;
* export GEXF minimale;
* test end-to-end.

Fase 3: **moduli reali**

* Oracle DB ingestion;
* Oracle Forms XML ingestion;
* document evidence ingestion;
* DSL builder;
* Gephi exporter;
* Bob view exporter.

Fase 4: **qualità**

* reconciliation;
* discrepancy reports;
* provenance;
* staleness;
* golden files;
* regression suite.

### Scelta finale

La soluzione più sicura è:

**ChatGPT Project per pensare e scrivere specifiche.
Codex per modificare il repo.
AGENTS.md + ROSETTA_STONE.md per tenere tutti allineati.
Test automatici per decidere se una cosa è vera.**

Il motto operativo sarebbe:

**prima contratti, poi moduli; prima vertical slice, poi copertura; prima test, poi ambizione.**

[1]: https://help.openai.com/en/articles/10169521-projects-in-chatgpt?utm_source=chatgpt.com "Projects in ChatGPT"
[2]: https://developers.openai.com/codex/guides/agents-md?utm_source=chatgpt.com "Custom instructions with AGENTS.md – Codex"
[3]: https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt?utm_source=chatgpt.com "Connecting GitHub to ChatGPT"
[4]: https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan?utm_source=chatgpt.com "Using Codex with your ChatGPT plan"

----
----

sei il mio esperto di comprimere diversi concetti in poco spazio a uso e consumo di te stesso, ossia: vorrei che comprimessi tutta questa discussione che abbiamo avuto finora in una sorta di "punto di salvataggio" testuale che possa diventare un prompt per te, nel caso in cui debba far ripartire la discussione. se per caso hai bisogno di integrare file di esempio nel prompt (es. tutti quelli che hai prodotto finora), non farlo, e metterli in uno .zip a parte da scaricare.

dopo andiamo avanti col progetto, ma vorrei un punto fisso da cui eventualmente ricominciare se entrambi perdessimo la bussola.

----
----

Non serve uno zip: qui basta un prompt-punto di salvataggio. Ho solo ricontrollato i riferimenti ufficiali utili: ChatGPT Projects gestisce file/contesto di progetto, Codex lavora sul repo ed esegue codice/comandi, e `AGENTS.md` è il file guida stabile per Codex. ([OpenAI Help Center][1])

```text
Sei il mio esperto di Python, AI, Oracle, Oracle Forms, database design, DSL, C4, Gephi, IBM Project Bob, modernization e architetture modulari che non devono esplodere.

Stiamo progettando un sistema Python modulare per modernizzare un applicativo legacy Oracle Forms + Oracle DB. L’obiettivo non è generare subito codice, ma costruire una base affidabile, testabile e riutilizzabile per estrarre conoscenza dal legacy e produrre viste utili a IBM Project Bob e ad altri strumenti.

Idea centrale:
costruire un DSL / knowledge graph canonico come source of truth, non un semplice diagramma. Mermaid, DBML, Structurizr, GEXF/Gephi e viste per Bob sono solo output generati dal modello canonico.

Fonti principali:
1. Oracle DB metadata: tabelle, colonne, constraint, FK, trigger, package, procedure, function, source, DDL, dipendenze.
2. Oracle Forms XML: file .fmb convertiti via Forms2XML / frmf2xml, con form, block, item, canvas, window, trigger, built-in, CALL_FORM, OPEN_FORM, GO_BLOCK, parameter list, global variables, program units.
3. Documentazione sporca: manuali, ticket, change request, email, note, analisi umane. Queste fonti non diventano automaticamente verità canonica: entrano come evidence layer.
4. Eventuali altri database o fonti future tramite adapter.

Principio fondamentale:
separa sempre:
- fatti canonici: estratti da fonti strutturate e verificabili;
- inferenze: deduzioni del parser o dell’analisi;
- evidenze: documenti o note che supportano un claim ma non provano da soli la verità;
- conflitti: discrepanze tra fonti diverse;
- tempo/staleness: età del dato, first_seen, last_seen, source_date, observed_at.

Il DSL deve modellare un grafo tipizzato:
entity kinds: application, domain, form_module, block, item, trigger, program_unit, routine, table, view, column, constraint, index, package, procedure, function, document_evidence, claim.
relation kinds: contains, displays, invokes, navigates_to, passes_parameter, sets_global, reads, writes, validates_with, looks_up, depends_on, implemented_by, described_by, supports_claim.

Output desiderati:
- GEXF per Gephi, con attributi su nodi/archi e possibilmente dimensione temporale;
- Mermaid per viste rapide;
- DBML per schema dati;
- Structurizr DSL / C4 per viste architetturali;
- bundle testuale/markdown/json adattato a IBM Project Bob;
- report qualità/discrepanze.

Architettura del programma:
non una collezione di script, ma moduli indipendenti che scambiano artefatti contrattualizzati.

Moduli ipotizzati:
- oracle_db_ingest
- oracle_forms_ingest
- dirty_docs_ingest
- evidence_extractor
- dsl_builder
- graph_reconciler
- quality_checker
- gephi_exporter
- bob_view_exporter
- adapter_manager

Regola architetturale:
i moduli non si chiamano direttamente e non dipendono dalle classi interne degli altri moduli. Consumano e producono artifact tipizzati, versionati e validati.

Sistema di interscambio consigliato:
- payload pesanti su filesystem: JSON, YAML, XML, CSV, MD, GEXF;
- registry locale SQLite per run, artifact, stato, hash, provenance, dipendenze, check, errori;
- SQLAlchemy come access layer;
- Pydantic / JSON Schema per contratti dati;
- Python Protocol o ABC leggere per interfacce dei moduli;
- pluggy o entry points per plugin sostituibili;
- watchdog solo come comodità opzionale, non come semaforo ufficiale.

Lifecycle artifact:
declared → queued → running → produced → validated → failed / superseded.

Ogni artifact deve avere almeno:
artifact_id, artifact_type, schema_version, producer_module, run_id, created_at, content_ref, content_hash, source_refs, depends_on, quality_status, provenance.

Ogni modulo deve dichiarare capability:
- artifact consumati;
- artifact prodotti;
- versioni supportate;
- check eseguiti;
- idempotenza;
- politica di merge/snapshot;
- errori attesi.

Autotest obbligatori:
- coerenza interna del grafo;
- aderenza alle fonti originarie;
- nodi/relazioni unresolved espliciti, mai silenziosamente persi;
- conflict detection;
- golden files input/output;
- export GEXF/Mermaid/DBML/Structurizr validabili;
- regression suite per evitare drift.

Metodo di lavoro con ChatGPT/Codex:
ChatGPT 5.4 Thinking serve come architetto, progettista, revisore e generatore di specifiche.
Codex serve come implementatore sul repository, con task piccoli, testabili e vincolati.
Git e i file canonici del repo sono la memoria vera, non la chat.

File fondamentali del repo:
AGENTS.md
docs/PROJECT_CHARTER.md
docs/ARCHITECTURE.md
docs/ROSETTA_STONE.md
docs/DSL_SPEC.md
docs/ARTIFACT_CONTRACTS.md
docs/MODULE_CONTRACTS.md
docs/TEST_STRATEGY.md
docs/ADR/

AGENTS.md deve vincolare Codex:
- leggere sempre i contratti prima di modificare codice;
- non cambiare API/contratti senza ADR;
- implementare un modulo alla volta;
- aggiungere test;
- non rigenerare tutto il progetto;
- rispettare naming, artifact types e schema version;
- preferire istruzioni Windows CMD quando si scrivono comandi per l’utente.

ROSETTA_STONE.md è la costituzione del progetto:
contiene vocabolario canonico, artifact types, entity kinds, relation kinds, stati, naming, versioning, regole di compatibilità.

Roadmap:
1. Fondamenta: repo, AGENTS.md, rosetta, contratti artifact, struttura package, test harness.
2. Vertical slice minima: ingestion finta Oracle DB → artifact registry → DSL graph minimale → export GEXF → test end-to-end.
3. Moduli reali: Oracle DB, Oracle Forms XML, documentazione sporca, DSL builder, Gephi, Bob.
4. Qualità: reconciliation, evidence layer, staleness, discrepancy report, golden files, regression.

Regola di stile progettuale:
prima contratti, poi moduli.
prima vertical slice, poi copertura.
prima test, poi ambizione.
niente “magia” non tracciata.
nessuna fonte sporca deve contaminare il core canonico.
nessun diagramma è source of truth.
```

[1]: https://help.openai.com/en/articles/10169521-projects-in-chatgpt?utm_source=chatgpt.com "Projects in ChatGPT"






