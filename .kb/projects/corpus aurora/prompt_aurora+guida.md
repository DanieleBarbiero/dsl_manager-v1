leggi i seguenti file:

- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`

- i report di nome `dsl_manager_slice_<NN>_report.md` nelle relative directory `.kb/projects/slicing/slice_<NN>`, dove `<NN>` è espresso con due cifre e zero-padding

- l'attuale codice del progetto `dsl_mngr` e relativi test

vorrei che ti facessi una chiara idea del progetto e di come funziona, e poi producessi i seguenti file:

- un corredo di file che rappresenti una applicazione mock obsoleta da modernizzare. non troppo estesa o complicata, ma abbastanza complessa da utilizzare le risorse del `dsl-manager`: documenti (di vari formati) da distinguere in vecchi e nuovi, utili e disutili alla modernizzazione, dump di database Oracle, una serie di semplici interfacce Oracle Forms di cui `dsl-manager` possa fare il parsing, codice `PL/SQL`, e quant'altro ritieni necessario. racchiudi il tutto in un file `.zip` da salvare nella root del progetto.

- una guida per principianti assoluti all'utilizzo di `dsl-manager`, che utilizzi il corpus di esempio che hai prodotto al punto precedente. la guida deve procedere per step, istruendo l'utente su come utilizzare il corpus di esempio per esplorare le varie funzioni di `dsl-manager`. l'idea è di presentare un ciclo completo di lavoro: dai file grezzi al dsl, passando per la preparazione di package da e per l'ai, fino ad arrivare all'esportazioni di grafi. salva anche questa guida nella root del progetto.

tutti i file devono essere in italiano (salvo dove è necessario l'inglese tecnico), per cui attenzione alle accentate: evita mojibake.

pensaci attentamente, passo per passo. prima di produrre la risposta finale, esegui una autoverifica per verificare che tutti i punti della richiesta siano stati soddisfatti.
