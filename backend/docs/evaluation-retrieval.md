# Évaluation de la recherche produit

> Rapport de mesure conservé dans le dépôt.

## Objectif

Mesurer l’effet du seuil de distance de la recherche vectorielle sur les résultats pertinents et les requêtes qui ne devraient rien retourner. Le seuil de production mesuré était `0.70`.

## Protocole

- Date de mesure : 22 octobre 2026
- Environnement : VM `agent-p059-vm`
- Jeu : `data/evaluation_cases.json`, version 2
- Recherche : distance cosinus avec `all-MiniLM-L6-v2`
- Échantillon : 24 requêtes, dont 20 positives et 4 sans résultat attendu
- Commande :

```bash
.venv/bin/python -m scripts.evaluate --only retrieval \
  --threshold 0.45 --threshold 0.50 --threshold 0.55 \
  --threshold 0.60 --threshold 0.65 --threshold 0.70
```

L’évaluation a terminé sans erreur (`error_count: 0`). La première tentative avait été interrompue pendant un import Python; les imports isolés de NumPy, ChromaDB et du module de recherche ont ensuite terminé en moins de deux secondes.

## Résultats par seuil

`hit@1` mesure la proportion de requêtes positives pour lesquelles le premier résultat est pertinent. Le taux de faux positifs est calculé sur les quatre requêtes négatives.

| Seuil maximal de distance | Hit@1 | Hit@3 | MRR | Faux positifs |
|---:|---:|---:|---:|---:|
| 0.45 | 50 % (10/20) | 50 % | 0.50 | 0 % (0/4) |
| 0.50 | 60 % (12/20) | 60 % | 0.60 | 0 % (0/4) |
| 0.55 | 60 % (12/20) | 60 % | 0.60 | 0 % (0/4) |
| 0.60 | 65 % (13/20) | 65 % | 0.65 | 50 % (2/4) |
| 0.65 | 70 % (14/20) | 70 % | 0.70 | 50 % (2/4) |
| 0.70 (production) | 75 % (15/20) | 75 % | 0.75 | 50 % (2/4) |

## Interprétation et décision

Le seuil actuel `0.70` donne le meilleur rappel parmi les seuils testés, mais retourne un résultat pour deux des quatre requêtes sans résultat attendu. Les seuils `0.50` et `0.55` ont les mêmes métriques sur cet échantillon : 60 % de hit@1 et aucun faux positif observé. `0.50` est donc un candidat prudent à tester, mais **aucun changement de seuil de production n’est décidé par ce rapport**.

Le rappel de 60 % reste faible. Les quatre requêtes négatives constituent un échantillon trop petit pour conclure que le taux de faux positifs réel est nul. Il faut élargir les cas négatifs et analyser les exemples manqués avant de figer le seuil.

## Décision modèle

Le modèle de production reste `all-MiniLM-L6-v2`, avec le seuil existant
`0.70`. Le test multilingue a montré un meilleur rappel sur ce petit jeu, mais
son coût CPU mesuré sur la VM est excessif et son taux de faux positifs est de
1/4. Aucun modèle ni seuil de production n’est modifié. Le comparatif est
conservé comme expérience terminée; le travail reprend sur la résilience LLM.

## Latence observée

| Mesure | Résultat |
|---|---:|
| Requêtes | 24 |
| Première requête à froid | 143,163 ms (environ 143 s) |
| Moyenne incluant la première requête | 6,001 ms |
| Moyenne des requêtes chaudes | 37.7 ms |
| Médiane / p95 à chaud | 8.36 ms / 11.71 ms |
| Maximum à chaud | 683.65 ms |

Le premier appel à froid domine le coût total; les recherches chaudes sont nettement plus rapides. Le journal d’exécution a aussi affiché un avertissement Hugging Face concernant l’absence de `HF_TOKEN`. L’évaluation ne permet pas à elle seule d’attribuer les 143 secondes au téléchargement, au chargement du modèle ou à une autre initialisation; il faut mesurer séparément ces phases.

## Comparaison des modèles (22 octobre 2026)

Le benchmark isolé a comparé les deux modèles sur les mêmes 9 produits et les
mêmes 24 requêtes, sans modifier l’index de production. Aucun appel n’a échoué.

| Modèle | Seuil | Hit@1 / Hit@3 | Faux positifs (4 négatives) |
|---|---:|---:|---:|
| `all-MiniLM-L6-v2` | 0.45 | 50 % | 0 % (0/4) |
| `all-MiniLM-L6-v2` | 0.50–0.55 | 60 % | 0 % (0/4) |
| `all-MiniLM-L6-v2` | 0.60 | 65 % | 50 % (2/4) |
| `all-MiniLM-L6-v2` | 0.65 | 70 % | 50 % (2/4) |
| `all-MiniLM-L6-v2` | 0.70 | 75 % | 50 % (2/4) |
| `paraphrase-multilingual-MiniLM-L12-v2` | 0.45 | 70 % | 25 % (1/4) |
| `paraphrase-multilingual-MiniLM-L12-v2` | 0.50 | 85 % | 25 % (1/4) |
| `paraphrase-multilingual-MiniLM-L12-v2` | 0.55 | 90 % | 25 % (1/4) |
| `paraphrase-multilingual-MiniLM-L12-v2` | 0.60–0.70 | 100 % | 25 % (1/4) |

Sur cet échantillon, le modèle multilingue améliore nettement le rappel. Au
seuil 0.60, il retrouve les 20 produits attendus, mais retourne aussi un
résultat pour une des quatre requêtes négatives. Quatre cas négatifs ne
suffisent pas pour valider ce taux en production; il faut augmenter cet
échantillon et inspecter le faux positif. Le seuil 0.60 est un candidat à
approfondir, pas une décision de production.

Les durées de cette première exécution du comparatif sont anormalement élevées :

| Modèle | Initialisation + indexation | Encodage + recherche du lot de 24 | Moyenne amortie par requête |
|---|---:|---:|---:|
| `all-MiniLM-L6-v2` | 621.7 s | 86.6 ms | 3.61 ms |
| `paraphrase-multilingual-MiniLM-L12-v2` | 78.5 s | 344.9 s | 14.37 s |

Ces durées justifient un diagnostic CPU avant d’en tirer une comparaison de
latence de production. Un essai séparé de trois requêtes avec un thread PyTorch
a pris 341.2 s pour initialisation/indexation puis 542.7 s pour encoder et
chercher les requêtes, soit 14 min 44 s au total. Ce résultat ne mesure pas la
qualité (trois requêtes positives seulement) et montre que la limite à un
thread n’a pas aidé dans cet environnement. Le benchmark laisse désormais
PyTorch choisir son nombre de threads par défaut, sauf si `--torch-threads`
est fourni explicitement. Ne pas relancer le modèle multilingue avant d’avoir
vérifié les ressources et la pression CPU/mémoire de la VM.

Au diagnostic système, la VM disposait de 2 vCPU et 3.8 GiB de RAM sans swap.
La pression mémoire PSI `full avg300` était de 14.19 %; elle peut contribuer
aux durées élevées. Aucun benchmark d’embeddings supplémentaire n’est prévu.

## Routage LLM mesuré séparément

Une exécution distincte de `--only tool-selection` a évalué 8 cas : exactitude `1.0` (8/8), aucune erreur, latence moyenne 896.01 ms, p50 582.58 ms et p95 3160.37 ms. Cette mesure utilise le LLM et n’est pas incluse dans l’évaluation de recherche hors ligne ci-dessus.

## Décision modèle

Le modèle de production reste `all-MiniLM-L6-v2`, avec le seuil actuel `0.70`.
Le modèle multilingue n’est pas activé : malgré son meilleur rappel mesuré, son
coût CPU sur la VM est excessif et il a retourné un produit pour une des quatre
requêtes négatives. Aucun modèle ni seuil de production n’est modifié.

## Prochaines étapes

Les cas négatifs de recherche restent à étoffer (quatre dans la version 2 du
jeu). Le travail CDC passe maintenant à la vérification de reconstruction sur
une VM neuve, puis à la répétition de l'évaluation après déploiement.

Le champ `tool_selection` de la sortie de l’évaluation hors ligne indique `not_measured`, ce qui est attendu : le routage est évalué par l’exécution LLM séparée.
