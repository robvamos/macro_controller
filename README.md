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
py -3 gui_macro_manager.py
```

In alternativa:

```powershell
python gui_macro_manager.py
```

### Avvio come amministratore

Con doppio clic su:

- [Avvia_Macro_Manager_come_amministratore.bat](/F:/_CODEX/AI-WORKSPACE/DDGameAss/Avvia_Macro_Manager_come_amministratore.bat)

Questo launcher chiede i permessi amministrativi e avvia l'interfaccia principale.

## Struttura del progetto

- [gui_macro_manager.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/gui_macro_manager.py): interfaccia principale e coordinamento generale
- [macro_controller.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/macro_controller.py): logica base di registrazione e playback
- [macro_editor.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/macro_editor.py): editor delle macro
- [task_controller.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/task_controller.py): esecuzione e pianificazione task
- [repositories](/F:/_CODEX/AI-WORKSPACE/DDGameAss/repositories): accesso ai dati e persistenza SQLite
- [services](/F:/_CODEX/AI-WORKSPACE/DDGameAss/services): stato operativo, focus, recording e playback
- [ui](/F:/_CODEX/AI-WORKSPACE/DDGameAss/ui): pannelli e helper dell'interfaccia
- [core](/F:/_CODEX/AI-WORKSPACE/DDGameAss/core): stato condiviso, percorsi e configurazione
- [doomsday](/F:/_CODEX/AI-WORKSPACE/DDGameAss/doomsday): moduli OCR, catalogo e visione esterna per Doomsday
- [config](/F:/_CODEX/AI-WORKSPACE/DDGameAss/config): configurazione applicativa e temi
- [data](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data): database SQLite del progetto
- [docs](/F:/_CODEX/AI-WORKSPACE/DDGameAss/docs): note tecniche e documentazione interna
- [tests](/F:/_CODEX/AI-WORKSPACE/DDGameAss/tests): test automatici

## Configurazione e dati

Il repository privato include anche i file locali del progetto:

- [config/config.json](/F:/_CODEX/AI-WORKSPACE/DDGameAss/config/config.json)
- [config/macro_config.json](/F:/_CODEX/AI-WORKSPACE/DDGameAss/config/macro_config.json)
- [data/macro_recorder.db](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data/macro_recorder.db)

Per Doomsday sono stati importati anche dataset modulari in:

- [data/doomsday/catalog/market_profiles](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data/doomsday/catalog/market_profiles)
- [data/doomsday/catalog/profile_pack](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data/doomsday/catalog/profile_pack)
- [data/doomsday/roster](/F:/_CODEX/AI-WORKSPACE/DDGameAss/data/doomsday/roster)

Questo permette di mantenere insieme codice, impostazioni e database reale.

## Integrazione workspace

Il progetto e' stato anche registrato nel workspace condiviso AI:

- [AGENTS.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/AGENTS.md)
- [project-manifest.json](/F:/_CODEX/AI-WORKSPACE/DDGameAss/project-manifest.json)
- [project card nel knowledge hub](/F:/_CODEX/AI-WORKSPACE/codex-knowledge-hub/projects/ddgameass.yaml)

Le interfacce Doomsday condivise verso altri progetti sono documentate in:

- [interfaces/doomsday-roster-bootstrap.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/interfaces/doomsday-roster-bootstrap.md)
- [interfaces/doomsday-vision-primitives.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/interfaces/doomsday-vision-primitives.md)

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

- [debug_macro_playback.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/debug_macro_playback.py): diagnostica dei problemi di riproduzione
- [repair_macros.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/repair_macros.py): riparazione e verifica macro
- [test_focus_logic.py](/F:/_CODEX/AI-WORKSPACE/DDGameAss/test_focus_logic.py): script di verifica manuale della logica focus

## Documentazione interna

- [docs/IMPLEMENTATION_SUMMARY.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/docs/IMPLEMENTATION_SUMMARY.md)
- [docs/README_FOCUS_FIX.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/docs/README_FOCUS_FIX.md)
- [docs/SOLUZIONE_MACRO_PLAYBACK.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/docs/SOLUZIONE_MACRO_PLAYBACK.md)
- [CHANGELOG.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/CHANGELOG.md)
- [ROADMAP.md](/F:/_CODEX/AI-WORKSPACE/DDGameAss/ROADMAP.md)

## Stato attuale

Il progetto è stato ripulito e modularizzato nelle aree principali:

- persistenza separata in repository
- runtime separato in servizi
- stato condiviso centralizzato
- GUI alleggerita in moduli dedicati
- test automatici introdotti sui componenti più importanti

È una buona base per continuare con nuove funzioni o ulteriori rifiniture.
