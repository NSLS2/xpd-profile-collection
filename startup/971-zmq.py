from bluesky.callbacks.zmq import Publisher

raw_publisher = Publisher(glbl['inbound_proxy_address'], prefix=b'raw')  # used in bsui
xrun.subscribe(raw_publisher)
raw_publisher = Publisher(glbl['inbound_proxy_address'], prefix=b'raw')  # used by bluesky-queueserver
RE.subscribe(raw_publisher)
