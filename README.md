# Wind Rose - ERC 4.0 Rotor Controller

Applicazione con **rosa dei venti** per il controllo del rotore **ERC 4.0** (solo azimut), con integrazione **PstRotator (YO3DMU)** e **SDC (UT4LW)** via UDP usando il protocollo **GS232B**.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Protocol](https://img.shields.io/badge/Protocol-GS232B%20%7C%20PstRotator-green)
![Interface](https://img.shields.io/badge/Interface-UDP-orange)

## Funzionalita'

- **Rosa dei venti interattiva**: clicca sulla bussola per puntare l'antenna
- **Direzioni preimpostate**: N, NE, E, SE, S, SW, W, NW con un click
- **Azimut manuale**: inserisci gradi (0-360) e premi VAI
- **Rotazione continua**: CCW / CW con pulsanti dedicati
- **STOP** di emergenza
- **Polling automatico**: legge la posizione corrente dal rotore ogni secondo
- **Doppia modalita' di connessione**:
  - **PstRotator**: comunicazione UDP con PstRotator di YO3DMU
  - **GS232B/SDC**: comunicazione diretta UDP con SDC di UT4LW
- **Preset (UTP)**: salva, carica ed elimina posizioni con nome personalizzato (file JSON persistente)
- **Log comandi**: area dedicata che mostra tutti i comandi TX/RX inviati e ricevuti con timestamp
- **Barra di stato**: mostra l'ultimo comando inviato/ricevuto in tempo reale
- **Impostazioni persistenti**: host, porta e modalita' vengono salvati automaticamente

## Requisiti

- Python 3.10+
- Tkinter (incluso di default con Python)
- PstRotator (YO3DMU) oppure SDC (UT4LW) configurato con porta UDP per il controllo rotore

## Installazione

```bash
git clone https://github.com/iw3ssd/recorder-file.git
cd recorder-file
python3 wind_rose_erc4.py
```

Nessuna dipendenza esterna richiesta: usa solo la libreria standard di Python.

## Utilizzo

1. Avvia **PstRotator** (o **SDC**) e configura la connessione UDP per il rotore ERC 4.0
2. Avvia `wind_rose_erc4.py`
3. Seleziona la modalita': **PstRotator** o **GS232B/SDC**
4. Inserisci l'indirizzo IP e la porta UDP (default: `127.0.0.1:12000`)
5. Clicca **Connetti**
6. Usa la rosa dei venti, i pulsanti direzionali o l'azimut manuale per controllare il rotore

### Gestione Preset (UTP)

1. Inserisci un **nome** e un **azimut** nella sezione "Preset (UTP)"
2. Clicca **Salva** per memorizzare il preset
3. Seleziona un preset dalla lista e clicca **Vai** per puntare il rotore
4. Clicca **Elimina** per rimuovere un preset
5. I preset vengono salvati in `%APPDATA%/WindRoseERC4/presets.json` (Windows) o `~/WindRoseERC4/presets.json` (Linux/Mac)

### Log Comandi

L'area "Log Comandi" in basso mostra ogni comando inviato (TX) e ogni risposta ricevuta (RX) con il timestamp. La barra di stato mostra sempre l'ultimo comando.

## Protocolli Supportati

### GS232B (SDC/UT4LW)

| Comando | Descrizione |
|---------|-------------|
| `C`     | Richiedi azimut corrente |
| `Mxxx`  | Vai all'azimut xxx (000-360) |
| `S`     | Stop rotazione |
| `L`     | Ruota a sinistra (CCW) |
| `R`     | Ruota a destra (CW) |

### PstRotator (YO3DMU)

| Comando | Descrizione |
|---------|-------------|
| `<PST>AZ:xxx.x</PST>` | Imposta azimut |
| `<PST>AZ?</PST>`       | Richiedi azimut corrente |
| `<PST>STOP</PST>`      | Stop rotazione |

## Architettura

```
                          PstRotator Mode:
Wind Rose App ---(UDP/PST)----> PstRotator ---(Seriale/GS232B)---> ERC 4.0 ---> Rotore

                          GS232B/SDC Mode:
Wind Rose App ---(UDP/GS232B)---> SDC (UT4LW) ---(Seriale)---> ERC 4.0 ---> Rotore
```

## Configurazione ERC 4.0

Assicurarsi che l'ERC 4.0 sia configurato con:
- Protocollo: **GS232B**
- Baudrate: **9600** (o secondo configurazione)
- In PstRotator: selezionare ERC 4.0 come controller e configurare la porta COM
- In SDC: creare un ponte UDP verso la porta COM del ERC 4.0

## File di Configurazione

| File | Percorso | Descrizione |
|------|----------|-------------|
| `presets.json` | `%APPDATA%/WindRoseERC4/` | Preset salvati dall'utente |
| `settings.json` | `%APPDATA%/WindRoseERC4/` | Impostazioni di connessione |

---

# Contest Online ScoreBoard — Viewer

Applicazione Python/tkinter per visualizzare i contest a cui un nominativo sta partecipando su [contestonlinescore.com](https://contestonlinescore.com/).

## Funzionalita'

- **Ricerca per nominativo**: inserisci il callsign e cerca in tutti i contest attivi
- **Scansione automatica**: analizza tutti i contest correnti (closed, on air)
- **Tabella risultati**: mostra contest, categoria, posizione, punteggio, QSO, unici, club
- **Apri nel browser**: click per aprire il contest selezionato su contestonlinescore.com
- **Barra di progresso**: indica l'avanzamento della scansione

## Requisiti

- Python 3.10+
- `requests` e `beautifulsoup4`

```bash
pip3 install requests beautifulsoup4
```

## Utilizzo

```bash
python3 contest_viewer.py
```

1. Il nominativo predefinito e' **IW3SSD** (modificabile)
2. Clicca **Cerca** per avviare la scansione
3. I risultati appariranno nella tabella
4. Seleziona una riga e clicca **Apri nel browser** per vedere il contest completo

---

## Licenza

Uso libero per radioamatori.

## Autore

IW3SSD - Andrea
