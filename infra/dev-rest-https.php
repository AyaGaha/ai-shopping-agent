<?php
/**
 * DEV ONLY (P059) — mu-plugin charge automatiquement par WordPress.
 *
 * WooCommerce n'accepte l'authentification par cle API (consumer key/secret)
 * que sur une connexion HTTPS. En HTTP il ignore les cles et repond
 * 401 "woocommerce_rest_cannot_view", meme avec des cles valides.
 * On declare donc HTTPS uniquement pour les requetes vers l'API REST.
 *
 * Acceptable ici car l'agent appelle WordPress via localhost sur la meme VM :
 * les cles ne circulent pas sur le reseau. A SUPPRIMER des qu'un vrai
 * certificat HTTPS est en place.
 */
if ( isset( $_SERVER['REQUEST_URI'] ) && ( false !== strpos( $_SERVER['REQUEST_URI'], '/wp-json/' ) || false !== strpos( $_SERVER['REQUEST_URI'], 'rest_route=' ) ) ) {
	$_SERVER['HTTPS'] = 'on';
}
