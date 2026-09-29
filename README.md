# DDGameAss

Assistente desktop Windows per registrazione e playback controllato di macro, automazione pianificata, OCR e apprendimento supervisionato dell'interfaccia Doomsday.

## Avvio rapido

```powershell
python gui_macro_manager.py
```

Per richiedere l'elevazione amministrativa usa [Avvia_Macro_Manager_come_amministratore.bat](Avvia_Macro_Manager_come_amministratore.bat). Il launcher individua Python dal profilo workstation, da `.venv`, da `PATH` o dal launcher `py`; non contiene percorsi installati su una macchina specifica.

Per configurare un clone nuovo leggi [workstation/README.md](workstation/README.md). Le impostazioni reali e il runtime sono sotto `workstation/local/<profilo>/`, escluso da Git.

## Installazione e supporto

- [Dipendenze Python](requirements.txt) e [pyproject.toml](pyproject.toml)
- [Setup Windows](setup/windows/README.md)
- [Inventario supporto, strumenti e versioni](docs/project-support.md)

## Struttura

- [core](core): configurazione, percorsi e stato
- [doomsday](doomsday): OCR, catalogo, runtime e visione
- [repositories](repositories), [services](services), [ui](ui): persistenza, logica applicativa e pannelli
- [data/doomsday/knowledge](data/doomsday/knowledge): conoscenza semantica versionata e condivisibile
- `workstation/local/<profilo>/runtime/`: impostazioni, database, log, catture e altri dati locali ignorati
- [tests](tests): suite di verifica automatica

## Conoscenza tra workstation

Per rendere gli apprendimenti disponibili sugli altri computer usa il flusso GitHub documentato in [Condivisione della conoscenza](docs/knowledge-sharing.md): aggiorna il clone, esegui l'export additivo, rivedi il diff, poi commit e push su `main`. Le altre postazioni ricevono il catalogo con `git pull origin main`; il database locale importa gli elementi visuali condivisi.

## Esecuzione, analisi e sviluppo

L'esecuzione di piani semantici resta disabilitata per impostazione predefinita. I candidati derivati da apprendimento o traffico metadata-only richiedono revisione umana e non conferiscono autorità di playback. Consulta [intelligent-assistant.md](docs/architecture/intelligent-assistant.md), [network-observation.md](docs/architecture/network-observation.md) e le [interfacce pubblicate](interfaces).

Per verificare il clone:

```powershell
python workstation/settings.py
python workstation/test_settings.py
python scripts/validate_portability.py
python -m unittest discover -s tests -p "test_*.py"
```

## Knowledge hub

Le istruzioni di sviluppo e i collegamenti ai registry condivisi sono in [AGENTS.md](AGENTS.md). Il manifest del progetto è [project-manifest.json](project-manifest.json); la scheda centralizzata vive nel repository [robvamos/knowledge](https://github.com/robvamos/knowledge).

## Intelligence di gioco

La versione 0.5 aggiunge un core separato dalla GUI e dal playback legacy che:

- interpreta obiettivi come Campagna, Challenge, Arena, rally, guarnigione ed eventi;
- seleziona modalità e ruleset compatibili con la versione del gioco;
- costruisce piani di azioni semantiche, mai coordinate grezze;
- riconosce vincoli espliciti come `senza spendere valuta` o `senza perdite`;
- conserva provenienza, confidenza e conflitti tra fonti;
- applica una policy immediatamente prima di ogni futura esecuzione;
- valuta gli esiti e registra episodi in un database intelligence separato.

Per validare il dominio o ispezionare un piano senza eseguire macro:

```powershell
python scripts/plan_game_objective.py --validate
python scripts/plan_game_objective.py --list-modes
python scripts/plan_game_objective.py "migliora in Arena della Gloria senza spendere valuta" --game-version 1.56.0
```

L'esecuzione è disabilitata per impostazione predefinita. Il database macro in
conflitto e i nodi UI privi di riconoscitori sono blocker espliciti, documentati
in [intelligent-assistant.md](docs/architecture/intelligent-assistant.md).

## Integrazione workspace

Il progetto e' stato anche registrato nel workspace condiviso AI:

- [AGENTS.md](AGENTS.md)
- [project-manifest.json](project-manifest.json)
- [project card nel knowledge hub](https://github.com/robvamos/knowledge/blob/main/projects/ddgameass.yaml)

Le interfacce Doomsday condivise verso altri progetti sono documentate in:

- [interfaces/doomsday-roster-bootstrap.md](interfaces/doomsday-roster-bootstrap.md)
- [interfaces/doomsday-vision-primitives.md](interfaces/doomsday-vision-primitives.md)
- [interfaces/doomsday-creators-pipeline.md](interfaces/doomsday-creators-pipeline.md)
- [interfaces/doomsday-intelligence-runtime.md](interfaces/doomsday-intelligence-runtime.md)
- [interfaces/doomsday-runtime-roster-acquisition.md](interfaces/doomsday-runtime-roster-acquisition.md)
- [interfaces/doomsday-hero-interface-learning.md](interfaces/doomsday-hero-interface-learning.md)
- [interfaces/doomsday-network-observation.md](interfaces/doomsday-network-observation.md)

## Runtime del gioco e acquisizione roster

Il progetto mantiene un inventario interrogabile per ciascuna workstation:

- VirtualBox con Android-x86 9.0-r2, storico;
- BlueStacks 5, installato ma non attivo;
- client Windows Doomsday; la versione e i percorsi vengono rilevati localmente.

L'ultima osservazione documentata ha rilevato il client 1.58.0 il 23/07/2026; questo dato storico non imposta il runtime di altre workstation.

Per ispezionarlo senza avviare emulatori o ADB:

```powershell
python scripts/probe_game_runtimes.py
```

La prima interfaccia roster usa una cattura Win32 della finestra già visibile,
poi OCR e contributi con provenienza. Non legge memoria o traffico di rete e non
sovrascrive direttamente il roster. Dettagli e prossimi passi sono in
[runtime-roster-acquisition.md](docs/architecture/runtime-roster-acquisition.md).

### Learning supervisionato visuale + rete

La modalita' Learning avvia o riusa automaticamente l'osservatore di rete
metadata-only e collega ogni click ai frame e alla finestra di messaggi
TCP/UDP corrispondente. Per insegnare il percorso lista eroi:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_learning_mode.ps1 -Mode general -Minutes 15 -Scenario hero-inspection
```

Per esplorare un dominio:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_learning_mode.ps1 `
  -Mode general -Minutes 15 -Domain research
```

Domini iniziali: `battle_reports`, `resources`, `armaments`, `gathering`,
`workshop`, `research` e `missions`. Il proxy puo' essere escluso soltanto
esplicitamente con `-DisableNetworkObservation`; la sessione viene allora
marcata come parziale.

La sessione si ferma con `Ctrl+Alt+S`. Ogni click viene scritto subito in un
journal locale e associato a frame completi, cursori degli eventi di rete e una
fingerprint metadata-only. Al termine viene generato
`network_correlation_summary.json`.
Le coordinate non diventano etichette semantiche: automazione e commit roster
restano bloccati fino alla validazione visiva e alla conferma esplicita.

Il motore OCR usa Tesseract CLI locale con `ita+eng`; il profilo 1.58.0 contiene
per ora solo l'anchor testuale `Eroe`. Le ROI delle viste interne saranno
calibrate dai frame acquisiti. Vedi
[hero-interface-learning.md](docs/architecture/hero-interface-learning.md).
Il modello generale di convergenza e' descritto in
[dual-evidence-learning.md](docs/architecture/dual-evidence-learning.md).

### Osservazione di rete metadata-only

Mitmproxy è opzionale e viene installato nell'ambiente virtuale indicato dal
profilo workstation; Wireshark/tshark è opzionale per classificare TCP/UDP non
HTTP. La modalità predefinita osserva soltanto il PID Doomsday, inoltra TLS
ancora cifrato e non modifica il proxy di Windows né il trust store.

Per preparare in modo riproducibile il runtime opzionale dopo un clone:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_network_observation.ps1
```

Per usare lo stesso collegamento del Desktop e poi osservare il processo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_network_observation.ps1 -TargetProcess Doomsday -LaunchViaShortcut -Minutes 5
```

Il collegamento risolve il launcher `DoomsdayLastSurvivors.exe`. Il binario
versionato `Doomsday.exe` non viene mai avviato direttamente, perché senza il
contesto del launcher risponde con `ErrCode: 0x4`.

I file runtime finiscono in `workstation/local/<profilo>/runtime/network_observation/`.
Non vengono salvati header, cookie, token, valori query o payload; gli
identificativi probabili nei path vengono sostituiti da segnaposto. Vedi
[network-observation.md](docs/architecture/network-observation.md).

## Test automatici

Per eseguire la suite:

```powershell
python -m unittest discover -s tests -v
```

Gli entrypoint ripuliscono dall'ambiente gli overlay NumPy/Pillow incompatibili
iniettati da altri strumenti del workspace.

Per inizializzare o riallineare il database Doomsday importando i dataset presenti in `data/doomsday/`:

```powershell
python bootstrap_doomsday_data.py
```

La copertura attuale include:

- servizi operativi
- stato applicativo
- repository SQLite
- configurazione centrale
- dominio Doomsday versionato, planner, policy, outcome, provider ed evidenze

## Utility incluse

- [debug_macro_playback.py](debug_macro_playback.py): diagnostica dei problemi di riproduzione
- [repair_macros.py](repair_macros.py): riparazione e verifica macro
- [test_focus_logic.py](test_focus_logic.py): script di verifica manuale della logica focus

## Elementi grafici del gioco

La tab `Elementi` e' stata impostata per acquisire elementi grafici senza distorsioni:

- l'immagine salvata viene preservata nelle dimensioni originali
- lo storage viene normalizzato in `PNG` lossless
- l'anteprima e' ridotta solo a scopo visivo, senza alterare il file memorizzato
- oltre a nome e descrizione, e' possibile annotare anche il ruolo semantico dell'elemento

Procedura consigliata:

- [docs/GAME_ELEMENT_INGESTION_WORKFLOW.md](docs/GAME_ELEMENT_INGESTION_WORKFLOW.md)

### Censimento rapido da Codex

Se vogliamo censire un elemento senza passare dalla UI, ora c'e' anche un flusso diretto:

```powershell
python scripts/register_game_element.py --image "F:\percorso\elemento.png" --name "popup_crossed_circle_symbol" --description "Chiude alcuni popup bloccanti." --connotation "popup close recovery symbol"
```

Oppure, se hai gia' copiato l'immagine negli appunti di Windows:

```powershell
python scripts/register_game_element.py --clipboard --name "popup_crossed_circle_symbol" --description "Chiude alcuni popup bloccanti." --connotation "popup close recovery symbol"
```

Questo percorso:

- preserva l'immagine senza distorsioni
- applica la deduplica col catalogo esistente
- salva la connotazione semantica insieme alla descrizione
- registra di default gli elementi inseriti da Codex come elementi di sistema protetti
- restituisce a schermo se l'elemento e' stato creato o riusato

Gli elementi di sistema non vengono eliminati dalla galleria e non vengono rimossi da una pulizia generale del catalogo. Per registrarne uno cancellabile dall'utente usa `--user-element`.

## Documentazione interna

- [docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)
- [docs/README_FOCUS_FIX.md](docs/README_FOCUS_FIX.md)
- [docs/SOLUZIONE_MACRO_PLAYBACK.md](docs/SOLUZIONE_MACRO_PLAYBACK.md)
- [docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md](docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md)
- [docs/architecture/intelligent-assistant.md](docs/architecture/intelligent-assistant.md)
- [docs/architecture/runtime-roster-acquisition.md](docs/architecture/runtime-roster-acquisition.md)
- [docs/architecture/network-observation.md](docs/architecture/network-observation.md)
- [CHANGELOG.md](CHANGELOG.md)
- [ROADMAP.md](ROADMAP.md)

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

- [docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md](docs/DOOMSDAY_CREATOR_TURF_PUBLICATION.md)
- [interfaces/doomsday-creators-pipeline.md](interfaces/doomsday-creators-pipeline.md)
- [data/doomsday/creator_turf/creator-program-plan.json](data/doomsday/creator_turf/creator-program-plan.json)

## Workstation configuration

Read [workstation/README.md](workstation/README.md). Preserve each host profile; never commit local values or expose them through HTTP.
