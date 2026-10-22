"""Pure deterministic text rules shared by runtime guardrails and evaluation."""
import re
import unicodedata

CONFIRMATION_PHRASES = {
    "oui",
    "oui je confirme",
    "oui je confirme la commande",
    "je confirme",
    "je confirme la commande",
    "confirme",
    "je valide",
    "je valide la commande",
    "valide",
    "vas y",
    "allez y",
    "d accord",
    "ok",
    "okay",
    "c est bon",
    "je le prends",
    "yes",
    "yes please",
    "i confirm",
    "i confirm the order",
    "confirm",
    "go ahead",
    "go ahead with the order",
    "i approve",
    "place the order",
    "do it",
}

CANCELLATION_PHRASES = {
    "annule",
    "annule la commande",
    "je veux annuler",
    "je veux annuler la commande",
    "cancel",
    "cancel the order",
    "i want to cancel",
    "i want to cancel the order",
}

INJECTION_PATTERNS = (
    re.compile(r"\bignore (?:all )?(?:the )?(?:previous|preceding|above) instructions\b"),
    re.compile(r"\bdisregard (?:all )?(?:the )?(?:previous|preceding|above) instructions\b"),
    re.compile(r"\bignore (?:toutes? )?(?:les )?instructions? precedentes\b"),
    re.compile(r"\bignore (?:toutes? )?(?:les )?regles\b"),
    re.compile(r"\b(reveal|show|print) (?:the )?(?:system )?prompt\b"),
    re.compile(r"\b(revele|affiche|montre) (?:le )?prompt systeme\b"),
)

# Short, explicit advice requests should not be left to the model's interpretation
# of an earlier assistant quote. Keep this deliberately small and deterministic.
PRODUCT_ADVICE_PATTERNS = (
    re.compile(r"\bconseil(?:le(?: moi| nous)?|lez moi)?\b"),
    re.compile(r"\brecommand(?:e|er|ez|ation|ations)(?: moi| nous)?\b"),
    re.compile(r"\bque me conseilles tu\b"),
    re.compile(r"\bwhat do you recommend\b"),
    re.compile(r"\bcan you recommend\b"),
    re.compile(r"\bi need advice\b"),
    re.compile(r"\bany suggestions\b"),
    re.compile(r"\bi am not sure what to choose\b"),
    re.compile(r"\bi don't know what to choose\b"),
)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w\s]", " ", normalized).split())


def has_explicit_confirmation(message: str) -> bool:
    return normalize_text(message) in CONFIRMATION_PHRASES


def has_explicit_cancellation(message: str) -> bool:
    return normalize_text(message) in CANCELLATION_PHRASES


def contains_prompt_injection(message: str) -> bool:
    normalized = normalize_text(message)
    return any(pattern.search(normalized) for pattern in INJECTION_PATTERNS)


def is_product_advice_request(message: str) -> bool:
    """Recognize concise FR/EN advice requests that require catalog grounding."""
    normalized = normalize_text(message)
    return any(pattern.search(normalized) for pattern in PRODUCT_ADVICE_PATTERNS)
