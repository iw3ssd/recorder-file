# Wind Rose - ERC 4.0 Rotor Controller

Applicazione con **rosa dei venti** per il controllo del rotore **ERC 4.0** (solo azimut), con integrazione **SDC (UT4LW)** via UDP usando il protocollo **GS232B**.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Protocol](https://img.shields.io/badge/Protocol-GS232B-green)
![Interface](https://img.shields.io/badge/Interface-UDP-orange)

## Funzionalita'

- **Rosa dei venti interattiva**: clicca sulla bussola per puntare l'antenna
- **Direzioni preimpostate**: N, NE, E, SE, S, SW, W, NW con un click
- **Azimut manuale**: inserisci gradi (0-360) e premi VAI
- **Rotazione continua**: CCW / CW con pulsanti dedicati
- **STOP** di emergenza
- **Polling automatico**: legge la posizione corrente dal rotore ogni secondo
- **Comunicazione UDP**: si integra con SDC di UT4LW via protocollo GS232B su UDP

## Requisiti

- Python 3.10+
- Tkinter (incluso di default con Python)
- SDC (UT4LW) configurato con porta UDP per il controllo rotore

## Installazione

```bash
git clone https://github.com/iw3ssd/recorder-file.git
cd recorder-file
python3 wind_rose_erc4.py
```

## Utilizzo

1. Avvia SDC e configura la connessione UDP per il rotore ERC 4.0
2. Avvia `wind_rose_erc4.py`
3. Inserisci l'indirizzo IP e la porta UDP di SDC (default: `127.0.0.1:12000`)
4. Clicca **Connetti**
5. Usa la rosa dei venti, i pulsanti direzionali o l'azimut manuale per controllare il rotore

## Protocollo GS232B

Comandi supportati (inviati via UDP a SDC):

| Comando | Descrizione |
|---------|-------------|
| `C`     | Richiedi azimut corrente |
| `Mxxx`  | Vai all'azimut xxx (000-360) |
| `S`     | Stop rotazione |
| `L`     | Ruota a sinistra (CCW) |
| `R`     | Ruota a destra (CW) |

## Architettura

```
Wind Rose App ---(UDP/GS232B)---> SDC (UT4LW) ---(Seriale)---> ERC 4.0 ---> Rotore
```

## Configurazione ERC 4.0

Assicurarsi che l'ERC 4.0 sia configurato con:
- Protocollo: **GS232B**
- Baudrate: **9600** (o secondo configurazione)
- In SDC: creare un ponte UDP verso la porta COM del ERC 4.0

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
