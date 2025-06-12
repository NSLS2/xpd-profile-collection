# Make ophyd listen to pyepics.
import nslsii
import ophyd.signal
import logging
from IPython import get_ipython

ip = get_ipython()

print(f"Loading {__file__} from {ip.profile_dir.startup_dir}.")

logger = logging.getLogger("startup_profile")

from bluesky_queueserver import is_re_worker_active

ophyd.signal.EpicsSignal.set_defaults(connection_timeout=5)
# See docstring for nslsii.configure_base() for more details
# this command takes away much of the boilerplate for settting up a profile
# (such as setting up best effort callbacks etc)

nslsii.configure_base(get_ipython().user_ns, 'xpd', pbar=True, bec=True,
                      magics=True, mpl=True, epics_context=False,
                      publish_documents_with_kafka=True, redis_url="info.xpd.nsls2.bnl.gov")

del one_1d_step
del one_nd_step
del one_shot

# At the end of every run, verify that files were saved and
# print a confirmation message.
from bluesky.callbacks.broker import verify_files_saved, post_run
# RE.subscribe(post_run(verify_files_saved, db), 'stop')

# Uncomment the following lines to turn on verbose messages for
# debugging.
# import logging
# ophyd.logger.setLevel(logging.DEBUG)
# logging.basicConfig(level=logging.DEBUG)


RE.md['facility'] = 'NSLS-II'
RE.md['group'] = 'XPD'
RE.md['beamline_id'] = '28-ID-2'

import subprocess


def show_env():
    # this is not guaranteed to work as you can start IPython without hacking
    # the path via activate
    proc = subprocess.Popen(["conda", "list"], stdout=subprocess.PIPE)
    out, err = proc.communicate()
    a = out.decode('utf-8')
    b = a.split('\n')
    print(b[0].split('/')[-1][:-1])
