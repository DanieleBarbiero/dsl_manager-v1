# Istruzioni di applicazione — prompt Slice 20–29 DSL Manager v1

## Contenuto del pacchetto

Il pacchetto è volutamente separato dal repository GitHub e non contiene commit o PR.

- `repo_overlay/` — **file da copiare nel repository**:
  - `.kb/modifica_prompt_slice_v2.md`
  - `.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md`
  - ...
  - `.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md`
- `tools/apply_design_update.py` — applicatore sicuro della modifica al design v02; **non è destinato al commit**.
- `reference/design_document_v_02.modified.preview.md` — preview per revisione; **non sovrascrivere il design del clone con questo file**.
- `reference/PATCH_design_document_v_02.diff` — patch di riferimento/fallback; usare solo se `git apply --check` passa. Lo script guarded è preferibile.
- `AUDIT_FINALE.md`, `MANIFEST.json`, `SHA256SUMS.txt` — documentazione del pacchetto; non sono destinati al repository.

## Procedura raccomandata

Parti da un clone locale aggiornato di `DanieleBarbiero/dsl_manager-v1` e **non perdere eventuali modifiche locali**.

### 1. Controlla lo stato del clone

Dalla root del repository:

```text
git status --short --branch
git branch --show-current
```

Se hai modifiche non correlate, salvale/committale/stashale secondo il tuo normale workflow prima di applicare questo pacchetto.

### 2. Verifica la baseline del design

```text
git hash-object ".kb/documenti/documenti di design/run 2/design_document_v_02.md"
```

Il valore atteso per la baseline verificata durante la preparazione del pacchetto è:

```text
8aa78b1210216b78d97e4e2554b075a7c1b462df
```

Se è diverso, **fermati**: il design è cambiato rispetto alla baseline usata per questo lavoro. Non usare `--force-baseline` come scorciatoia; confronta prima le differenze.

### 3. Copia l'overlay nel repository

Copia **il contenuto di `repo_overlay/` nella root del repository**, mantenendo i path.

In PowerShell, dalla directory che contiene il pacchetto:

```text
Copy-Item -Recurse -Force ".\repo_overlay\.kb\*" "C:\PERCORSO\dsl_manager-v1\.kb\"
```

Oppure copia manualmente i file mantenendo esattamente questa struttura:

```text
.kb/
├── modifica_prompt_slice_v2.md
└── projects/
    └── slicing/
        ├── slice_20/dsl_manager_slice_20_prompt.md
        ├── slice_21/dsl_manager_slice_21_prompt.md
        ├── slice_22/dsl_manager_slice_22_prompt.md
        ├── slice_23/dsl_manager_slice_23_prompt.md
        ├── slice_24/dsl_manager_slice_24_prompt.md
        ├── slice_25/dsl_manager_slice_25_prompt.md
        ├── slice_26/dsl_manager_slice_26_prompt.md
        ├── slice_27/dsl_manager_slice_27_prompt.md
        ├── slice_28/dsl_manager_slice_28_prompt.md
        └── slice_29/dsl_manager_slice_29_prompt.md
```

Non creare `dsl_manager_slice_NN_report.md`: verranno prodotti solo quando le rispettive slice saranno implementate.

### 4. Dry-run della modifica al design

Usa Python 3.12 o un normale Python 3 recente per lo script di applicazione; lo script usa solo standard library e non esegue DSL Manager.

```text
python "PERCORSO_PACCHETTO\tools\apply_design_update.py" "C:\PERCORSO\dsl_manager-v1" --check
```

Il comando deve terminare con:

```text
CHECK PASS: transformation is applicable; no file written.
```

Se lo script segnala un Git blob diverso da `8aa78b…`, non proseguire automaticamente.

### 5. Applica la modifica al design

```text
python "PERCORSO_PACCHETTO\tools\apply_design_update.py" "C:\PERCORSO\dsl_manager-v1"
```

Lo script modifica soltanto:

```text
.kb/documenti/documenti di design/run 2/design_document_v_02.md
```

La trasformazione:

- aggiorna i link delle sezioni 18.1–18.10;
- aggiorna la riga di auto-verifica sui prompt;
- sostituisce i dieci prompt embedded della sezione 22 con un indice ai file canonici esterni;
- verifica che non restino vecchi anchor o blocchi prompt embedded;
- scrive il file atomicamente.

### 6. Verifiche prima del commit

Esegui:

```text
git diff --check
git status --short
git diff --stat
git diff -- ".kb/documenti/documenti di design/run 2/design_document_v_02.md"
```

Controlla che i file nuovi siano esattamente:

```text
.kb/modifica_prompt_slice_v2.md
.kb/projects/slicing/slice_20/dsl_manager_slice_20_prompt.md
...
.kb/projects/slicing/slice_29/dsl_manager_slice_29_prompt.md
```

più la modifica al design v02.

Non è necessario eseguire la suite runtime di DSL Manager per **questa sola migrazione documentale**: i prompt prodotti ordinano invece a Codex di installare/testare il runtime quando verrà implementata ciascuna slice.

### 7. Commit manuale

Dopo la revisione, aggiungi soltanto i file del repository, non `tools/`, `reference/`, `AUDIT_FINALE.md`, `MANIFEST.json` o `SHA256SUMS.txt` del pacchetto.

Esempio:

```text
git add ".kb/modifica_prompt_slice_v2.md"
git add ".kb/documenti/documenti di design/run 2/design_document_v_02.md"
git add ".kb/projects/slicing/slice_20" ".kb/projects/slicing/slice_21" ".kb/projects/slicing/slice_22" ".kb/projects/slicing/slice_23" ".kb/projects/slicing/slice_24" ".kb/projects/slicing/slice_25" ".kb/projects/slicing/slice_26" ".kb/projects/slicing/slice_27" ".kb/projects/slicing/slice_28" ".kb/projects/slicing/slice_29"
git diff --cached --check
git status --short
git commit -m "Add run 2 slice implementation prompts"
git push
```

La scelta del messaggio di commit è ovviamente modificabile.

## Patch di riferimento

`reference/PATCH_design_document_v_02.diff` è conservata per ispezione e come fallback. Se vuoi provarla manualmente:

```text
git apply --check "PERCORSO_PACCHETTO/reference/PATCH_design_document_v_02.diff"
```

Applicala solo se il check passa e dopo aver verificato la baseline. Il metodo raccomandato resta `apply_design_update.py`, perché impone anche il guard sul Git blob remoto verificato.
