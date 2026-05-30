# DDGameAss

Applicazione desktop Python per registrare, modificare e riprodurre macro su Windows, con supporto a task schedulati, elementi di gioco, temi grafici e strumenti di diagnostica.

## Cosa fa

- Registra macro di mouse e tastiera
- Riproduce macro su una finestra target
- Gestisce task schedulati e sequenze di macro
- Salva configurazione, temi e database localmente
- Include utility di diagnostica e riparazione
- Ha una suite di test automatici per i componenti principali

## Avvio rapido

### Avvio normale

```powershell
F:\phyton3.131\python.exe gui_macro_manager.py
```

In alternativa:

```powershell
python gui_macro_manager.py
```

### Avvio come amministratore

Con doppio clic su:

- [Avvia_Macro_Manager_come_amministratore.bat](/F:/_CODEX/DDassistant/Avvia_Macro_Manager_come_amministratore.bat)

Questo launcher chiede i permessi amministrativi e avvia l'interfaccia principale.
Se disponibile, usa in priorità il runtime locale su `F:\phyton3.131` per evitare problemi col launcher `py`.

## Dipendenze e packaging

Le dipendenze Python del progetto sono state centralizzate in:

- [requirements.txt](/F:/_CODEX/DDassistant/requirements.txt)
- [pyproject.toml](/F:/_CODEX/DDassistant/pyproject.toml)

La base per i futuri setup applicativi è in:

- [setup/README.md](/F:/_CODEX/DDassistant/setup/README.md)
- [setup/common/app-packaging.json](/F:/_CODEX/DDassistant/setup/common/app-packaging.json)
- [setup/windows/README.md](/F:/_CODEX/DDassistant/setup/windows/README.md)

Questo permette di iniziare dal setup Windows senza spargere metadati o asset che in futuro potranno servire anche a Linux o Android.

## Struttura del progetto

- [gui_macro_manager.py](/F:/_CODEX/DDassistant/gui_macro_manager.py): interfaccia principale e coordinamento generale
- [macro_controller.py](/F:/_CODEX/DDassistant/macro_controller.py): logica base di registrazione e playback
- [macro_editor.py](/F:/_CODEX/DDassistant/macro_editor.py): editor delle macro
- [task_controller.py](/F:/_CODEX/DDassistant/task_controller.py): esecuzione e pianificazione task
- [repositories](/F:/_CODEX/DDassistant/repositories): accesso ai dati e persistenza SQLite
- [services](/F:/_CODEX/DDassistant/services): stato operativo, focus, recording e playback
- [ui](/F:/_CODEX/DDassistant/ui): pannelli e helper dell'interfaccia
- [core](/F:/_CODEX/DDassistant/core): stato condiviso, percorsi e configurazione
- [doomsday](/F:/_CODEX/DDassistant/doomsday): moduli OCR, catalogo e visione esterna per Doomsday
- [config](/F:/_CODEX/DDassistant/config): configurazione applicativa e temi
- [data](/F:/_CODEX/DDassistant/data): database SQLite del progetto
- [docs](/F:/_CODEX/DDassistant/docs): note tecniche e documentazione interna
- [tests](/F:/_CODEX/DDassistant/tests): test automatici

## Configurazione e dati

Il repository privato include anche i file locali del progetto:

- [config/config.json](/F:/_CODEX/DDassistant/config/config.json)
- [config/macro_config.json](/F:/_CODEX/DDassistant/config/macro_config.json)
- [data/macro_recorder.db](/F:/_CODEX/DDassistant/data/macro_recorder.db)

Per Doomsday sono stati importati anche dataset modulari in:

- [data/doomsday/catalog/market_profiles](/F:/_CODEX/DDassistant/data/doomsday/catalog/market_profiles)
- [data/doomsday/catalog/profile_pack](/F:/_CODEX/DDassistant/data/doomsday/catalog/profile_pack)
- [data/doomsday/roster](/F:/_CODEX/DDassistant/data/doomsday/roster)

Questo permette di mantenere insieme codice, impostazioni e database reale.

## Integrazione workspace

Il progetto e' stato anche registrato nel workspace condiviso AI:

- [AGENTS.md](/F:/_CODEX/DDassistant/AGENTS.md)
- [project-manifest.json](/F:/_CODEX/DDassistant/project-manifest.json)
- [project card nel knowledge hub](/F:/_CODEX/AI-WORKSPACE/codex-knowledge-hub/projects/ddgameass.yaml)

Le interfacce Doomsday condivise verso altri progetti sono documentate in:

- [interfaces/doomsday-roster-bootstrap.md](/F:/_CODEX/DDassistant/interfaces/doomsday-roster-bootstrap.md)
- [interfaces/doomsday-vision-primitives.md](/F:/_CODEX/DDassistant/interfaces/doomsday-vision-primitives.md)
- [interfaces/doomsday-creators-pipeline.md](/F:/_CODEX/DDassistant/interfaces/doomsday-creators-pipeline.md)

## Test automatici

Per eseguire la suite:

```powershell
python -m unittest discover -s tests -v
```

Per inizializzare o riallineare il database Doomsday importando i dataset presenti in `data/doomsday/`:

```powershell
python bootstrap_doomsday_data.py
```

La copertura attuale include:

- servizi operativi
- stato applicativo
- repository SQLite
- configurazione centrale

## Utility incluse

- [debug_macro_playback.py](/F:/_CODEX/DDassistant/debug_macro_playback.py): diagnostica dei problemi di riproduzione
- [repair_macros.py](/F:/_CODEX/DDassistant/repair_macros.py): riparazione e verifica macro
- [test_focus_logic.py](/F:/_CODEX/DDassistant/test_focus_logic.py): script di verifica manuale della logica focus

## Elementi grafici del gioco

La tab `Elementi` e' stata impostata per acquisire elementi grafici senza distorsioni:

- l'immagine salvata viene preservata nelle dimensioni originali
- lo storage viene normalizzato in `PNG` lossless
- l'anteprima e' ridotta solo a scopo visivo, senza alterare il file memorizzato
- oltre a nome e descrizione, e' possibile annotare anche il ruolo semantico dell'elemento

Procedura consigliata:

- [docs/GAME_ELEMENT_INGESTION_WORKFLOW.md](/F:/_CODEX/DDassistant/docs/GAME_ELEMENT_INGESTION_WORKFLOW.md)

## Documentazione interna

- [docs/IMPLEMENTATION_SUMMARY.md](/F:/_CODEX/DDassistant/docs/IMPLEMENTATION_SUMMARY.md)
- [docs/README_FOCUS_FIX.md](/F:/_CODEX/DDassistant/docs/README_FOCUS_FIX.md)
- [docs/SOLUZIONE_MACRO_PLAYBACK.md](/F:/_CODEX/DDassistant/docs/SOLUZIONE_MACRO_PLAYBACK.md)
- [docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md](/F:/_CODEX/DDassistant/docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md)
- [CHANGELOG.md](/F:/_CODEX/DDassistant/CHANGELOG.md)
- [ROADMAP.md](/F:/_CODEX/DDassistant/ROADMAP.md)

## Stato attuale

Il progetto è stato ripulito e modularizzato nelle aree principali:

- persistenza separata in repository
- runtime separato in servizi
- stato condiviso centralizzato
- GUI alleggerita in moduli dedicati
- test automatici introdotti sui componenti più importanti

È una buona base per continuare con nuove funzioni o ulteriori rifiniture.

## Creator publication branch

Il progetto ora include anche un filone dedicato alla pubblicazione creator per `Doomsday: Last Survivors`, pensato per usare il contesto ufficiale `Creator Turf` come sbocco reale per contenuti multimediali prodotti col supporto del progetto.

Riferimenti principali:

- [docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md](/F:/_CODEX/DDassistant/docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md)
- [interfaces/doomsday-creators-pipeline.md](/F:/_CODEX/DDassistant/interfaces/doomsday-creators-pipeline.md)
- [data/doomsday/creator_turf/creator-program-plan.json](/F:/_CODEX/DDassistant/data/doomsday/creator_turf/creator-program-plan.json)
