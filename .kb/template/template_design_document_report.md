# Report di generazione del documento di design

**Prompt di origine:** `<prompt_path>`  
**Documento prodotto:** `<design_document_path>`  
**Documento di riferimento:** `<baseline_design_path>`  
**Data:** `<YYYY-MM-DD>`  
**Esito:** `<completato | completato_con_note | bloccato>`

## 1. Sintesi del risultato

- `<risultato principale>`
- `<perimetro coperto>`
- `<eventuali limitazioni rilevanti>`

## 2. Perimetro degli input

| Input o gruppo | Ruolo | Copertura | Note |
|---|---|---|---|
| `<path_o_glob>` | `<baseline | stato_implementato | contratto | proposta | scenario | template>` | `<completa | selettiva | non_applicabile>` | `<criterio di selezione o nota>` |

Indicare il numero di file individuati per ogni glob o directory e segnalare
esplicitamente input mancanti, illeggibili o esclusi.

## 3. Gerarchia e uso delle fonti

Descrivere quali fonti sono state considerate autorevoli per:

- stato implementato;
- contratti e compatibilità;
- baseline architetturale;
- proposte future;
- esempi e scenari di test.

Quando due fonti divergono, indicare la regola applicata per scegliere o
riconciliare il dato.

## 4. Processo seguito

Riassumere le fasi di assimilazione e sintesi:

1. `<inventario e classificazione>`;
2. `<lettura progressiva e ricerche mirate>`;
3. `<analisi separate per capability>`;
4. `<riconciliazione delle dipendenze>`;
5. `<composizione e autoverifica>`.

Non riportare ragionamenti interni estesi; descrivere attività, criteri ed
evidenze verificabili.

## 5. Decisioni progettuali consolidate

| Decisione | Alternative considerate | Motivazione | Sezione del design |
|---|---|---|---|
| `<decisione>` | `<alternative>` | `<motivazione>` | `<sezione>` |

## 6. Conflitti, ambiguità e assunzioni

| Tema | Evidenze in conflitto o informazione mancante | Risoluzione o assunzione | Impatto |
|---|---|---|---|
| `<tema>` | `<fonti_o_lacuna>` | `<risoluzione>` | `<impatto>` |

Distinguere le decisioni imposte dal prompt dalle inferenze adottate durante
la generazione.

## 7. Tracciabilità dei requisiti

| Requisito | Fonti principali | Sezione del design | Slice |
|---|---|---|---|
| `<requisito>` | `<path_o_riferimento>` | `<sezione>` | `<slice_NN>` |

## 8. File non-input consultati

Elencare ogni file locale non dichiarato come input e spiegare perché è stato
necessario. Se non ne sono stati consultati, scrivere `Nessuno`.

## 9. Grounding web

| Fonte | Data di consultazione | Punto supportato | Motivazione |
|---|---|---|---|
| `<URL_o_Nessuno>` | `<YYYY-MM-DD>` | `<decisione_o_specifica>` | `<motivo>` |

Usare `Nessuno` quando non è stato necessario consultare fonti esterne.

## 10. Copertura del template di design

| Sezione prevista | Esito | Nota |
|---|---|---|
| `<sezione>` | `<compilata | non_applicabile | accorpata>` | `<motivazione>` |

## 11. Autoverifica

- [ ] Il documento richiesto è stato creato nel path previsto.
- [ ] La baseline e lo stato implementato sono distinti dalle proposte.
- [ ] Ogni capability richiesta è coperta da design, test e slice.
- [ ] Compatibilità, migrazioni, hash, diff e snapshot sono considerati.
- [ ] Le nuove slice rispettano la numerazione richiesta.
- [ ] Le decisioni non direttamente imposte sono dichiarate.
- [ ] I riferimenti tecnici usati sono tracciabili.
- [ ] Non sono stati creati o modificati file fuori dallo scope autorizzato.

## 12. Limiti e follow-up

- `<limite residuo>`
- `<decisione richiesta>`
- `<verifica futura>`
