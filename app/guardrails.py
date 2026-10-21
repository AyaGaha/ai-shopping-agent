"""Deterministic order controls applied before any WooCommerce order operation."""
from decimal import Decimal, InvalidOperation

from app.conversation_memory import ConversationMemory
from app.guardrail_rules import (
    contains_prompt_injection,
    has_explicit_cancellation,
    has_explicit_confirmation,
)
from app.tools.order_tools import cancel_order, confirm_order, create_order
from app.woocommerce_client import WooCommerceRequestError, get

MAX_ORDER_QUANTITY = 5
MAX_CONFIRMED_ORDERS_PER_CONVERSATION = 3

class GuardrailError(Exception):
    """A deterministic policy refused an unsafe order operation."""


class GuardrailFilter:
    def __init__(self, memory: ConversationMemory, conversation_id: str, user_message: str):
        self.memory = memory
        self.conversation_id = conversation_id
        self.user_message = user_message

    def handle(self, tool_name: str, args: dict) -> dict:
        if contains_prompt_injection(self.user_message):
            raise GuardrailError("Action bloquée : la demande contient une instruction non autorisée.")
        if tool_name == "propose_order":
            return self._propose_order(args)
        if tool_name == "create_order":
            return self._create_order(args)
        if tool_name == "confirm_order":
            return self._confirm_order(args)
        if tool_name == "cancel_order":
            return self._cancel_order(args)
        raise GuardrailError(f"Outil de commande non autorisé : {tool_name}")

    def _propose_order(self, args: dict) -> dict:
        product_id = self._positive_integer(args.get("product_id"), "product_id")
        quantity = self._positive_integer(args.get("quantity"), "quantity")
        if quantity > MAX_ORDER_QUANTITY:
            raise GuardrailError(f"La quantité maximale par commande est {MAX_ORDER_QUANTITY}.")
        state = self._load_state()
        if state["confirmed_count"] >= MAX_CONFIRMED_ORDERS_PER_CONVERSATION:
            raise GuardrailError("La limite de commandes confirmées pour cette conversation est atteinte.")
        if state["pending_order"] is not None and state["pending_order"]["status"] != "proposed":
            raise GuardrailError("Une proposition ou une commande est déjà en cours.")

        product = get(f"products/{product_id}")
        if not isinstance(product, dict) or product.get("id") != product_id:
            raise GuardrailError("Produit WooCommerce introuvable.")
        if product.get("status") != "publish" or product.get("purchasable") is not True:
            raise GuardrailError("Ce produit n'est pas disponible à la vente.")
        if product.get("stock_status") != "instock":
            raise GuardrailError("Ce produit est en rupture de stock.")
        if product.get("manage_stock"):
            stock_quantity = product.get("stock_quantity")
            if (
                isinstance(stock_quantity, bool)
                or not isinstance(stock_quantity, int)
                or quantity > stock_quantity
            ):
                raise GuardrailError("La quantité demandée dépasse le stock disponible.")

        try:
            unit_price = Decimal(str(product["price"]))
        except (KeyError, InvalidOperation, TypeError) as error:
            raise GuardrailError("Le prix WooCommerce du produit est invalide.") from error
        if not unit_price.is_finite() or unit_price <= 0:
            raise GuardrailError("Le prix WooCommerce du produit est invalide.")

        currency_response = get("data/currencies/current")
        currency = currency_response.get("code") if isinstance(currency_response, dict) else None
        if not isinstance(currency, str) or not currency.strip():
            raise GuardrailError("La devise de la boutique est indisponible.")

        proposal = {
            "product_id": product_id,
            "product_name": product["name"],
            "quantity": quantity,
            "unit_price": str(unit_price),
            "total": str(unit_price * quantity),
            "currency": currency.strip(),
            "status": "proposed",
            "order_id": None,
        }

        def save_proposal(state: dict) -> dict:
            if state["confirmed_count"] >= MAX_CONFIRMED_ORDERS_PER_CONVERSATION:
                raise GuardrailError("La limite de commandes confirmées pour cette conversation est atteinte.")
            if state["pending_order"] is not None and state["pending_order"]["status"] != "proposed":
                raise GuardrailError("Une proposition ou une commande est déjà en cours.")
            return {**state, "pending_order": proposal}

        self.memory.update_order_state(self.conversation_id, save_proposal)
        return {**proposal, "status": "proposal_ready"}

    def _create_order(self, args: dict) -> dict:
        if not has_explicit_confirmation(self.user_message):
            raise GuardrailError("Commande refusée : une confirmation explicite est requise dans le dernier message.")
        product_id = self._positive_integer(args.get("product_id"), "product_id")
        quantity = self._positive_integer(args.get("quantity"), "quantity")

        state = self._load_state()
        proposal = state["pending_order"]
        if proposal is None or proposal["status"] != "proposed":
            raise GuardrailError("Aucune proposition en attente de confirmation.")
        if (
            product_id != proposal["product_id"]
            or quantity != proposal["quantity"]
        ):
            raise GuardrailError("Les paramètres ne correspondent pas à la proposition enregistrée.")
        if state["confirmed_count"] >= MAX_CONFIRMED_ORDERS_PER_CONVERSATION:
            raise GuardrailError("La limite de commandes confirmées pour cette conversation est atteinte.")

        self._set_pending_status("proposed", "creating")
        try:
            result = create_order(proposal["product_id"], proposal["quantity"])
        except WooCommerceRequestError:
            self._set_pending_status("creating", "proposed")
            raise
        except Exception:
            self._set_pending_status("creating", "creation_unknown")
            raise

        self._store_created_order(result["order_id"])
        try:
            total_matches = Decimal(str(result.get("total"))) == Decimal(proposal["total"])
        except InvalidOperation as error:
            raise GuardrailError(
                "WooCommerce a créé une commande en attente, mais son total n'a pas pu être vérifié. "
                "Elle n'a pas été confirmée; vérifie-la dans WooCommerce."
            ) from error

        if not total_matches or result.get("devise") != proposal["currency"]:
            try:
                cancellation = cancel_order(result["order_id"])
            except Exception as error:
                raise GuardrailError(
                    "Le prix ou la devise ont changé; la commande n'a pas été confirmée "
                    "et son annulation automatique a échoué. Contacte le support."
                ) from error
            if cancellation:
                self._clear_pending_order("created", result["order_id"])
            raise GuardrailError(
                "Le prix ou la devise ont changé depuis la proposition. "
                "La commande a été annulée; demande un nouveau récapitulatif."
            )

        return result

    def _store_created_order(self, order_id: int) -> None:
        def mark_created(current: dict) -> dict:
            order = current["pending_order"]
            if order is None or order["status"] != "creating":
                raise GuardrailError("État de commande modifié pendant la création.")
            return {
                **current,
                "pending_order": {
                    **order,
                    "status": "created",
                    "order_id": order_id,
                },
            }

        self.memory.update_order_state(self.conversation_id, mark_created)

    def _confirm_order(self, args: dict) -> dict:
        if not has_explicit_confirmation(self.user_message):
            raise GuardrailError("Confirmation refusée : le dernier message doit confirmer explicitement la commande.")
        order_id = self._positive_integer(args.get("order_id"), "order_id")
        state = self._load_state()
        proposal = state["pending_order"]
        if proposal is None or proposal["status"] != "created" or proposal["order_id"] != order_id:
            raise GuardrailError("Cette commande ne correspond pas à une commande en attente de confirmation.")
        if state["confirmed_count"] >= MAX_CONFIRMED_ORDERS_PER_CONVERSATION:
            raise GuardrailError("La limite de commandes confirmées pour cette conversation est atteinte.")

        self._set_pending_status("created", "confirming")
        try:
            result = confirm_order(order_id)
        except Exception:
            self._set_pending_status("confirming", "created")
            raise

        def mark_confirmed(current: dict) -> dict:
            order = current["pending_order"]
            if order is None or order["status"] != "confirming" or order["order_id"] != order_id:
                raise GuardrailError("État de commande modifié pendant la confirmation.")
            return {
                **current,
                "confirmed_count": current["confirmed_count"] + 1,
                "pending_order": None,
            }

        self.memory.update_order_state(self.conversation_id, mark_confirmed)
        return result

    def _cancel_order(self, args: dict) -> dict:
        if not has_explicit_cancellation(self.user_message):
            raise GuardrailError("Annulation refusée : une demande explicite est requise dans le dernier message.")
        order_id = self._positive_integer(args.get("order_id"), "order_id")
        state = self._load_state()
        proposal = state["pending_order"]
        if proposal is None or proposal["status"] != "created" or proposal["order_id"] != order_id:
            raise GuardrailError("Cette commande n'est pas une commande en attente créée par cette conversation.")

        self._set_pending_status("created", "cancelling")
        try:
            result = cancel_order(order_id)
        except Exception:
            self._set_pending_status("cancelling", "created")
            raise

        def clear_cancelled(current: dict) -> dict:
            order = current["pending_order"]
            if order is None or order["status"] != "cancelling" or order["order_id"] != order_id:
                raise GuardrailError("État de commande modifié pendant l'annulation.")
            return {**current, "pending_order": None}

        self.memory.update_order_state(self.conversation_id, clear_cancelled)
        return result

    def _clear_pending_order(self, expected_status: str, order_id: int) -> None:
        def clear(current: dict) -> dict:
            order = current["pending_order"]
            if order is None or order["status"] != expected_status or order["order_id"] != order_id:
                raise GuardrailError("État de commande modifié avant son annulation.")
            return {**current, "pending_order": None}

        self.memory.update_order_state(self.conversation_id, clear)

    def _set_pending_status(self, expected: str, new_status: str) -> None:
        def update(state: dict) -> dict:
            proposal = state["pending_order"]
            if proposal is None or proposal["status"] != expected:
                raise GuardrailError("La commande a déjà été traitée ou son état est invalide.")
            return {**state, "pending_order": {**proposal, "status": new_status}}

        self.memory.update_order_state(self.conversation_id, update)

    def _load_state(self) -> dict:
        state = self.memory.load_order_state(self.conversation_id)
        return state or {"confirmed_count": 0, "pending_order": None}

    @staticmethod
    def _positive_integer(value: object, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise GuardrailError(f"{field} doit être un entier positif.")
        return value
