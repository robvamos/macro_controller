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

- [Avvia_Macro_Manager_come_amministratore.bat](/F:/_CODEX/DDassistant/Avvia_Macro_Manager_come_amministratore.bat)

Questo launcher chiede i permessi amministrativi e avvia l'interfaccia principale.

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
- [scripts/generate_reference_calibration_audio.py](/F:/_CODEX/DDassistant/scripts/generate_reference_calibration_audio.py): genera audio campione per test live e aggiorna l'indice dei file creati

## Audio campione calibrazione

Nella cartella [data/calibration](/F:/_CODEX/DDassistant/data/calibration) e' disponibile un campione generico gia' pronto:

- [generic_reference_sample.mp3](/F:/_CODEX/DDassistant/data/calibration/generic_reference_sample.mp3)
- [generic_reference_sample.json](/F:/_CODEX/DDassistant/data/calibration/generic_reference_sample.json)

La libreria base include anche almeno 3 pezzi di test con variazioni note per verificare allineamento ritmico e fase del brano:

- [phase_alignment_drill.mp3](/F:/_CODEX/DDassistant/data/calibration/phase_alignment_drill.mp3): materiale stabile a `96 BPM` con blocchi noti per riconoscere il beat `1`
- [grid16_phrase_map.mp3](/F:/_CODEX/DDassistant/data/calibration/grid16_phrase_map.mp3): mappa fraseologica a `16 grid` con due zone di tempo note
- [tempo_transition_stress.mp3](/F:/_CODEX/DDassistant/data/calibration/tempo_transition_stress.mp3): cambi di tempo noti per testare la rapidita' di riallineamento

L'indice dei campioni generati viene mantenuto in:

- [data/calibration/index.json](/F:/_CODEX/DDassistant/data/calibration/index.json)

Dall'interfaccia principale e' ora disponibile anche la tab `Audio Campioni`, che permette di:

- caricare un file audio esterno
- scegliere inizio e fine della sezione da usare come campione
- salvare il ritaglio come nuovo sample MP3/WAV
- ritrovare il campione nella lista aggiornata automaticamente
- scomporre un campione con segmenti noti in piu' blocchi derivati
- combinare piu' campioni in una song di test ordinata per misurare tempo, fase della battuta e riconoscimento del beat `1`

E' disponibile anche una vista dedicata `Learning Lab`, piu' focalizzata e meno dispersiva, con:

- analisi di preprocessing e BPM detection a finestre
- costruzione della griglia di learning dal campione selezionato o dai segmenti BPM rilevati
- metriche compatte su stabilita' tempo, pattern riconoscibile, readiness di correzione e accuratezza del beat `1`
- feedback rapido dell'utilizzatore
- reset di sync quando una battuta parte male e va riallineata
- tooltip sui controlli principali
- sezione manuale avanzata compressa di default per lasciare il focus su preprocessing e tempo

La logica di convergenza musicale e' stata separata in uno strato dedicato:

- all'inizio il comportamento resta non invasivo
- con maggiore stabilita' del pattern e del BPM aumenta la confidenza
- solo quando la convergenza e' davvero solida il sistema suggerisce piu' intensita', componenti ed effetti

La tab `Learning Lab` propone anche una valutazione della configurazione corrente:

- dopo analisi e prove puoi salvare un giudizio rapido sulla configurazione
- lo storico viene riusato per capire quali assetti funzionano meglio
- questo permette al sistema di imparare non solo dal segnale, ma anche dal feedback dell'utilizzatore

Per rigenerare il campione base o crearne altri con un nome dedicato:

```powershell
python scripts/generate_reference_calibration_audio.py --ffmpeg F:\_CODEX\Audio2VideoPal\.tools\ffmpeg\bin\ffmpeg.exe
python scripts/generate_reference_calibration_audio.py --ffmpeg F:\_CODEX\Audio2VideoPal\.tools\ffmpeg\bin\ffmpeg.exe --preset reference_live_calibration --name test_session_01
python scripts/generate_reference_calibration_audio.py --list
```

## Documentazione interna

- [docs/IMPLEMENTATION_SUMMARY.md](/F:/_CODEX/DDassistant/docs/IMPLEMENTATION_SUMMARY.md)
- [docs/README_FOCUS_FIX.md](/F:/_CODEX/DDassistant/docs/README_FOCUS_FIX.md)
- [docs/SOLUZIONE_MACRO_PLAYBACK.md](/F:/_CODEX/DDassistant/docs/SOLUZIONE_MACRO_PLAYBACK.md)
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
