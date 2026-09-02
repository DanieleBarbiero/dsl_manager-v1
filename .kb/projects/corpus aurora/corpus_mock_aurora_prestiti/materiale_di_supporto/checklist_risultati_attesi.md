# Checklist dei risultati attesi

Al termine di un ciclo completo, verificare che:

- lo scan abbia registrato tutte le fonti sotto `corpus/active`;
- il batch abbia normalizzato e suddiviso in chunk i documenti supportati;
- il file XLSX sia stato segnalato come formato non supportato;
- il DDL abbia prodotto frammenti per quattro tabelle, colonne e vincoli;
- le tre form abbiano prodotto frammenti per form, campi e pulsanti;
- le procedure e il trigger abbiano prodotto frammenti SQL;
- i due log abbiano prodotto eventi osservati;
- il package AI contenga chunk e frammenti con ID verificabili;
- i candidati privi di evidenza letterale siano rifiutati;
- il merge trasformi soltanto `candidate_fact` e `candidate_relation`;
- lo snapshot DSL contenga entità e relazioni con tracciabilità;
- l'export GEXF sia prodotto da uno snapshot persistito;
- la UI locale mostri run, log, rifiuti, conflitti, snapshot e diff senza modificare il registry.

Possibili conflitti semantici da far emergere:

- limite di importo storico di 50000 euro contro limite corrente di 60000 euro;
- stati storici BOZZA/VALIDATA/DELIBERATA/ANNULLATA contro gli stati correnti;
- annotazione manuale della data di delibera contro aggiornamento automatico del trigger.
