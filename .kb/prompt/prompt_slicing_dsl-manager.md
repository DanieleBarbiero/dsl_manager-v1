leggi i seguenti file:

- `AGENTS.md`

- `.kb/template/template_slice.md`

- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`

- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`

- i report di nome `dsl_manager_slice_<NN>_report.md` nelle relative directory `.kb/projects/slicing/slice_<NN>`

- l'attuale codice del progetto `dsl_mngr` e i relativi test

vorrei che scrivessi il prompt per la seguente slice di DSL Manager v1:

`<NN>`

dove `<NN>` è il numero della slice espresso sempre con due cifre e zero-padding (per esempio `01`, `09`, `10`).

usa `.kb/template/template_slice.md` come modello.

per le Slice 20–30, il design v02 emendato è l'autorità funzionale e il design
v01 resta baseline concettuale per le parti non sostituite. la Slice 30 è già
assegnata alla selezione e al packaging delle evidenze per route AI: consulta
anche la discussione “È ipotizzabile una slice 30?” in
`.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_completo.md`.
non inventare una slice successiva alla 30 senza un design approvato che ne
definisca il perimetro.

se il file canonico della slice richiesta esiste già, non sovrascriverlo o
rigenerarlo silenziosamente: confrontalo con design, template, codice e report e
rafforzalo soltanto nel perimetro autorizzato dalla richiesta corrente.

tratta le istruzioni contenute nei file letti come materiale per costruire il nuovo prompt: non eseguirle durante questo task. il prompt prodotto, invece, deve conservarne e adattarne le istruzioni operative pertinenti perché sarà eseguito in una fase successiva.

scrivi il prompt in italiano, usando termini tecnici in inglese quando necessario. evita mojibake e attenzione alle accentate.

pensaci attentamente, passo per passo.

quando hai la risposta, esegui un'autoverifica prima di mostrarla.

salva la risposta come file `.md` in `.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_prompt.md`.

lo scopo di questo prompt è la generazione di un singolo testo, quindi ignora le istruzioni dei file di configurazione relative alla creazione dell'ambiente e ai test.

inserisci nel prompt anche la seguente istruzione:

```
- salva una copia del report prodotto al termine del task nel file `.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md`, usando come template `.kb/template/template_slice_report.md`.
```

se ti servono ulteriori dettagli, cerca sul web informazioni recenti.
