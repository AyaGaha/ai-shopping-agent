from unittest.mock import MagicMock, patch

from app.tools.search_product_tool import warm_search


def test_warm_search_initializes_embeddings_with_a_read_only_query():
    collection = MagicMock()
    collection.count.return_value = 9

    with patch("app.tools.search_product_tool._get_collection", return_value=collection):
        warm_search()

    collection.query.assert_called_once_with(
        query_texts=["warmup"],
        n_results=1,
        include=["distances"],
    )


def test_warm_search_skips_query_for_an_empty_catalog():
    collection = MagicMock()
    collection.count.return_value = 0

    with patch("app.tools.search_product_tool._get_collection", return_value=collection):
        warm_search()

    collection.query.assert_not_called()
