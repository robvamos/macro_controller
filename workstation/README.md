# Configurazione workstation

Lo schema portabile è in `settings.schema.json` e l'esempio senza valori macchina è in `settings.example.json`. Ogni clone mantiene impostazioni, database e runtime nella cartella ignorata `workstation/local/<profilo>/`.

Crea il profilo locale con il nome della workstation (minuscolo):

```powershell
python workstation/settings.py --init
```

Il comando non sovrascrive profili esistenti. Modifica poi `workstation/local/<profilo>/settings.json`. In alternativa seleziona un profilo con `DDGAMEASS_WORKSTATION_PROFILE` oppure un file esplicito con `DDGAMEASS_WORKSTATION_CONFIG`; il selettore del file ha precedenza. Senza selettori viene usato il profilo che corrisponde al nome host, se inizializzato.

`settings.example.json` documenta `workspaceRoot` e `knowledgeRoot`. Gli altri campi sono facoltativi e configurabili dal JSON o dalle variabili `DDGAMEASS_*`, `CODEX_PYTHON_EXE` e `TESSERACT_EXE`. Le stringhe di percorso relative sono risolte dalla radice del checkout, mai dalla cartella corrente del processo. `runtimeDir` e l'ambiente isolato opzionale di mitmproxy restano sotto il profilo locale.

Avvio applicazione:

```powershell
python gui_macro_manager.py
```

Oppure usa `Avvia_Macro_Manager_come_amministratore.bat`, che individua Python dal profilo, da `.venv`, da `PATH` o dal launcher `py`. Il launcher non richiede percorsi installati specifici di una workstation.

Verifica la configurazione dopo il clone o una modifica:

```powershell
python workstation/settings.py
python workstation/test_settings.py
python scripts/validate_portability.py
```

Puoi eseguire lo script di validazione anche da una directory diversa indicando il percorso del checkout. Le prove sintetiche coprono due profili indipendenti, percorsi con spazi, selettori, precedenze e conservazione delle impostazioni esistenti.

I profili non vengono sincronizzati da Git. Consulta [condivisione della conoscenza](../docs/knowledge-sharing.md) per pubblicare gli apprendimenti semantici nel repository in modo revisionabile. Non inserire segreti, screenshot grezzi o percorsi personali nei file condivisi.