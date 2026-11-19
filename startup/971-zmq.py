from bluesky.callbacks.zmq import Publisher

if is_re_worker_active():  # running in queueserver
    raw_publisher = Publisher(glbl['inbound_proxy_address'], prefix=b'raw')  # used by bluesky-queueserver
    RE.subscribe(raw_publisher)

else: # running in bsui
    raw_publisher = Publisher(glbl['inbound_proxy_address'], prefix=b'raw')  # used in bsui
    xrun.subscribe(raw_publisher)
    raw_publisher = Publisher(glbl['inbound_proxy_address'], prefix=b'raw')  # used by RE in bsui
    RE.subscribe(raw_publisher)
