# 🔧 Soluzione Problema Riproduzione Macro

## 📋 Descrizione del Problema

Le macro non vengono più riprodotte nella finestra del gioco. Questo può essere causato da diversi fattori:

1. **Problemi di focus della finestra**
2. **Eventi macro corrotti o malformattati**
3. **Coordinate mouse invalide**
4. **Problemi con gli hook di tastiera/mouse**
5. **Conflitti con altre applicazioni**

## 🚀 Soluzioni Disponibili

### 1. Script di Diagnostica

Esegui lo script di diagnostica per identificare il problema specifico:

```bash
cd macro_controller
python debug_macro_playback.py
```

Questo script eseguirà una serie di test per verificare:
- ✅ Connessione al database
- ✅ Caricamento delle macro
- ✅ Rilevamento della finestra target
- ✅ Riproduzione delle macro

### 2. Strumento di Riparazione

Se vengono identificati problemi, usa lo strumento di riparazione automatica:

```bash
cd macro_controller
python repair_macros.py
```

Opzioni disponibili:
1. **Verifica integrità macro** - Controlla tutte le macro per problemi
2. **Ripara macro problematiche** - Ripara automaticamente i problemi trovati
3. **Crea backup macro** - Crea backup prima della riparazione
4. **Esci** - Chiude lo strumento

### 3. Configurazione Avanzata

Lo script `macro_config.py` fornisce configurazioni avanzate per:
- Intervalli di controllo del focus
- Timeout per l'attesa delle finestre
- Delay per input simulation
- Validazione eventi
- Impostazioni di debug

## 🔍 Diagnosi Step-by-Step

### Passo 1: Verifica Database
```bash
python debug_macro_playback.py
```
- Controlla se il database esiste e è accessibile
- Verifica la struttura delle tabelle
- Conta le macro disponibili

### Passo 2: Verifica Macro
- Controlla se le macro hanno eventi validi
- Verifica la struttura degli eventi
- Controlla le coordinate del mouse

### Passo 3: Verifica Finestra Target
- Assicurati che l'applicazione target sia aperta
- Verifica che il nome dell'eseguibile sia corretto
- Controlla che la finestra sia visibile e non minimizzata

### Passo 4: Test Riproduzione
- Esegui un test di riproduzione con timeout
- Controlla i log per errori specifici
- Verifica che gli hook di input funzionino

## 🛠️ Risoluzione Problemi Comuni

### Problema: "Nessun evento trovato"
**Soluzione**: La macro non ha eventi registrati o sono stati corrotti
```bash
python repair_macros.py
# Scegli opzione 2 per riparare automaticamente
```

### Problema: "Finestra target non trovata"
**Soluzioni**:
1. Assicurati che l'applicazione sia aperta
2. Verifica il nome dell'eseguibile nelle impostazioni della macro
3. Controlla che la finestra non sia minimizzata

### Problema: "Coordinate mouse invalide"
**Soluzione**: Le coordinate sono fuori range o malformattate
```bash
python repair_macros.py
# Lo strumento normalizzerà automaticamente le coordinate
```

### Problema: "Hook di tastiera/mouse non funzionano"
**Soluzioni**:
1. Riavvia l'applicazione
2. Verifica che non ci siano conflitti con altre app
3. Controlla i permessi dell'applicazione

## ⚙️ Configurazione Ottimale

### File: `config/macro_config.json`
```json
{
  "playback": {
    "focus_check_interval": 0.05,
    "event_delay_tolerance": 0.01,
    "mouse_coordinate_validation": true,
    "keyboard_event_validation": true,
    "max_playback_duration": 300,
    "retry_on_focus_loss": true,
    "max_retry_attempts": 3
  },
  "window_management": {
    "focus_wait_timeout": 10.0,
    "window_detection_retry": 3,
    "client_area_only": true
  },
  "input_simulation": {
    "keyboard_delay": 0.01,
    "mouse_delay": 0.01,
    "use_absolute_coordinates": true,
    "coordinate_rounding": true
  }
}
```

## 🔄 Processo di Riparazione Completa

### 1. Backup (Raccomandato)
```bash
python repair_macros.py
# Scegli opzione 3 per creare backup
```

### 2. Verifica Integrità
```bash
python repair_macros.py
# Scegli opzione 1 per verificare
```

### 3. Riparazione Automatica
```bash
python repair_macros.py
# Scegli opzione 2 per riparare
```

### 4. Test Post-Riparazione
```bash
python debug_macro_playback.py
# Verifica che tutto funzioni
```

## 📱 Utilizzo dalla GUI

Dopo la riparazione, riavvia la GUI del Macro Manager:

```bash
python gui_macro_manager.py
```

### Controlli nella GUI:
1. **Seleziona una macro** dalla lista
2. **Verifica i dettagli** nel pannello destro
3. **Clicca "Riproduci"** per testare
4. **Controlla la console** per messaggi di errore

## 🚨 Risoluzione Emergenza

Se nulla funziona, usa il pulsante **STOP EMERGENZA** nella GUI:

1. Clicca "🚨 STOP EMERGENZA"
2. Riavvia l'applicazione
3. Esegui la diagnostica completa
4. Ripara le macro se necessario

## 📞 Supporto Tecnico

### Log di Debug
Abilita il logging dettagliato in `config/macro_config.json`:
```json
{
  "debug": {
    "enable_logging": true,
    "log_level": "DEBUG",
    "save_playback_logs": true,
    "validate_events_before_playback": true
  }
}
```

### Informazioni Utili
- **Versione Python**: 3.7+
- **Database**: SQLite3
- **Librerie**: keyboard, mouse, win32gui, psutil
- **Sistema**: Windows 10/11

### Comandi di Test Rapido
```bash
# Test rapido database
python -c "import sqlite3; conn = sqlite3.connect('data/macro_recorder.db'); print('Database OK')"

# Test rapido moduli
python -c "import keyboard, mouse, win32gui; print('Moduli OK')"

# Test configurazione
python macro_config.py
```

## ✅ Checklist di Verifica

- [ ] Database accessibile e valido
- [ ] Macro presenti con eventi validi
- [ ] Applicazione target aperta e visibile
- [ ] Nome eseguibile corretto nelle macro
- [ ] Hook di input funzionanti
- [ ] Coordinate mouse normalizzate
- [ ] Configurazione ottimale
- [ ] Test di riproduzione completato

## 🎯 Risultato Atteso

Dopo aver seguito questi passaggi, le macro dovrebbero:
1. **Caricarsi correttamente** dal database
2. **Rilevare la finestra target** automaticamente
3. **Riprodursi senza errori** nella finestra del gioco
4. **Gestire il focus** in modo intelligente
5. **Fermarsi correttamente** quando richiesto

---

**💡 Suggerimento**: Esegui sempre la diagnostica prima di tentare riparazioni manuali per identificare il problema specifico.
