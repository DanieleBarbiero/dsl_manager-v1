# Requisiti di modernizzazione Orione Assistenza

effective_from: 2026-03-01

Il servizio modernizzato conserva asset, interventi, tecnici, assegnazioni e
checklist. La decorrenza operativa concordata e' il 1 marzo 2026. La data e'
una data di dominio, non la data di creazione del file.

## Chiusura controllata

La chiusura dell'intervento richiede il completamento di tutte le voci
obbligatorie della checklist. Il comando di chiusura deve spiegare quali voci
mancano senza alterare quelle gia' completate.

## SLA e interpretazione

Il gruppo di lavoro ha scritto inizialmente: "Tutti gli interventi devono
essere chiusi entro quattro ore". L'affermazione e' troppo forte: la matrice
approvata limita l'obiettivo di quattro ore agli interventi P1 e distingue
presa in carico e risoluzione. La review deve correggere l'asserto, non
confermarlo letteralmente.

Un'interfaccia futura potrebbe notificare un sistema ticket esterno. Il nome,
il contratto e la responsabilita' di quel sistema non sono documentati: una
relazione che lo menzioni resta un orphan intenzionale e non va trasformata in
integrazione certa.

## Decisioni non ancora prese

Non e' stabilito se il tecnico reperibile possa riassegnare un P1 gia' preso in
carico. Non e' stabilito se una checklist incompleta sospenda o continui il
conteggio SLA. Queste frasi devono generare domande o interpretazioni pending.
