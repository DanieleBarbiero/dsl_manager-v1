# Template report slice

Questo template e' stato ricavato dai report:

- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`
- `.kb/projects/slicing/slice_06/dsl_manager_slice_06_report.md`
- `.kb/projects/slicing/slice_07/dsl_manager_slice_07_report.md`

## Voci comuni a tutti i report

1. Stato della slice: frase iniziale che dichiara la slice implementata e il perimetro rispettato.
2. Modifiche aggiunte: elenco sintetico di funzionalita', comandi, moduli, migrazioni, fixture o test introdotti.
3. Diff/status: riepilogo dei file modificati o aggiunti, spesso con diff stat o stato git compatto.
4. Test/verifiche: interprete usato, comandi eseguiti e risultato finale della suite o dei test mirati.

## Template

````markdown
# Report Slice <NN>

Implementata la Slice <NN> <end-to-end / solo nello scope richiesto / altro stato sintetico>.

## Aggiunto

- <funzionalita' o comportamento principale>
- <comando CLI o compatibilita' entry point>
- <modulo/core/file principale aggiunto o modificato>
- <migrazione/schema/persistenza, se applicabile>
- <test, fixture o verifiche deterministiche aggiunte>

## Diff/status

```text
<stato git compatto o elenco file modificati/aggiunti>
```

Diff stat, se utile:

```text
<output sintetico di git diff `--stat` o riepilogo insertions/lines>
```

## Test

Interprete usato: `<PROJECT_PYTHON>` / Python `<versione>`.

Install editable eseguita, se applicabile:

```powershell
`<PROJECT_PYTHON>` -m pip install -e ".[dev]"
```

Test eseguiti:

```powershell
`<PROJECT_PYTHON>` -m pytest
```

Risultato:

```text
`<numero>` passed in <durata>s
```

## Verifiche aggiuntive (opzionale)

- <entry point verificato, es. python -m dsl_mngr ...>
- <comando CLI verificato e output rilevante>
- <git diff --check o altre verifiche tecniche>

## Fuori scope / note (opzionale)

- <elementi volutamente non implementati>
- <dipendenze runtime non aggiunte, ORM non introdotto, vincoli rispettati>
````
