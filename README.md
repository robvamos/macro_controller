# Macro Controller

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

- [Avvia_Macro_Manager_come_amministratore.bat](/F:/Zombi/macro_controller/Avvia_Macro_Manager_come_amministratore.bat)

Questo launcher chiede i permessi amministrativi e avvia l'interfaccia principale.

## Struttura del progetto

- [gui_macro_manager.py](/F:/Zombi/macro_controller/gui_macro_manager.py): interfaccia principale e coordinamento generale
- [macro_controller.py](/F:/Zombi/macro_controller/macro_controller.py): logica base di registrazione e playback
- [macro_editor.py](/F:/Zombi/macro_controller/macro_editor.py): editor delle macro
- [task_controller.py](/F:/Zombi/macro_controller/task_controller.py): esecuzione e pianificazione task
- [repositories](/F:/Zombi/macro_controller/repositories): accesso ai dati e persistenza SQLite
- [services](/F:/Zombi/macro_controller/services): stato operativo, focus, recording e playback
- [ui](/F:/Zombi/macro_controller/ui): pannelli e helper dell'interfaccia
- [core](/F:/Zombi/macro_controller/core): stato condiviso, percorsi e configurazione
- [config](/F:/Zombi/macro_controller/config): configurazione applicativa e temi
- [data](/F:/Zombi/macro_controller/data): database SQLite del progetto
- [docs](/F:/Zombi/macro_controller/docs): note tecniche e documentazione interna
- [tests](/F:/Zombi/macro_controller/tests): test automatici

## Configurazione e dati

Il repository privato include anche i file locali del progetto:

- [config/config.json](/F:/Zombi/macro_controller/config/config.json)
- [config/macro_config.json](/F:/Zombi/macro_controller/config/macro_config.json)
- [data/macro_recorder.db](/F:/Zombi/macro_controller/data/macro_recorder.db)

Questo permette di mantenere insieme codice, impostazioni e database reale.

## Test automatici

Per eseguire la suite:

```powershell
python -m unittest discover -s tests -v
```

La copertura attuale include:

- servizi operativi
- stato applicativo
- repository SQLite
- configurazione centrale

## Utility incluse

- [debug_macro_playback.py](/F:/Zombi/macro_controller/debug_macro_playback.py): diagnostica dei problemi di riproduzione
- [repair_macros.py](/F:/Zombi/macro_controller/repair_macros.py): riparazione e verifica macro
- [test_focus_logic.py](/F:/Zombi/macro_controller/test_focus_logic.py): script di verifica manuale della logica focus

## Documentazione interna

- [docs/IMPLEMENTATION_SUMMARY.md](/F:/Zombi/macro_controller/docs/IMPLEMENTATION_SUMMARY.md)
- [docs/README_FOCUS_FIX.md](/F:/Zombi/macro_controller/docs/README_FOCUS_FIX.md)
- [docs/SOLUZIONE_MACRO_PLAYBACK.md](/F:/Zombi/macro_controller/docs/SOLUZIONE_MACRO_PLAYBACK.md)
- [CHANGELOG.md](/F:/Zombi/macro_controller/CHANGELOG.md)
- [ROADMAP.md](/F:/Zombi/macro_controller/ROADMAP.md)

## Stato attuale

Il progetto è stato ripulito e modularizzato nelle aree principali:

- persistenza separata in repository
- runtime separato in servizi
- stato condiviso centralizzato
- GUI alleggerita in moduli dedicati
- test automatici introdotti sui componenti più importanti

È una buona base per continuare con nuove funzioni o ulteriori rifiniture.
