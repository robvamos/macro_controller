# Supporto del progetto

Questo inventario distingue gli elementi richiesti dal codice, quelli necessari soltanto a workflow specifici e quelli verificati su questa workstation. Le versioni installate possono differire sulle altre postazioni: registra i risultati effettivi in `workstation/local/<profilo>/support-inventory.json`, che è ignorato da Git.

Aggiorna l'inventario locale con:

```powershell
python scripts/collect_support_inventory.py
```

## Strumenti di sviluppo

| Elemento | Categoria | Verifica / versione |
|---|---|---|
| Python | Richiesto per app, CLI e test | `python --version`; l'app supporta Python 3.11+ |
| Git | Richiesto per sincronizzare conoscenza tra workstation | `git --version`, `git remote -v` |
| PowerShell | Richiesto per launcher e setup Windows | `$PSVersionTable.PSVersion` |
| Skills `attivasviluppo`, `sviluppo-conoscenza` | Richieste nel workspace condiviso per setup e coordinamento | Segui le istruzioni delle skill installate localmente |
| Skill `project-bootstrap` | Riutilizzata per sincronizzare manifest e schede Knowledge | Installata nel workspace Codex |
| Plugin/app esterni | Nessuno richiesto dal runtime | Non vengono installati dal progetto |

## Dipendenze Python

Le dipendenze applicative sono dichiarate in `pyproject.toml` e `requirements.txt`. Il workflow di osservazione rete è separato e usa i pin in `requirements-network-observation.txt` in un ambiente virtuale locale.

| Dipendenza | Uso | Verifica |
|---|---|---|
| NumPy, OpenCV, Pillow | Visione, immagini e OCR | `python -c "import numpy, cv2, PIL; print(numpy.__version__, cv2.__version__, PIL.__version__)"` |
| keyboard, mouse, psutil, PyGetWindow, pywin32 | Input, finestre e processi Windows | `python -c "import importlib.metadata as m; print({n:m.version(n) for n in ['keyboard','mouse','psutil','PyGetWindow','pywin32']})"` |
| mitmproxy | Facoltativo: osservazione locale metadata-only per PID | `workstation/settings.py --get networkObserverDir`, poi `mitmdump --version` |

## Programmi esterni facoltativi

| Programma | Workflow | Verifica |
|---|---|---|
| Tesseract OCR | Lettura OCR locale, lingue `ita+eng` | `TESSERACT_EXE` oppure `tesseract --version` e `tesseract --list-langs` |
| Wireshark / tshark | Ispezione di catture locali, se necessaria | `Get-Command tshark` e `tshark --version` |
| Client Doomsday / BlueStacks / VirtualBox | Discovery runtime, cattura e apprendimento visuale | Imposta i percorsi nel profilo o usa il discovery in sola lettura |

Un elemento si considera **verificato** solo dopo un controllo eseguito sulla workstation attiva. Un valore in uno schema, nel file requisiti o nel registro condiviso non prova che il programma sia installato localmente. Non installare strumenti opzionali se il workflow non li richiede. Nessun setup modifica CA attendibili o proxy Windows.

## Verifiche del repository

Dopo una modifica, `python workstation/settings.py`, `python workstation/test_settings.py`, `python scripts/validate_portability.py` e la suite `python -m unittest discover -s tests -p "test_*.py"` controllano la configurazione e il codice. La CI esegue gli stessi controlli su Windows.