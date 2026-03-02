"""Client API pour PerfectDraft Pro."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://api.perfectdraft.com"
API_KEY = "cAyzERqthCJXYVExjNAhr9CzE8ncLN2cQK3WGK10"

# AWS Cognito — authentification directe, sans captcha
COGNITO_ENDPOINT = "https://cognito-idp.eu-west-1.amazonaws.com/"
COGNITO_CLIENT_ID = "glmv1olrsekstlg7se10nvmis"
COGNITO_USER_POOL = "eu-west-1_UXWVyvlHR"

DEVICE_ID = "ha-perfectdraft-integration"


class PerfectDraftAuthError(Exception):
    """Erreur d'authentification (identifiants invalides, token expiré…)."""


class PerfectDraftApiError(Exception):
    """Erreur lors d'un appel à l'API PerfectDraft."""


class PerfectDraftClient:
    """Client HTTP pour l'API PerfectDraft Pro.

    Flux d'authentification :
      1. authenticate(email, password) → appel direct Cognito USER_PASSWORD_AUTH
         → pas de captcha, pas de dépendance à l'app PerfectDraft
      2. Chaque heure : refresh_tokens() → Cognito REFRESH_TOKEN_AUTH
      3. Si le refresh token est expiré (~30 jours) : re-auth avec email/password
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0
        # Stockés pour re-auth automatique si refresh token expiré
        self._email: str | None = None
        self._password: str | None = None

    # ------------------------------------------------------------------ #
    # Authentification                                                      #
    # ------------------------------------------------------------------ #

    async def authenticate(self, email: str, password: str) -> None:
        """Authentification initiale via AWS Cognito USER_PASSWORD_AUTH.

        Avantages :
        - Aucun captcha requis (on contourne l'endpoint PerfectDraft)
        - Retourne access_token + refresh_token
        - Compatible avec le flux de refresh automatique
        """
        self._email = email
        self._password = password

        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        }
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {
                "USERNAME": email,
                "PASSWORD": password,
            },
            "ClientId": COGNITO_CLIENT_ID,
        }

        async with self._session.post(
            COGNITO_ENDPOINT, json=payload, headers=headers
        ) as resp:
            data = await resp.json(content_type=None)

            if resp.status != 200:
                error_type = data.get("__type", "")
                if error_type in ("NotAuthorizedException", "UserNotFoundException"):
                    raise PerfectDraftAuthError("Email ou mot de passe incorrect")
                raise PerfectDraftAuthError(
                    f"Erreur Cognito ({resp.status}): {data.get('message', error_type)}"
                )

        auth = data.get("AuthenticationResult", {})
        self._access_token = auth["AccessToken"]
        self._refresh_token = auth["RefreshToken"]
        self._token_expiry = time.time() + auth.get("ExpiresIn", 3600) - 60
        _LOGGER.debug("Authentification Cognito réussie pour %s", email)

    async def refresh_tokens(self) -> None:
        """Renouveler l'access token via Cognito REFRESH_TOKEN_AUTH.

        Ne nécessite ni mot de passe ni captcha.
        Si le refresh token est expiré, re-authentifie avec email/password.
        """
        if not self._refresh_token:
            raise PerfectDraftAuthError("Pas de refresh token disponible")

        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        }
        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "AuthParameters": {"REFRESH_TOKEN": self._refresh_token},
            "ClientId": COGNITO_CLIENT_ID,
        }

        async with self._session.post(
            COGNITO_ENDPOINT, json=payload, headers=headers
        ) as resp:
            data = await resp.json(content_type=None)

            if resp.status == 400 and data.get("__type") == "NotAuthorizedException":
                # Refresh token expiré → re-auth complète avec les credentials stockés
                _LOGGER.info("Refresh token expiré, re-authentification en cours…")
                if self._email and self._password:
                    await self.authenticate(self._email, self._password)
                    return
                raise PerfectDraftAuthError(
                    "Session expirée. Veuillez reconfigurer l'intégration."
                )

            if resp.status != 200:
                raise PerfectDraftAuthError(
                    f"Impossible de renouveler le token ({resp.status})"
                )

        auth = data.get("AuthenticationResult", {})
        self._access_token = auth["AccessToken"]
        # Le refresh token n'est pas retourné lors du refresh → on conserve l'ancien
        self._token_expiry = time.time() + auth.get("ExpiresIn", 3600) - 60
        _LOGGER.debug("Token Cognito renouvelé avec succès")

    async def _ensure_token(self) -> None:
        """Garantir que l'access token est valide avant chaque appel API."""
        if time.time() >= self._token_expiry:
            await self.refresh_tokens()

    # ------------------------------------------------------------------ #
    # Headers                                                               #
    # ------------------------------------------------------------------ #

    def _base_headers(self) -> dict[str, str]:
        return {
            "User-Agent": "PerfectDraft/HA-Integration CFNetwork/HomeAssistant",
            "x-app-device-id": DEVICE_ID,
            "x-app-installation-id": DEVICE_ID,
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
            headers=self._bearer_headers(),
        ) as resp:
            if resp.status != 200:
                raise PerfectDraftApiError(f"Erreur settings: {resp.status}")
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
        email: str,
        password: str,
        access_token: str,
        refresh_token: str,
        token_expiry: float,
    ) -> None:
        """Restaurer une session depuis le stockage HA au redémarrage."""
        self._email = email
        self._password = password
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        return self._refresh_token

    @property
    def token_expiry(self) -> float:
        return self._token_expiry
