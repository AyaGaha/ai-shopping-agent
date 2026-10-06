"""
Client WooCommerce REST API — remplace shopify_client.py.

Auth beaucoup plus simple que Shopify : Basic Auth avec consumer_key/secret,
pas d'OAuth, pas de distinction Partner App vs Custom App. Un seul fichier à
connaître pour parler à l'API ; order_tools.py ne voit que cette interface.

Même pattern de résilience que pour Shopify : retry avec backoff exponentiel
(3 tentatives, 1s/2s/4s) uniquement sur les erreurs transitoires — jamais sur
une erreur de requête mal formée.
"""
import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class WooCommerceTransientError(Exception):
    """Erreur réseau/serveur temporaire — justifie un retry."""


class WooCommerceRequestError(Exception):
    """Erreur de requête (4xx, validation WooCommerce) — ne pas réessayer."""


def _base_url() -> str:
    url = os.environ.get("WOOCOMMERCE_URL")
    if not url:
        raise RuntimeError("WOOCOMMERCE_URL manquante dans .env (ex: http://<ip-vm>/wp-json/wc/v3)")
    return url.rstrip("/")


def _auth() -> tuple[str, str]:
    key = os.environ.get("WOOCOMMERCE_CONSUMER_KEY")
    secret = os.environ.get("WOOCOMMERCE_CONSUMER_SECRET")
    if not key or not secret:
        raise RuntimeError("WOOCOMMERCE_CONSUMER_KEY / WOOCOMMERCE_CONSUMER_SECRET manquantes dans .env")
    return key, secret


def _handle_response(response: httpx.Response) -> dict | list:
    if response.status_code >= 500:
        raise WooCommerceTransientError(f"Erreur serveur WooCommerce: {response.status_code}")
    if response.status_code == 429:
        raise WooCommerceTransientError("Rate limit WooCommerce atteint")
    if response.status_code >= 400:
        raise WooCommerceRequestError(f"Requête invalide: {response.status_code} — {response.text}")
    return response.json()


@retry(
    retry=retry_if_exception_type(WooCommerceTransientError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),  # 1s, 2s, 4s
    reraise=True,
)
def get(path: str, params: dict | None = None) -> dict | list:
    url = f"{_base_url()}/{path.lstrip('/')}"
    try:
        response = httpx.get(url, params=params, auth=_auth(), timeout=10.0)
    except httpx.TransportError as e:
        raise WooCommerceTransientError(f"Erreur réseau: {e}") from e
    return _handle_response(response)


@retry(
    retry=retry_if_exception_type(WooCommerceTransientError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def post(path: str, json_body: dict) -> dict:
    url = f"{_base_url()}/{path.lstrip('/')}"
    try:
        response = httpx.post(url, json=json_body, auth=_auth(), timeout=10.0)
    except httpx.TransportError as e:
        raise WooCommerceTransientError(f"Erreur réseau: {e}") from e
    return _handle_response(response)


@retry(
    retry=retry_if_exception_type(WooCommerceTransientError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def put(path: str, json_body: dict) -> dict:
    url = f"{_base_url()}/{path.lstrip('/')}"
    try:
        response = httpx.put(url, json=json_body, auth=_auth(), timeout=10.0)
    except httpx.TransportError as e:
        raise WooCommerceTransientError(f"Erreur réseau: {e}") from e
    return _handle_response(response)
