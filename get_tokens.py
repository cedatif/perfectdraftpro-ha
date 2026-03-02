#!/usr/bin/env python3
"""
Script pour obtenir les tokens PerfectDraft Pro à coller dans Home Assistant.

Installation :
    pip install requests

Usage :
    python3 get_tokens.py

Le token reCAPTCHA doit être capturé depuis l'app PerfectDraft via un proxy
(ex: mitmproxy, Charles) — c'est la valeur "recaptchaToken" envoyée lors
du login. Il est valide ~2 minutes.
"""

import sys
import requests

# ------------------------------------------------------------------ #
# Constantes PerfectDraft                                              #
# ------------------------------------------------------------------ #

API_BASE = "https://api.perfectdraft.com"
API_KEY = "cAyzERqthCJXYVExjNAhr9CzE8ncLN2cQK3WGK10"
RECAPTCHA_ACTION = "Android_recaptchaThatWorks/login"


# ------------------------------------------------------------------ #
# API PerfectDraft                                                     #
# ------------------------------------------------------------------ #

def authenticate(email: str, password: str, recaptcha_token: str) -> dict:
    import uuid
    resp = requests.post(
        f"{API_BASE}/lager-top/auth/signin",
        json={
            "email": email,
            "password": password,
        },
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "x-captcha-token": recaptcha_token,
            "x-captcha-site": "app_ios",
            "x-app-device-id": "ha-perfectdraft-integration",
            "x-app-installation-id": "ha-perfectdraft-integration",
            "x-correlation-id": str(uuid.uuid4()),
            "User-Agent": "PerfectDraft/1770399265 CFNetwork/3860.400.51 Darwin/25.3.0",
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Authentification échouée ({resp.status_code}) : {resp.text}")
    return resp.json()


def get_me(access_token: str) -> dict:
    resp = requests.get(
        f"{API_BASE}/api/me",
        headers={
            "x-api-key": API_KEY,
            "x-access-token": access_token,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Erreur /api/me ({resp.status_code}) : {resp.text}")
    return resp.json()


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main() -> None:
    print("=== PerfectDraft Pro — Obtention des tokens ===\n")
    print("Capture le token reCAPTCHA depuis l'app via un proxy (Charles/mitmproxy),")
    print("puis colle-le ci-dessous. Tu as ~2 minutes.\n")

    email = input("Email PerfectDraft  : ").strip().lower()
    password = input("Mot de passe        : ").strip()
    recaptcha_token = input("Token reCAPTCHA     : ").strip()

    print("\n[1/2] Authentification PerfectDraft...")
    try:
        auth = authenticate(email, password, recaptcha_token)
    except RuntimeError as e:
        print(f"  ERREUR : {e}")
        sys.exit(1)
    access_token = auth["AccessToken"]
    refresh_token = auth["RefreshToken"]
    print("  OK")

    print("[2/2] Récupération de la tireuse...")
    try:
        me = get_me(access_token)
    except RuntimeError as e:
        print(f"  ERREUR : {e}")
        sys.exit(1)
    machines = me.get("perfectdraftMachines", [])
    if not machines:
        print("  ERREUR : Aucune tireuse trouvée sur ce compte.")
        sys.exit(1)
    machine = machines[0]
    machine_id = machine["id"]
    device_uuid = machine["deviceId"]
    print("  OK\n")

    print("=" * 60)
    print("TOKENS À COLLER DANS HOME ASSISTANT")
    print("=" * 60)
    print(f"Email         : {email}")
    print(f"Access Token  : {access_token}")
    print(f"Refresh Token : {refresh_token}")
    print(f"Machine ID    : {machine_id}")
    print(f"Device UUID   : {device_uuid}")
    print("=" * 60)
    print("\nDans HA : Paramètres → Appareils et services → Ajouter une intégration")
    print("→ PerfectDraft Pro → 'Coller les tokens'\n")


if __name__ == "__main__":
    main()
