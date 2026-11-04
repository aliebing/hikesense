-- Guest keys are now an HMAC of the IP (HIKESENSE_GUEST_SALT), never the address itself. Rows from
-- before stored the plain IP; they only count for 24 h, so they are simply dropped.
delete from guest_requests;
comment on column guest_requests.key is
  'HMAC-SHA256 (HIKESENSE_GUEST_SALT) of the IPv4 address or IPv6 /64, first 32 hex characters';
