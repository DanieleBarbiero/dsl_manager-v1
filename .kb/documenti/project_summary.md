# DSL Manager — project summary

Ultimo aggiornamento: **2026-09-10**.

Questo documento è il punto di ingresso sintetico per persone e assistenti AI.
Riassume identità, vincoli, architettura, workflow e storia delle correzioni. Non
sostituisce i contratti eseguibili: in caso di divergenza prevalgono, nell'ordine,
`AGENTS.md`, `pyproject.toml`, codice/test e documentazione tecnica pertinente.

## Identità e stato

| Campo | Valore |
|---|---|
| Nome progetto/distribuzione | `dsl_mngr` |
| Nome applicazione | DSL Manager |
| Descrizione breve | Applicazione locale per acquisire corpus eterogenei, normalizzare e strutturare evidenze, derivare candidati governati, consolidare fatti/relazioni e produrre DSL e grafi GEXF |
| Versione applicativa | `1.1.0` |
| Stato | Sviluppo attivo; slice 01–29 presenti nel repository |
| Package Python | `dsl_mngr` |
| Layout | `src/`; `src` non è un package importabile |
| CLI | `dsl-manager` oppure `python -m dsl_mngr` |
| Persistenza | SQLite per workspace, con migrazioni versionate |
| Ambiente primario locale | Windows / VS Code, virtual environment `.venv` |

La versione è definita da `pyproject.toml`. Questo riepilogo deve essere
aggiornato quando cambia la release, ma non è la fonte autoritativa del numero
di versione.

## Runtime e dipendenze

| Elemento | Vincolo/versione |
|---|---|
| Python | `>=3.12,<3.13` |
| Interprete locale configurato | `.venv\Scripts\python.exe`, letto da `PROJECT_PYTHON` in `.codex/config.toml` |
| Docling | `2.97.0` |
| lxml | `6.1.2` |
| Test | `pytest` tramite extra `dev` |
| Python verificato nell'ultimo bugfix | `3.12.10` |

Comandi canonici su Windows, da eseguire dalla root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m dsl_mngr
```

Non usare il Python globale e non impostare un `PYTHONPATH` personalizzato. Nel
cloud si usa invece il runtime Python selezionato dall'ambiente.

## Struttura essenziale del repository

```text
src/dsl_mngr/          package applicativo e CLI
tests/                 test, fixture e golden
.kb/                   knowledge base versionata
  documenti/           manuali, design, analisi, bugfix e questo riepilogo
  projects/            slicing e scenari, incluso il corpus Aurora
  prompt/              prompt di progetto
  template/            template documentali riutilizzabili
.wb/                   risorse workbench versionate
.workspaces/           workspace runtime locali; non sono documentazione canonica
```

I nuovi file controllati dal progetto usano `lowercase_snake_case`. Le sequenze
ordinate usano underscore e due cifre, per esempio `bugfix_01_...`.

## Architettura e flusso principale

```text
corpus/active
  -> scan e source registry
  -> parser/normalizzazione isolata
  -> frammenti e manifest tecnici
  -> candidati deterministici oppure package AI opzionale
  -> import di output AI esterno come candidati pending
  -> review governata
  -> merge e riconciliazione
  -> snapshot DSL v1/v2
  -> diff ed export GEXF
```

Responsabilità principali:

- `dsl_mngr.cli`: comandi, validazione degli argomenti, output ed exit code;
- `dsl_mngr.core`: workspace, database, registry, run, candidati, review, merge,
  temporalità, DSL, diff, preflight OOXML e grafi;
- `dsl_mngr.workers`: normalizzazione Docling e parser eseguiti in processi
  controllati;
- `dsl_mngr.resources`: risorse offline, incluse le XSD GEXF 1.3.

## Capacità e invarianti da preservare

- Le sorgenti registrate sono identificate tramite SHA-256; un cambio di byte
  richiede una nuova revisione.
- XLSX e XLSM sono letti direttamente; le macro non vengono eseguite, le formule
  non vengono ricalcolate e i link esterni non vengono dereferenziati.
- Il preflight OOXML opera in memoria, senza estrazione sul filesystem, con
  allowlist dei formati e limiti di risorse.
- DOCX, PPTX, XLSX e XLSM possono fornire proprietà e timestamp come evidenze
  temporali grezze; un metadato non costituisce automaticamente verità di
  dominio.
- Candidati `pending`, `rejected` o `superseded` non diventano fatti o relazioni
  effettivi. La review comune è il confine di governance.
- L'handoff AI è locale: DSL Manager crea package deterministici e importa
  JSONL dall'inbox, ma non invoca autonomamente modelli o servizi di rete. Anche
  i candidati AI restano pending fino alla review applicabile.
- Correzioni di candidati creano nuove foglie e possono richiedere
  riconciliazione; la storia append-only non viene riscritta.
- DSL schema 1 preserva il profilo legacy/statico. DSL schema 2 rappresenta la
  temporalità e alimenta l'export GEXF dinamico.
- I percorsi di test OOXML, temporalità e GEXF devono restare offline.
- Report e artefatti usano percorsi relativi alla workspace e output
  deterministici ove previsto; run ID e timestamp di audit non fanno parte
  degli hash semantici.

## Documentazione da leggere

Per orientarsi rapidamente:

1. `AGENTS.md` — regole operative e vincoli dell'ambiente;
2. `pyproject.toml` — release, Python e dipendenze;
3. `documenti/manuali/manuale_utente_dsl_manager.md` — uso della CLI;
4. `documenti/documenti tecnici/analisi_tecnica_dsl_manager.md` — architettura
   implementata;
5. `documenti/documenti tecnici/contratti_manifest_dsl_manager.md` — contratti
   dati e artefatti;
6. `projects/corpus aurora/.../materiale_di_supporto/guida_dsl_manager_powershell_v_02.md`
   e `guida_dsl_manager_cmd_v_02.md` — scenario Aurora completo e riproducibile;
7. `documenti/bugfixes/` — diagnosi e correzioni storiche.

## Scenari e verifica

Il corpus Aurora sotto
`.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/` è lo scenario E2E
principale. Solo le 18 fonti sotto `corpus/active` sono input operativi; le
fixture sotto `materiale_di_supporto/fixture_controllate` sono casi di test
negativi o controllati. Fra questi, `ai_response_aurora_controllata.jsonl`
permette di esercitare offline package DDL, inbox, import, review e merge senza
attribuire all'output simulato alcuna autorità speciale.

Le guide operative Aurora sono le versioni 02. Le versioni 01 sono archiviate
con nomi esplicitamente versionati e rimandano alle guide correnti; tutti i
riferimenti operativi del repository puntano alle versioni 02.

La suite canonica è `python -m pytest` con l'interprete corretto. L'ultima
esecuzione completa, dopo l'aggiunta dello scenario AI Aurora e l'aggiornamento
delle guide v02, ha raccolto e superato tutti i 181 test in 416.30 secondi. Il
worker Docling, che in una precedente esecuzione aveva mostrato un lock Windows
transitorio durante il cleanup, è passato sia al rerun isolato sia nelle
esecuzioni complete successive. I dettagli storici sono nei report dei bugfix.

## Registro bug corretti

| ID | Rilevato | Corretto | Release | Severità | Sintomo | Correzione | Verifica | Report |
|---|---|---|---|---|---|---|---|---|
| `BUGFIX_01` | 2026-09-09 | 2026-09-09 | `1.1.0` working tree | Alta | `batch consolidate` falliva in `derive` su DOCX con “Excel preflight requires an .xlsx or .xlsm name.” | Preflight metadata OOXML per DOCX/PPTX con delega invariata al validatore Excel per XLSX/XLSM | Test di regressione e Slice 28 passati; suite finale `179 passed` dopo `BUGFIX_02` | [bugfix_01_ooxml_temporal_docx_preflight.md](bugfixes/bugfix_01_ooxml_temporal_docx_preflight.md) |
| `BUGFIX_02` | 2026-09-09 | 2026-09-09 | `1.1.0` working tree | Bassa | Tre test documentali fallivano perché cercavano il nome precedente dell'outline sintetico | Test e link canonici aggiornati a `outline_dsl_manager_flow_from_input_to_output_riassunto.md` | `7 passed` mirati; suite completa `179 passed` | [bugfix_02_stale_outline_references.md](bugfixes/bugfix_02_stale_outline_references.md) |

## Osservazioni aperte

- Aggiungere in futuro una fixture PPTX binaria per coprire esplicitamente il
  ramo introdotto insieme al supporto DOCX.
- Valutare l'aggiunta di `source_revision_id` e `file_path` ai report di errore
  della derivazione temporale.
- È stato osservato su Windows un lock transitorio di `.worker_stdout.tmp` nel
  cleanup del worker Docling. Non fa parte di `BUGFIX_01` e non è stato corretto.

## Regole di manutenzione del riepilogo

Aggiornare questo file quando cambia almeno uno dei seguenti elementi:

- versione o runtime Python;
- dipendenze applicative principali;
- layout, entry point o comandi canonici;
- invarianti di sicurezza/governance;
- capacità o limiti noti significativi;
- bug corretto, includendo data, release, test e link al report;
- migrazione o contratto persistente rilevante.

Ogni nuovo bugfix dovrebbe usare
`../template/template_bugfix_report.md`, ricevere il successivo numero a due
cifre e aggiungere una riga al registro sopra.
