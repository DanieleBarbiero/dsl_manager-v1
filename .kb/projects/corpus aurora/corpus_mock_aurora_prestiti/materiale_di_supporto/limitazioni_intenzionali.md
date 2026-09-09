# Limitazioni intenzionali del corpus

## Oracle Forms

I file XML sono facsimili leggibili, non file binari `.fmb`. Il parser riconosce
il sottoinsieme con radice `<form>`, campi e pulsanti usato dalle fixture.

## SQL e PL/SQL

Il DDL usa tipi Oracle ma mantiene i vincoli dentro `CREATE TABLE`. Il parser
del codice database non e' un parser PL/SQL generale: procedure e trigger usano
il sottoinsieme coperto da `CREATE PROCEDURE`, `CREATE TRIGGER`, `UPDATE` e
`CALL`.

## Documenti ed Excel

Markdown, testo, HTML, DOCX, XLSX e XLSM sono normalizzabili. L'analisi Excel e'
strutturale e offline: l'external link e' inventariato ma non dereferenziato; il
VBA e' rilevato e sottoposto a hash ma mai eseguito.

Il malformed e il partial sono fixture controllate fuori da `corpus/active`:
non rappresentano fonti operative. Il primo verifica il rifiuto di sicurezza;
il secondo richiede l'iniezione test di un esito Docling `partial_success` e non
simula un file corrotto.

## Temporalita'

Le date nei nomi file, nei metadata OOXML e nei contenuti sono evidenze, non
verita' effettive. Segnali concordanti possono alzare la confidenza ma restano
soggetti a review; segnali discordanti devono restare pending/conflicted.

## Dati e rete

Non sono presenti dati personali reali. Gli identificativi nei log sono
fittizi. Tutti gli scenari del corpus sono eseguibili senza rete e senza una AI
reale.
