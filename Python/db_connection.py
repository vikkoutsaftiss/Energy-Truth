"""
db_connection.py -- PostgreSQL-verbinding voor Energy-Truth.

Direct met de self-hosted database via psycopg2.
Credentials komen uit environment variables (lokaal via .env,
in Kubernetes uit het db-auth Secret).

Gebruik:
    from db_connection import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "Net_Aanbieder" LIMIT 5')
            rows = cur.fetchall()

Voor code die de bestaande .table().select() stijl gebruikt:
    from db_connection import get_client
    client = get_client()
    result = client.table("Net_Aanbieder").select("*").limit(5).execute()
    print(result.data)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

import psycopg2
import psycopg2.extras


# ---------------------------------------------------------------------------
# .env loader (optioneel, alleen lokaal). Geen externe library nodig.
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent / ".env"

def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

_load_env_file(_env_path)


# ---------------------------------------------------------------------------
# Connectie-helper
# ---------------------------------------------------------------------------
def _read_db_env() -> dict:
    required = ["DATABASE_IP", "DATABASE_PORT", "POSTGRES_DB",
                "POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"DB-credentials ontbreken: {missing}", file=sys.stderr)
        print(f"Vul ze in {_env_path} (lokaal) of in het db-auth Secret (cluster).",
              file=sys.stderr)
        sys.exit(1)
    # SSL-modus instelbaar via env (DB_SSLMODE). Standaard 'prefer':
    # versleutelt als de server SSL aanbiedt, valt anders terug op plat
    # verkeer. Daarmee breekt de huidige verbinding met app_test niet
    # (die heeft per mei 2026 nog geen SSL aan). Zodra de Postgres-server
    # SSL aan heeft (self-signed cert volstaat) -> zet DB_SSLMODE=require
    # voor gegarandeerde versleuteling, of verify-full met CA-cert.
    # Zie Security_bevinding_DB-versleuteling.md voor de afweging.
    return {
        "host": os.environ["DATABASE_IP"],
        "port": int(os.environ["DATABASE_PORT"]),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "sslmode": os.environ.get("DB_SSLMODE", "prefer"),
    }


def get_connection():
    """Open een nieuwe psycopg2-connectie. Caller is verantwoordelijk
    voor close (of gebruik `with` context manager).

    Time-outs (instelbaar via env, met verstandige defaults):
      - connect_timeout (seconden): hoe lang we wachten om verbinding te
        krijgen. Voorkomt eindeloos hangen als de DB onbereikbaar is.
        Env: DATABASE_CONNECT_TIMEOUT (default 10).
      - statement_timeout (milliseconden, server-side): de DB breekt een
        enkele query af die te lang draait, zodat een hangende of op-hol-
        geslagen query de worker niet blokkeert. Env:
        DATABASE_STATEMENT_TIMEOUT_MS (default 60000 = 60s).
    """
    cfg = _read_db_env()
    connect_timeout = int(os.environ.get("DATABASE_CONNECT_TIMEOUT", "10"))
    statement_timeout_ms = int(os.environ.get("DATABASE_STATEMENT_TIMEOUT_MS", "60000"))
    return psycopg2.connect(
        connect_timeout=connect_timeout,
        options=f"-c statement_timeout={statement_timeout_ms}",
        **cfg,
    )


# ---------------------------------------------------------------------------
# Compatibiliteits-wrapper: bootst de .table().select().eq().execute() stijl
# na bovenop psycopg2, zodat bestaande modules ongewijzigd kunnen blijven.
# Alle identifiers worden gequote zodat de CamelCase-kolomnamen
# (ProductNaam, Net_AanbiederID, etc.) correct geadresseerd worden.
# ---------------------------------------------------------------------------

def _quote_ident(name: str) -> str:
    """Quote een identifier: ProductNaam -> "ProductNaam"."""
    if name == "*":
        return "*"
    return '"' + name.replace('"', '""') + '"'


def _quote_columns(cols: str) -> str:
    """'ID, ProductNaam' -> '"ID", "ProductNaam"' (laat * staan)."""
    if cols.strip() == "*":
        return "*"
    parts = [c.strip() for c in cols.split(",")]
    return ", ".join(_quote_ident(p) for p in parts if p)


class _Response:
    """Antwoord-object met dezelfde .data en .count attributen."""
    def __init__(self, data: list[dict], count: Optional[int] = None):
        self.data = data
        self.count = count

    def __repr__(self) -> str:
        return f"<Response data={len(self.data)} rows count={self.count}>"


class _Query:
    """Builder die SELECT/INSERT/UPDATE/UPSERT/DELETE collectert
    en op .execute() omzet in een echte SQL-call."""

    def __init__(self, client: "Client", table: str):
        self._client = client
        self._table = table
        self._mode = "select"
        self._columns = "*"
        self._count_mode: Optional[str] = None
        self._filters: list[tuple[str, str, Any]] = []
        self._order: list[tuple[str, bool]] = []
        self._limit: Optional[int] = None
        self._offset: int = 0
        self._payload: Any = None
        self._on_conflict: Optional[str] = None
        self._update_set: Optional[dict] = None

    # ---- mode-setters ----
    def select(self, columns: str = "*", count: Optional[str] = None) -> "_Query":
        self._mode = "select"
        self._columns = columns
        self._count_mode = count
        return self

    def insert(self, payload) -> "_Query":
        self._mode = "insert"
        self._payload = payload if isinstance(payload, list) else [payload]
        return self

    def upsert(self, payload, on_conflict: Optional[str] = None) -> "_Query":
        self._mode = "upsert"
        self._payload = payload if isinstance(payload, list) else [payload]
        self._on_conflict = on_conflict
        return self

    def update(self, payload: dict) -> "_Query":
        self._mode = "update"
        self._update_set = payload
        return self

    def delete(self) -> "_Query":
        self._mode = "delete"
        return self

    # ---- filters ----
    def eq(self, col: str, val: Any) -> "_Query":
        self._filters.append((col, "=", val)); return self

    def gte(self, col: str, val: Any) -> "_Query":
        self._filters.append((col, ">=", val)); return self

    def lte(self, col: str, val: Any) -> "_Query":
        self._filters.append((col, "<=", val)); return self

    def in_(self, col: str, vals: Iterable) -> "_Query":
        self._filters.append((col, "IN", tuple(vals))); return self

    # ---- ordering / paging ----
    def order(self, col: str, desc: bool = False) -> "_Query":
        self._order.append((col, desc)); return self

    def limit(self, n: int) -> "_Query":
        self._limit = n; return self

    def range(self, start: int, end: int) -> "_Query":
        """PostgREST-stijl: inclusive range, dus offset=start, limit=end-start+1."""
        self._offset = int(start)
        self._limit = int(end) - int(start) + 1
        return self

    # ---- execute ----
    def _build_where(self, params: list) -> str:
        if not self._filters:
            return ""
        parts = []
        for col, op, val in self._filters:
            if op == "IN":
                if not val:
                    parts.append("FALSE")  # IN () is altijd false
                else:
                    placeholders = ", ".join(["%s"] * len(val))
                    parts.append(f"{_quote_ident(col)} IN ({placeholders})")
                    params.extend(val)
            else:
                parts.append(f"{_quote_ident(col)} {op} %s")
                params.append(val)
        return " WHERE " + " AND ".join(parts)

    def execute(self) -> _Response:
        conn = self._client._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if self._mode == "select":
                    return self._do_select(conn, cur)
                if self._mode == "insert":
                    return self._do_insert(conn, cur)
                if self._mode == "upsert":
                    return self._do_upsert(conn, cur)
                if self._mode == "update":
                    return self._do_update(conn, cur)
                if self._mode == "delete":
                    return self._do_delete(conn, cur)
                raise ValueError(f"Onbekende mode: {self._mode}")
        finally:
            if self._client._autoclose:
                conn.close()

    # ----- SELECT -----
    def _do_select(self, conn, cur) -> _Response:
        params: list = []
        sql = f"SELECT {_quote_columns(self._columns)} FROM {_quote_ident(self._table)}"
        sql += self._build_where(params)
        if self._order:
            order_parts = [f"{_quote_ident(c)} {'DESC' if d else 'ASC'}" for c, d in self._order]
            sql += " ORDER BY " + ", ".join(order_parts)
        if self._limit is not None:
            sql += f" LIMIT {int(self._limit)}"
        if self._offset:
            sql += f" OFFSET {int(self._offset)}"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

        count = None
        if self._count_mode == "exact":
            # Aparte COUNT(*) query met dezelfde WHERE
            cparams: list = []
            csql = f'SELECT COUNT(*) AS n FROM {_quote_ident(self._table)}' + self._build_where(cparams)
            cur.execute(csql, cparams)
            count = cur.fetchone()["n"]
        return _Response(rows, count)

    # ----- INSERT -----
    def _do_insert(self, conn, cur) -> _Response:
        if not self._payload:
            return _Response([])
        cols = list(self._payload[0].keys())
        col_sql = ", ".join(_quote_ident(c) for c in cols)
        placeholders = ", ".join(["(" + ", ".join(["%s"] * len(cols)) + ")"] * len(self._payload))
        params: list = []
        for row in self._payload:
            for c in cols:
                params.append(row.get(c))
        sql = (f"INSERT INTO {_quote_ident(self._table)} ({col_sql}) "
               f"VALUES {placeholders} RETURNING *")
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return _Response(rows)

    # ----- UPSERT -----
    def _do_upsert(self, conn, cur) -> _Response:
        if not self._payload:
            return _Response([])
        cols = list(self._payload[0].keys())
        col_sql = ", ".join(_quote_ident(c) for c in cols)
        placeholders = ", ".join(["(" + ", ".join(["%s"] * len(cols)) + ")"] * len(self._payload))
        params: list = []
        for row in self._payload:
            for c in cols:
                params.append(row.get(c))

        conflict = self._on_conflict or "ID"
        conflict_cols = ", ".join(_quote_ident(c.strip()) for c in conflict.split(","))
        update_set = ", ".join(
            f"{_quote_ident(c)} = EXCLUDED.{_quote_ident(c)}"
            for c in cols if c not in conflict.split(",")
        )

        sql = (f"INSERT INTO {_quote_ident(self._table)} ({col_sql}) "
               f"VALUES {placeholders} "
               f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set} "
               f"RETURNING *")
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return _Response(rows)

    # ----- UPDATE -----
    def _do_update(self, conn, cur) -> _Response:
        if not self._update_set:
            return _Response([])
        set_parts = []
        params: list = []
        for c, v in self._update_set.items():
            set_parts.append(f"{_quote_ident(c)} = %s")
            params.append(v)
        sql = f"UPDATE {_quote_ident(self._table)} SET " + ", ".join(set_parts)
        sql += self._build_where(params)
        sql += " RETURNING *"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return _Response(rows)

    # ----- DELETE -----
    def _do_delete(self, conn, cur) -> _Response:
        params: list = []
        sql = f"DELETE FROM {_quote_ident(self._table)}" + self._build_where(params) + " RETURNING *"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return _Response(rows)


class Client:
    """Drop-in vervanging voor de .table()-stijl client.
    Per call (.execute) wordt een verse psycopg2 connectie geopend en
    daarna gesloten. Voor de schaal van Energy-Truth (kleine batches)
    is dat ruim voldoende; voor latere optimalisatie kan een pool."""

    def __init__(self, autoclose: bool = True):
        self._autoclose = autoclose

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def _conn(self):
        return get_connection()


def get_client() -> Client:
    """Backwards-compatibel: bestaande modules blijven get_client() roepen."""
    return Client()
