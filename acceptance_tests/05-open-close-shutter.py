"Watch for shutter to close and open."
from bluesky.plan_stubs import pchain, wait, abs_set
from ophyd import set_and_wait


# simple signal-based approach

set_and_wait(shctl1, 1)
set_and_wait(shctl1, 0)
set_and_wait(shctl1, 1)


# better Device-based approach
# RE(pchain(abs_set(shutter, 'Open'), wait(), abs_set(shutter, 'Close'), wait(),
#     abs_set(shutter, 'Open'), wait()))
