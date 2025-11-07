from bluesky.callbacks.zmq import Publisher

if is_re_worker_active():  # running in queueserver
    raw_publisher = Publisher(glbl['inbound_proxy_address'], RE=RE, prefix=b'raw')  # used by bluesky-queueserver

else:
    raw_publisher = Publisher(glbl['inbound_proxy_address'], RE=xrun, prefix=b'raw')  # used in bsui
