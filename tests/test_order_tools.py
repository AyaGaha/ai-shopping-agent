"""
Tests de B.2 (WooCommerce) -- aucune boutique reelle necessaire : tout est mocke.

Comme pour la version Shopify precedente, on valide notre logique (construction
de requete, gestion des erreurs, retry/backoff) -- pas la disponibilite reelle
de WooCommerce, que seule ta VM peut confirmer.
"""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.tools.order_tools import confirm_order, create_order
from app.woocommerce_client import WooCommerceRequestError, WooCommerceTransientError, get


def _fake_response(status_code=200, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = str(json_data)
    return resp


@patch("app.woocommerce_client._auth", return_value=("ck_fake", "cs_fake"))
@patch("app.woocommerce_client._base_url", return_value="http://fake-vm/wp-json/wc/v3")
class TestCreateOrder:
    @patch("app.woocommerce_client.httpx.post")
    def test_create_order_success(self, mock_post, *_):
        mock_post.return_value = _fake_response(201, {"id": 42, "total": "19.90", "status": "pending"})
        result = create_order(product_id=7, quantity=1)
        assert result["order_id"] == 42
        assert result["statut"] == "commande_creee_en_attente_de_confirmation"

    @patch("app.woocommerce_client.httpx.post")
    def test_create_order_invalid_product_not_retried(self, mock_post, *_):
        """Une erreur de validation (produit inexistant) ne doit pas declencher de retry."""
        mock_post.return_value = _fake_response(400, {"message": "Invalid product ID"})
        with pytest.raises(WooCommerceRequestError):
            create_order(product_id=999999, quantity=1)
        assert mock_post.call_count == 1


@patch("app.woocommerce_client._auth", return_value=("ck_fake", "cs_fake"))
@patch("app.woocommerce_client._base_url", return_value="http://fake-vm/wp-json/wc/v3")
class TestRetryBackoff:
    @patch("app.woocommerce_client.httpx.get")
    def test_retries_on_server_error_then_succeeds(self, mock_get, *_):
        mock_get.side_effect = [
            _fake_response(503),
            _fake_response(503),
            _fake_response(200, {"ok": True}),
        ]
        result = get("products")
        assert result == {"ok": True}
        assert mock_get.call_count == 3

    @patch("app.woocommerce_client.httpx.get")
    def test_gives_up_after_max_attempts(self, mock_get, *_):
        mock_get.return_value = _fake_response(503)
        with pytest.raises(WooCommerceTransientError):
            get("products")
        assert mock_get.call_count == 3


@patch("app.woocommerce_client._auth", return_value=("ck_fake", "cs_fake"))
@patch("app.woocommerce_client._base_url", return_value="http://fake-vm/wp-json/wc/v3")
class TestConfirmOrder:
    @patch("app.woocommerce_client.httpx.put")
    def test_confirm_order_success(self, mock_put, *_):
        mock_put.return_value = _fake_response(200, {"id": 42, "status": "processing"})
        result = confirm_order(order_id=42)
        assert result["statut"] == "commande_confirmee"
        assert result["statut_woocommerce"] == "processing"
