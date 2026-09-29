# Roadmap

## Prossime priorita'

- Recuperare o ricatturare gli elementi grafici 229-342 referenziati dalla macro storica locale 72; le macro restano nel database per-workstation e non si sincronizzano via Git.
- Rendere strutturali/unknown i nodi UI senza condizioni anche nell'evaluator legacy e aggiungere riconoscitori discriminanti ai nodi usati come precondizioni.
- Collegare la versione del runtime attivo alla pianificazione e bloccare i ruleset incompatibili.
- Esporre nella GUI il workflow roster live gia' transazionale: cattura, revisione, decisioni, conferma, commit e refresh del roster campo.
- Validare sui nuovi frame le transizioni Eroe e calibrare ROI per lista, profilo, statistiche, abilita' e talenti.
- Rendere transazionale il salvataggio di Scheduled Tasks e sequenze macro.
- Aggiungere retry differiti e stato dead-letter all'outbox delle evidenze.
- Collegare le prime azioni semantiche solo dopo evidenza before/after confermata e verificarne gli esiti con OCR/UI graph.
- Completata l'attribuzione semantica macro-campagna: le prossime campagne devono raccogliere receipt e nuova percezione per passare da `candidate` a `validated`.
- Aggiungere una modalita' di playback "turbo" selezionabile da UI, con filtri opzionali sui move molto ravvicinati.
- Introdurre test automatici piu' mirati sul flusso scheduler end-to-end.
- Migliorare l'anteprima visuale dell'editor con confronto prima/dopo ottimizzazione.

## Migliorie successive

- Introdurre un Executor concreto a passo singolo con conferma, timeout, cancellazione, receipt e nuova percezione obbligatoria.
- Usare le performance degli episodi solo per ordinare suggerimenti, senza apprendere autorità o abbassare il rischio.
- Ampliare ruleset e claim tramite regole in-game e battle report versionati; usare Discord solo per gap mirati e in modalità temporanea read-only.
- Esportazione/importazione macro in JSON leggibile.
- Profilazione piu' dettagliata dei tempi di playback.
- Cronologia operazioni recenti nell'interfaccia principale.
- Diagnostica guidata per focus, finestra target e permessi amministrativi.
- Preview read-only di GoalInterpretation e GamePlan nella GUI: completata nella tab `Piano Gioco`.
