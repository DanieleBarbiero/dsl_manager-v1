# Laboratorio Vega Ricambi

**Versione del laboratorio: 1.0**

Vega Ricambi è uno scenario completamente fittizio e molto piccolo pensato per
collaudare `dsl_manager-v1` senza trasformare ogni test in un'attesa lunga per
Docling.

La regola di progetto è intenzionale:

- **6 fonti operative in tutto**;
- **solo 2 fonti passano da normalizzazione + chunking Docling**;
- **1 campione DDL**;
- **1 campione PL/SQL / database code**;
- **1 campione Oracle Forms XML**;
- **1 campione log**;
- **1 DOCX**;
- **1 XLSX**.

Il corpus normale non contiene duplicati dello stesso formato, PDF, PPTX,
HTML, TXT o XLSM. Aurora e Orione restano i laboratori di copertura larga;
Vega serve come **smoke test rapido e ripetibile**.

## Se vuoi soltanto eseguire il laboratorio

Apri PowerShell nella root del repository `dsl_manager-v1` e avvia:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.kb\projects\laboratorio_vega_ricambi\materiale_di_supporto\laboratorio_vega_ricambi_interattivo_v_02.ps1
```

Se hai estratto questo ZIP fuori dal repository, copia la cartella sotto
`.kb\projects\` oppure passa allo script soltanto dopo averlo collocato in una
sottocartella del repository. Lo script trova la root risalendo fino a
`AGENTS.md`, `pyproject.toml` e `.codex\config.toml`.

> Lo script **non è un secondo DSL Manager**. È un tutor. Le operazioni
> applicative sono sempre eseguite con `python -m dsl_mngr`.

## Se qualcosa si interrompe

Lo script crea una sessione con un file:

```text
session_state.json
```

e stampa un comando di ripresa completo. Copialo e conservalo. Esempio:

```powershell
.\laboratorio_vega_ricambi_interattivo_v_02.ps1 -Resume "C:\...\session_state.json"
```

Il salvataggio contiene anche il percorso del workspace. Se cambi il workspace
prima dell'inizializzazione, il nuovo percorso viene scritto immediatamente
nello stato. Dopo l'inizializzazione non viene permesso di "spostare" il
workspace nella stessa sessione: database, ID e artefatti appartengono al
workspace già creato.

## Perché l'output in console è corto

Ogni comando produce file separati:

```text
logs\NNN_nome-comando.stdout.log
logs\NNN_nome-comando.stderr.log
logs\commands.jsonl
```

In console vengono mostrati soltanto:

- cosa sta succedendo;
- perché;
- exit code;
- durata;
- pochi campi utili o poche righe;
- percorso del log completo.

Quindi un JSON di migliaia di righe non cancella visivamente la spiegazione
dello step precedente.

## Ordine consigliato di lettura

1. questo file;
2. `materiale_di_supporto/GUIDA_COMPLETA_POWERSHELL.md`;
3. `materiale_di_supporto/checklist_risultati_attesi.md`;
4. `materiale_di_supporto/matrice_fixture_attesi.md`;
5. soltanto se serve: `materiale_di_supporto/limitazioni_intenzionali.md`;
6. per idee di evoluzione del prodotto:
   `materiale_di_supporto/SUGGERIMENTI_MIGLIORAMENTO.md`.

## Cosa non fare

Non lavorare direttamente dentro `corpus/active` di questa fixture.
Lo script ne copia i byte in un workspace separato e verifica gli hash.

Non mettere `fixture_controllate` nel corpus normale. Il workbook malformato
serve soltanto a una prova diagnostica esplicita.

Non inventare ID `RUN_*`, `REV_*`, `AISEL_*`, `AIPKG_*`, `CREC_*` o `DSL_*`.
Usa sempre quelli realmente prodotti dal workspace corrente.

Non cancellare un workspace solo perché un comando fallisce. I report e i log
del fallimento sono spesso la parte più utile del test.
