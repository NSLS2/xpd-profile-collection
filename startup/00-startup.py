# Make ophyd listen to pyepics.
import nslsii
import ophyd.signal
import logging
import os
import time as ttime
from IPython import get_ipython
from databroker import Broker
from tiled.client import from_profile

ip = get_ipython()


print(f"Loading {__file__}...")

logger = logging.getLogger("startup_profile")

from bluesky_queueserver import is_re_worker_active

ophyd.signal.EpicsSignal.set_defaults(connection_timeout=5)
# See docstring for nslsii.configure_base() for more details
# this command takes away much of the boilerplate for settting up a profile
# (such as setting up best effort callbacks etc)

from IPython.terminal.prompts import Prompts, Token

class ProposalIDPrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [
            (
                Token.Prompt,
                f"{RE.md.get('data_session', 'N/A')} [",
            ),
            (Token.PromptNum, str(self.shell.execution_count)),
            (Token.Prompt, "]: "),
        ]


ip = get_ipython()
ip.prompts = ProposalIDPrompt(ip)

class TiledInserter:
    
    def __init__(self, tiled_writing_client):
        
        self.tiled_writing_client = tiled_writing_client
        
    def insert(self, name, doc):
        ATTEMPTS = 20
        error = None
        
        for attempt in range(ATTEMPTS):
            try:
                self.tiled_writing_client.post_document(name, doc)
            except Exception as exc:
                print("Document saving failure:", repr(exc))
                error = exc
            else:
                break
            ttime.sleep(2)
        else:
            # Out of attempts
            raise error


# Define tiled catalog
tiled_writing_client = from_profile(
    "nsls2", api_key=os.environ["TILED_BLUESKY_WRITING_API_KEY_XPD"]
)["xpd"]["raw"]
tiled_inserter = TiledInserter(tiled_writing_client)
if not is_re_worker_active():
    c = tiled_reading_client = from_profile("nsls2")["xpd"]["raw"]
    db = Broker(c)

nslsii.configure_base(
    get_ipython().user_ns,
    tiled_inserter,
    pbar=True,
    bec=True,
    magics=True,
    mpl=True,
    epics_context=False,
    publish_documents_with_kafka="xpd" if is_re_worker_active() else None,
    redis_url="info.xpd.nsls2.bnl.gov",
)

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


RE.md["facility"] = "NSLS-II"
RE.md["group"] = "XPD"
RE.md["beamline_id"] = "28-ID-2"

import subprocess


def show_env():
    # this is not guaranteed to work as you can start IPython without hacking
    # the path via activate
    proc = subprocess.Popen(["conda", "list"], stdout=subprocess.PIPE)
    out, err = proc.communicate()
    a = out.decode("utf-8")
    b = a.split("\n")
    print(b[0].split("/")[-1][:-1])

# Data Security Convenience Functions
# check the current logged in + active user
def whoami():
    try:
        print(f"\nLogged in to Tiled as: {c.context.whoami()['identities'][0]['id']}\n")
    except TypeError as e:
        print("Not authenticated with Tiled! Please login...")


whoami()


# logout of Tiled and clear the cached default identities (username)
def logout():
    c.logout(clear_default=True)


# login to Tiled using the specified username
# this version automatically logs-out the existing user when called
def login():
    beamline_username = input("Please enter your username: ")
    beamline_unauthenticated = (
        c.context.api_key is None and c.context.http_client.auth is None
    )
    if not beamline_unauthenticated:
        beamline_current_user = c.context.whoami()["identities"][0]["id"]
        if beamline_username != beamline_current_user:
            logout()

    c.login(username=beamline_username)

    print(f"Logged in to Tiled as {beamline_username}!")