"""
Tests de B.1 — indexation + recherche, aucune clé API nécessaire.
Prérequis : avoir lancé `python scripts/index_catalog.py` au moins une fois.
"""
from app.tools.search_product_tool import search_product


def test_search_returns_results():
    result = search_product("quelque chose pour boire du café chaud")
    assert "produits_trouves" in result
    assert len(result["produits_trouves"]) > 0


def test_search_finds_relevant_product():
    """Vérifie que la recherche sémantique trouve un produit pertinent, pas juste n'importe quoi."""
    result = search_product("un vêtement noir à porter en hiver")
    noms = [p["nom"].lower() for p in result["produits_trouves"]]
    # On s'attend à voir le sweat à capuche ou un t-shirt noir dans les meilleurs résultats
    assert any("sweat" in nom or "noir" in nom for nom in noms)


def test_search_result_has_expected_fields():
    result = search_product("carnet pour écrire", k=1)
    produit = result["produits_trouves"][0]
    assert "id" in produit
    assert "nom" in produit
    assert "prix" in produit
    assert "score_similarite" in produit
