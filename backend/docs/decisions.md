# Journal des décisions

| Décision | Motif | Conséquence |
|---|---|---|
| Shopify remplacé par WooCommerce | Le projet a besoin d'une boutique contrôlable et de commandes testables sans dépendre du flux d'une app Shopify. | Les outils de commande utilisent WooCommerce REST et des clés Read/Write. |
| Flux de commande B : proposition, puis confirmation | Présenter un récapitulatif vérifié avant toute création évite de transformer une recherche en achat implicite. | Le serveur conserve la proposition; `create_order` exige une confirmation explicite. |
| Garde-fous déterministes en code, en plus du prompt | Les règles de prix, quantité, négation et état de commande ne doivent pas dépendre du respect du prompt par le LLM. | Les opérations sensibles sont bloquées ou autorisées côté serveur. |
| Pas de recherche forcée pour toute conversation | Une salutation ou une question générale ne nécessite pas le catalogue; une demande de conseil produit, elle, doit se baser sur les résultats de recherche. | Le modèle choisit si un outil est nécessaire; les recommandations sont limitées aux produits présents dans l'observation `search_product`. |
| `all-MiniLM-L6-v2` et le seuil `0.70` conservés | Le candidat multilingue a amélioré le rappel sur 24 cas, mais son inférence CPU a été extrêmement lente sur la VM; seulement quatre cas négatifs ont été évalués. | Le changement de modèle ou de seuil attend un jeu plus large et une mesure plus représentative. |
| Pas de retry sur la création de commande | Un timeout peut survenir après que WooCommerce a créé la commande; rejouer le POST peut créer un doublon. | Les issues incertaines sont vérifiées manuellement dans WooCommerce. |
| Reconstruire par WP-CLI et Compose | L'installation manuelle n'est pas répétable et risque de diverger d'une VM à l'autre. | `infra/provision.sh` garde la stack idempotente; les secrets ne sont pas versionnés. |
