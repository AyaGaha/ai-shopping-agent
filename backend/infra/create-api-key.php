<?php
// Create a least-privilege-scoped WooCommerce API credential for this demo app.
// Follows WooCommerce's WC_Auth key storage format; plaintext is emitted once to
// provision.sh, which stores it in an ignored 0600 file on the host.
global $wpdb;
$user = get_user_by( 'login', 'agent-p059-api' );
if ( ! $user ) {
	$user_id = wp_insert_user( array(
		'user_login' => 'agent-p059-api',
		'user_email' => 'agent-p059-api@example.invalid',
		'user_pass' => wp_generate_password( 48, true, true ),
		'role' => 'shop_manager',
	) );
	if ( is_wp_error( $user_id ) ) {
		fwrite( STDERR, "Could not create WooCommerce service user.\n" );
		exit( 1 );
	}
	$user = get_user_by( 'id', $user_id );
}
$consumer_key = 'ck_' . wc_rand_hash();
$consumer_secret = 'cs_' . wc_rand_hash();
$inserted = $wpdb->insert(
	$wpdb->prefix . 'woocommerce_api_keys',
	array(
		'user_id' => $user->ID,
		'description' => 'AI Shopping Agent P059 provisioning',
		'permissions' => 'read_write',
		'consumer_key' => wc_api_hash( $consumer_key ),
		'consumer_secret' => $consumer_secret,
		'truncated_key' => substr( $consumer_key, -7 ),
	),
	array( '%d', '%s', '%s', '%s', '%s', '%s' )
);
if ( false === $inserted ) {
	fwrite( STDERR, "WooCommerce API key creation failed.\n" );
	exit( 1 );
}
fwrite( STDOUT, wp_json_encode( array(
	'consumer_key' => $consumer_key,
	'consumer_secret' => $consumer_secret,
) ) . "\n" );
