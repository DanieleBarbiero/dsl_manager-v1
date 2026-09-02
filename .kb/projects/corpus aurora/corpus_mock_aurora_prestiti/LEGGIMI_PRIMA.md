# Corpus dimostrativo «Aurora Prestiti»

Questo archivio rappresenta una piccola applicazione legacy immaginaria per la gestione di prestiti personali.

Il sistema originale usa:

- Oracle Database;
- semplici schermate assimilabili a Oracle Forms, esportate in XML;
- procedure e trigger PL/SQL;
- batch notturni con log testuali;
- documentazione accumulata in anni diversi e con attendibilità diversa.

Tutti i nomi di persone, codici, importi ed eventi sono inventati. Il corpus non contiene dati reali.

## Obiettivo della modernizzazione

Ricostruire un DSL tracciabile che descriva almeno:

- le entità `Cliente`, `PraticaPrestito`, `Rata` e `Pagamento`;
- gli stati e le regole principali delle pratiche;
- le tabelle Oracle e i relativi collegamenti;
- le form che modificano le tabelle;
- le procedure, i trigger e i comportamenti osservati nei log;
- i conflitti fra documentazione storica e corrente.

## Struttura

La directory `corpus/active` contiene le fonti da far acquisire a `dsl-manager`.

La directory `materiale_di_supporto` non deve essere copiata nel corpus attivo. Contiene:

- l'inventario ragionato delle fonti;
- le limitazioni intenzionali dell'esempio;
- una checklist dei risultati attesi.

Per il ciclo completo seguire la guida `guida_dsl-manager.md` distribuita insieme allo ZIP nella root del progetto.

