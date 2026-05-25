"""
db_connection.py — Veilige Supabase-verbinding voor Energy-Truth.

Laadt credentials uit .env bestand (NOOIT hardcoded in code).
Biedt een herbruikbare get_client() functie voor alle modules.

Gebruikt de service_role key (niet anon) omdat RLS aan staat.
De service_role key omzeilt RLS — veilig voor server-side scripts,
NIET gebruiken in frontend/browser code.

Setup:
    1. Kopieer .env.example naar .env
    2. Vul je Supabase URL en service_role key in
    3. Installeer dependencies: pip install supabase python-dotenv

Gebruik:
    from db_connection import get_client
    client = get_client()
    data = client.table("providers").select("*").execute()
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client


# Laad .env uit dezelfde map als dit script
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


def get_client() -> Client:
    """
    Maakt een Supabase client aan met credentials uit .env.

    Returns:
        Supabase Client object.

    Raises:
        SystemExit: als SUPABASE_URL of SUPABASE_KEY niet gevonden is.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("❌ SUPABASE_URL en/of SUPABASE_SERVICE_KEY niet gevonden!")
        print()
        print("Oplossing:")
        print("  1. Kopieer .env.example naar .env")
        print("  2. Vul je Supabase credentials in")
        print()
        print(f"  Verwacht .env bestand op: {_env_path}")
        sys.exit(1)

    return create_client(url, key)


def test_connection() -> bool:
    """
    Test de verbinding door de providers tabel op te vragen.

    Returns:
        True als de verbinding werkt, False bij een fout.
    """
    try:
        client = get_client()
        result = client.table("providers").select("*").limit(5).execute()
        print(f"✅ Verbinding met Supabase OK — {len(result.data)} provider(s) gevonden")
        if result.data:
            print(f"   Kolommen: {list(result.data[0].keys())}")
            for row in result.data:
                print(f"   → {row}")
        return True
    except Exception as e:
        print(f"❌ Verbinding mislukt: {e}")
        return False


# ---------------------------------------------------------------------------
# MAIN — Direct uitvoeren om verbinding te testen
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Supabase verbinding testen...")
    print(f".env pad: {_env_path}")
    print(f".env bestaat: {_env_path.exists()}")
    print()
    test_connection()
