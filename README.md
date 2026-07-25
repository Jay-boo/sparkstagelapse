# spark-prettyprint

Affichage interactif de DataFrames (Spark ou pandas), que vous soyez dans un
notebook, un script, ou un run Databricks — avec un dashboard web local qui
**reste ouvert et à jour même après la fin du script qui l'a lancé.**

## Installation

Depuis la racine de ce dossier :

```bash
pip install -e .
# ou, si vous voulez l'explorateur plein écran (Textual) :
pip install -e ".[tui]"
```

## Usage rapide

```python
from spark_prettyprint import display_spark

# df = spark.sql("select * from ...")
display(df, title="Employees")        # mode "auto" : notebook -> riche, script -> dashboard web
display(df, title="Employees", mode="web")   # force le dashboard web
display(df, title="Employees", mode="tui")   # explorateur plein écran (bloquant)
display(df, title="Employees", mode="rich")  # impression ASCII terminal
```

Ou directement sur un pandas DataFrame :

```python
from spark_prettyprint import SparkDisplay

SparkDisplay(pdf, title="Aperçu").show_web()
```

## Le dashboard persistant

Au premier `show_web()` (ou `mode="web"`), le client :

1. Vérifie si un serveur répond déjà sur `127.0.0.1:8765` (`/health`).
2. Si oui : pousse simplement la nouvelle table dessus en HTTP, aucun
   nouveau process n'est créé.
3. Si non : **spawn le serveur dans un process détaché** (pas un thread —
   un thread daemon meurt avec son process parent, un process séparé non).
   Le script continue de tourner normalement, sans bloquer.

Le serveur reste donc actif après la fin du script. Le prochain run — même
demain, même depuis un autre script — retrouvera le même dashboard déjà
ouvert dans votre navigateur et le mettra à jour en websocket.

### Gérer le serveur manuellement

```bash
python -m spark_prettyprint.dashboard status
python -m spark_prettyprint.dashboard stop
python -m spark_prettyprint.dashboard start   # démarrage manuel, bloquant, premier plan
```

Logs et pidfile : `~/.cache/spark-prettyprint/dashboard_<port>.log` / `.pid`.

### Changer le port / host

```python
from spark_prettyprint import DashboardClient, SparkDisplay

client = DashboardClient(host="127.0.0.1", port=9000)
SparkDisplay(pdf, title="Aperçu", _dashboard=client).show_web()
```

## Structure du package

```
src/spark_prettyprint/
├── __init__.py            # API publique : SparkDisplay, display_spark, DashboardClient
├── display.py              # SparkDisplay / display_spark — rendu selon le contexte
└── dashboard/
    ├── app.py               # app FastAPI (routes HTTP + WebSocket), state en mémoire
    ├── server.py            # bootstrap serveur (foreground), pid/log files
    ├── client.py             # DashboardClient : health-check, spawn détaché, push HTTP
    ├── templates.py          # template HTML/JS + rendu table -> HTML
    └── __main__.py            # CLI : start / stop / status
```
