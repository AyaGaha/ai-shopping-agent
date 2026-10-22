<?php
// Idempotent seed importer for the demo catalog. Run through WP-CLI after WooCommerce activation.
$catalog_path = '/workspace/data/products.json';
$products = json_decode( file_get_contents( $catalog_path ), true, 512, JSON_THROW_ON_ERROR );
$created = 0;
$updated = 0;

foreach ( $products as $item ) {
	$sku = 'agent-p059-' . (string) $item['id'];
	$product_id = wc_get_product_id_by_sku( $sku );
	$product = $product_id ? wc_get_product( $product_id ) : new WC_Product_Simple();
	$product->set_name( $item['nom'] );
	$product->set_sku( $sku );
	$product->set_description( $item['description'] ?? '' );
	$product->set_regular_price( (string) $item['prix'] );
	$product->set_status( 'publish' );
	$product->set_catalog_visibility( 'visible' );
	$product->set_virtual( false );
	$product->save();
	$product_id ? $updated++ : $created++;
}

fwrite( STDOUT, wp_json_encode( array( 'created' => $created, 'updated' => $updated ) ) . "\n" );
