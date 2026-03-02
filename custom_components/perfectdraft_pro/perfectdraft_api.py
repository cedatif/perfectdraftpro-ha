"""Client API pour PerfectDraft Pro."""
from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://api.perfectdraft.com"
API_KEY = "cAyzERqthCJXYVExjNAhr9CzE8ncLN2cQK3WGK10"
DEVICE_ID = "ha-perfectdraft-integration"


class PerfectDraftAuthError(Exception):
    """Erreur d'authentification (token expiré, refresh impossible…)."""


class PerfectDraftApiError(Exception):
    """Erreur lors d'un appel à l'API PerfectDraft."""


class PerfectDraftClient:
    """Client HTTP pour l'API PerfectDraft Pro.

    Flux d'authentification :
      1. restore_session() → restaure les tokens au démarrage HA
      2. Chaque heure : refresh_tokens() → POST /lager-top/auth/renewaccesstokens
         (pas de reCAPTCHA, pas de Cognito direct)
      3. Si le refresh token est expiré (~30 jours) : erreur → reconfigurer via proxy
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0
        self._machine_id: int | None = None

    # ------------------------------------------------------------------ #
    # Authentification                                                      #
    # ------------------------------------------------------------------ #

    async def refresh_tokens(self) -> None:
        """Renouveler l'access token via POST /lager-top/auth/renewaccesstokens.

        Ne nécessite ni mot de passe ni reCAPTCHA.
        Si le refresh token est expiré (~30 jours), lève PerfectDraftAuthError.
        """
        if not self._refresh_token:
            raise PerfectDraftAuthError("Pas de refresh token disponible")

        user_id = self._extract_user_id()
        if not user_id:
            raise PerfectDraftAuthError("Impossible d'extraire le userId du token JWT")

        headers = {
            **self._base_headers(),
            "x-access-token": self._access_token or "",
            "x-api-key": API_KEY,
        }

        async with self._session.post(
            f"{API_BASE}/lager-top/auth/renewaccesstokens",
            json={"refreshToken": self._refresh_token, "userId": user_id},
            headers=headers,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                _LOGGER.error("Échec du refresh token (%s): %s", resp.status, text)
                raise PerfectDraftAuthError(
                    "Session expirée. Veuillez reconfigurer l'intégration "
                    "(recapturer les tokens via le proxy)."
                )
            data = await resp.json(content_type=None)

        self._access_token = data["accessToken"]
        # Le refreshToken n'est pas renouvelé → on conserve l'ancien
        self._token_expiry = time.time() + data.get("expiresIn", 3600) - 60
        _LOGGER.debug("Access token renouvelé via PerfectDraft API")

    async def _ensure_token(self) -> None:
        """Garantir que l'access token est valide avant chaque appel API."""
        if time.time() >= self._token_expiry:
            await self.refresh_tokens()

    def _extract_user_id(self) -> str | None:
        """Extraire le 'sub' (userId Cognito) depuis le payload JWT de l'access token."""
        if not self._access_token:
            return None
        try:
            payload_b64 = self._access_token.split(".")[1]
            # Ajouter le padding base64 manquant
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.b64decode(payload_b64))
            return payload.get("sub") or payload.get("username")
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Headers                                                               #
    # ------------------------------------------------------------------ #

    def _base_headers(self) -> dict[str, str]:
        device = str(self._machine_id) if self._machine_id else DEVICE_ID
        return {
            "User-Agent": "PerfectDraft/1770399265 CFNetwork/3860.400.51 Darwin/25.3.0",
            "x-app-device-id": device,
            "x-app-installation-id": device,
            "x-correlation-id": str(uuid.uuid4()),
            "Accept": "application/json",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }

    def _auth_headers(self) -> dict[str, str]:
        return {
            **self._base_headers(),
            "x-api-key": API_KEY,
            "x-organization": "5",
            "x-access-token": self._access_token or "",
        }

    def _bearer_headers(self) -> dict[str, str]:
        return {
            **self._base_headers(),
            "Authorization": f"Bearer {self._access_token or ''}",
        }

    # ------------------------------------------------------------------ #
    # Endpoints API                                                         #
    # ------------------------------------------------------------------ #

    async def get_me(self) -> dict[str, Any]:
        """Profil utilisateur → liste des tireuses (machine_id, device_uuid)."""
        await self._ensure_token()
        async with self._session.get(
            f"{API_BASE}/api/me", headers=self._auth_headers()
        ) as resp:
            if resp.status != 200:
                raise PerfectDraftApiError(f"Erreur /api/me: {resp.status}")
            return await resp.json(content_type=None)

    async def get_machine(self, machine_id: int) -> dict[str, Any]:
        """Données temps réel de la tireuse (température, volume, pression…)."""
        await self._ensure_token()
        async with self._session.get(
            f"{API_BASE}/api/perfectdraft_machines/{machine_id}",
            headers=self._auth_headers(),
        ) as resp:
            if resp.status != 200:
                raise PerfectDraftApiError(f"Erreur machine {machine_id}: {resp.status}")
            return await resp.json(content_type=None)

    async def get_machine_keg(self, machine_id: int) -> dict[str, Any]:
        """Fût actif actuellement en place."""
        await self._ensure_token()
        async with self._session.get(
            f"{API_BASE}/api/perfectdraft_machines/{machine_id}",
            headers=self._auth_headers(),
            params={"groups[]": "perfectdraft_keg_active_read"},
        ) as resp:
            if resp.status != 200:
                raise PerfectDraftApiError(f"Erreur keg {machine_id}: {resp.status}")
            return await resp.json(content_type=None)

    async def get_machine_settings(self, device_uuid: str) -> dict[str, Any]:
        """Réglages de la tireuse (température cible, mode…)."""
        await self._ensure_token()
        async with self._session.get(
            f"{API_BASE}/lager-top/machine/{device_uuid}/settings",
            headers={**self._bearer_headers(), "x-api-key": API_KEY},
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("Erreur settings (%s) — données ignorées", resp.status)
                return {}
            return await resp.json(content_type=None)

    async def get_rewards(self) -> dict[str, Any]:
        """Points fidélité et niveau du compte."""
        await self._ensure_token()
        async with self._session.get(
            f"{API_BASE}/odp/rewards",
            headers={**self._bearer_headers(), "locale": "fr_FR"},
        ) as resp:
            if resp.status != 200:
                return {}
            return await resp.json(content_type=None)

    async def get_product(self, product_id: int) -> dict[str, Any]:
        """Informations sur une bière (nom, description…)."""
        await self._ensure_token()
        async with self._session.get(
            f"{API_BASE}/api/products/{product_id}",
            headers=self._auth_headers(),
        ) as resp:
            if resp.status != 200:
                return {}
            return await resp.json(content_type=None)

    # ------------------------------------------------------------------ #
    # Persistence des credentials (stockage HA)                            #
    # ------------------------------------------------------------------ #

    def restore_session(
        self,
        access_token: str,
        refresh_token: str,
        token_expiry: float,
        machine_id: int | None = None,
    ) -> None:
        """Restaurer une session depuis le stockage HA au redémarrage."""
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        self._machine_id = machine_id

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def token_expiry(self) -> float:
        return self._token_expiry
