# Wind Rose - ERC 4.0 Rotor Controller

Applicazione con **rosa dei venti** per il controllo del rotore **ERC 4.0** (solo azimut), con integrazione **PstRotator** via UDP (porte separate IN/OUT).

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Protocol](https://img.shields.io/badge/Protocol-PstRotator-green)
![Interface](https://img.shields.io/badge/Interface-UDP-orange)

## Funzionalita'

- **Rosa dei venti interattiva**: clicca sulla bussola per puntare l'antenna
- **Direzioni preimpostate**: N, NE, E, SE, S, SW, W, NW con un click
- **Azimut manuale**: inserisci gradi (0-360) e premi VAI
- **Nudge ±10°**: pulsanti per spostamento relativo di ±10 gradi
- **STOP** di emergenza
- **Ricezione posizione**: ascolto continuo dei report di posizione da PstRotator sulla porta UDP IN
- **Comunicazione UDP**: porte separate per invio comandi (OUT) e ricezione posizione (IN) verso PstRotator

## Requisiti

- Python 3.10+
- Tkinter (incluso di default con Python)
- PstRotator configurato con UDP Control abilitato

## Installazione

```bash
git clone https://github.com/iw3ssd/recorder-file.git
cd recorder-file
python3 wind_rose_erc4.py
```

## Utilizzo

1. Avvia **PstRotator** e abilita il controllo UDP (Setup → UDP Control)
2. Avvia `wind_rose_erc4.py`
3. Configura:
   - **Host**: indirizzo IP di PstRotator (default: `127.0.0.1`)
   - **Porta OUT**: porta UDP per inviare comandi a PstRotator (default: `12000`)
   - **Porta IN**: porta UDP per ricevere la posizione da PstRotator (default: `12001`)
4. Clicca **Connetti**
5. Usa la rosa dei venti, i pulsanti direzionali o l'azimut manuale per controllare il rotore

## Protocollo PstRotator (UDP)

Comandi inviati a PstRotator (porta OUT):

| Comando | Descrizione |
|---------|-------------|
| `<PST><AZIMUTH>xxx.x</AZIMUTH></PST>` | Vai all'azimut xxx |
| `<PST>AZ?</PST>` | Richiedi azimut corrente |
| `<PST>STOP</PST>` | Stop rotazione |

Risposte ricevute da PstRotator (porta IN):

| Formato | Descrizione |
|---------|-------------|
| `AZ xxx.x` | Report posizione azimut corrente |

## Architettura

```
Wind Rose App ---[UDP porta OUT]---> PstRotator ---(Seriale)---> ERC 4.0 ---> Rotore
              <--[UDP porta IN]----  PstRotator (position reports)
```

## Configurazione PstRotator

In PstRotator:
1. **Setup → UDP Control**: abilitare
2. **Port**: impostare la porta UDP (default 12000) — corrisponde alla porta OUT dell'app
3. **Position Reporting**: abilitare il report automatico della posizione — i dati verranno inviati alla porta IN dell'app

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

## Eseguibili Windows (.exe)

Entrambe le applicazioni possono essere compilate come eseguibili Windows standalone (non serve Python installato).

### Download

Scarica gli `.exe` dalla pagina [Releases](../../releases) di questo repository.

| Eseguibile | Applicazione |
|---|---|
| `WindRose_ERC4.exe` | Wind Rose — ERC 4.0 Azimuth Controller |
| `ContestViewer.exe` | Contest Online ScoreBoard Viewer |

### Build manuale (su Windows)

1. Installa [Python 3.10+](https://www.python.org/downloads/)
2. Esegui lo script:

```batch
build_windows.bat
```

Gli eseguibili saranno in `dist\`.

### Build automatica (GitHub Actions)

La workflow **Build Windows Executables** compila automaticamente gli `.exe` quando si crea un tag `v*`:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Oppure puoi avviare la build manualmente dalla tab **Actions** del repository.

---

## Licenza

Uso libero per radioamatori.

## Autore

IW3SSD - Andrea
