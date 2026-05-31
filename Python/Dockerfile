# =====================================================================
# Dockerfile -- Energy-Truth algoritme (worker + refresher in een image)
#
# Een "image" is een ingepakte computer: Python, de pakketten en onze code,
# samen in een afsluitbaar doosje dat overal hetzelfde draait. Kubernetes
# start straks dit doosje als een "pod".
#
# We bouwen in twee stappen (two-stage build), net als Vik:
#   1. builder: installeert de pakketten in een schone virtuele omgeving.
#   2. runtime: kopieert ALLEEN die omgeving + onze code. Geen build-rommel,
#      dus een kleinere en veiligere image.
#
# Zelfde image voor allebei:
#   - worker   -> draait standaard (CMD hieronder) als Deployment-poller.
#   - refresher-> de CronJob overschrijft het commando naar refresher.py.
# =====================================================================

# ---- Stap 1: builder ------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

# Maak een virtuele omgeving en installeer daar de exacte (gepinde) versies.
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# ---- Stap 2: runtime (de echte image) -------------------------------
FROM python:3.12-slim-bookworm

# PYTHONUNBUFFERED=1  -> logs verschijnen direct in `kubectl logs`, ook bij crash.
# PYTHONUTF8=1        -> alles draait in UTF-8 (geen rare tekens in logs).
# PYTHONDONTWRITEBYTECODE -> geen .pyc-bestanden op de (readonly) schijf.
# MPLCONFIGDIR        -> matplotlib mag alleen naar /tmp schrijven (zie k8s volume).
# PATH                -> gebruik de venv-Python uit stap 1.
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    PATH="/opt/venv/bin:$PATH"

# Neem de kant-en-klare pakketten uit de builder over.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Draai NIET als root (veiligheidseis uit het veiligheidsrapport, punt 7).
# We maken een gewone gebruiker met een vast nummer.
RUN useradd --create-home --uid 10001 appuser

# Kopieer onze code. .dockerignore houdt .env, secrets, README's enz. eruit.
COPY --chown=appuser:appuser . /app

USER appuser

# Standaard-commando: de worker (poller). De CronJob zet dit straks om naar
# `python refresher.py`.
CMD ["python", "worker.py"]
