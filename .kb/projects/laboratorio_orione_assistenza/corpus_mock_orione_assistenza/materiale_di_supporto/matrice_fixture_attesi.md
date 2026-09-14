# Matrice fixture e risultati attesi

| Fixture | Parser o controllo | Atteso principale | Azione di governo |
|---|---|---|---|
| `dump_oracle_ddl.sql` | DDL | 6 tabelle, 28 colonne, 4 FK, 2 indici; view avvertita | auto-review solo regole allowlisted |
| `prc_assegna_tecnico.sql` | database code | 1 procedure | struttura tecnica, non regola di dominio implicita |
| `trg_chiudi_intervento.sql` | database code | 1 trigger | separare timestamp tecnico e checklist interpretata |
| `frm_intervento.xml` | XML Forms | 1 form, 6 campi, 4 pulsanti, 4 tabelle | auto-review struttura/operazioni allowlisted |
| `interventi_2026.log` | log | 5 eventi validi, 1 riga invalida, INFO/WARN/ERROR | `observed`; non generalizzare un evento |
| `requisiti_modernizzazione_2026.md` | Docling + temporalita' | 1 chunk; decorrenza esplicita; asserto SLA troppo forte | confermare data, correggere SLA, lasciare domande pending |
| `decorrenza_servizio_2026.txt` | Docling + temporalita' | 1 chunk; stesso fatto checklist e stessa decorrenza | secondo supporto indipendente |
| `manuale_operativo_2026.docx` | Docling + OOXML | testo 2026; core properties 2024 | confermare contenuto, rifiutare metadata come validita' |
| `matrice_stati_sla_2026.xlsx` | Docling + workbook | 3 fogli visibili/hidden/veryHidden, piu' regioni, tabella e named range | formula cache distinta da formula senza cache |
| `calcolo_sla_macro_2026.xlsm` | Docling + preflight | stesso contenuto strutturale; `vbaProject.bin` presente e hashato | non eseguire macro |
| `architettura_integrazioni_2026.pptx` | Docling + OOXML | bozza 2026; core properties 2023 | integrazione esterna pending |
| `accordo_sla_2025.pdf` | Docling + PDF metadata | testo SLA storico; date 2025 | non sovrascrivere il corrente |
| `procedura_assegnazione_2023.html` | Docling + HTML temporal | intervallo chiuso 2023-01-01/2025-02-28 | rifiutare auto-assegnazione per il corrente |
| `inventario_arredi_2022.txt` | Docling | chunk leggibile ma irrilevante | non promuovere |
| `istruzioni_parcheggio_2026.html` | Docling | chunk recente ma irrilevante | non promuovere |
| `workbook_malformed_controllato.xlsx` | preflight controllato | rifiuto malformed | fuori dal corpus attivo |
| `workbook_partial_controllato.xlsx` | worker controllato | `partial_success` soltanto con iniezione | fuori dal corpus attivo; non provato dalla CLI reale |
| `ai_response_orione_assistenza_controllata.jsonl` | AI import | 13 record validi su workspace canonico pulito | replay etichettato e verificato prima della copia |

## Copertura workbook

`matrice_stati_sla_2026.xlsx` contiene stringhe, numeri, booleani, date,
`#DIV/0!`, blank, merged range `A6:B6`, tabella `tabella_sla`, named range
globale `target_p1_ore`, named range locale `area_stati`, regioni separate, una
formula con cache (`B7`) e una senza (`B8`). Il link esterno punta al dominio
riservato `orione.invalid`, compare nel manifest e non viene aperto.

## Contratto semantico AI

Il replay esercita fact, relation, mapping, conflict e question; contiene
explicit, observed, inferred e ambiguous. Gli esiti canonici sono:

- conferma dei due candidati checklist e merge in un fatto con due supporti;
- correzione dell'asserto SLA generale nel target P1, parent superseded e
  replacement confirmed;
- rifiuto dell'auto-assegnazione storica;
- conferma controllata di mapping/question/conflict per osservare quali record
  il merge materializza o salta;
- relazione `intervento assegnato_a tecnico` da rendere temporale;
- relazione verso il sistema ticket non documentato per l'orphan intenzionale;
- fatto di log `observed` separato dalla regola generale;
- ipotesi di contratto esterno lasciata pending.

## Contratto temporale finale

Confermare `2026-03-01` sulle revisioni del verbale e dei requisiti; rifiutare
`sources.first_seen_at`; lasciare almeno un conflitto filename/metadata pending.
Propagare `explicit_copy` ai due fatti scelti e alla relazione, quindi
confermare i nuovi candidati. Esercitare anche `aggregation` sulle due revisioni
concordanti. DSL v2 deve avere intervalli non vuoti. Il GEXF dinamico deve avere
almeno uno spell di nodo e uno di arco e passare XSD e semantica.
