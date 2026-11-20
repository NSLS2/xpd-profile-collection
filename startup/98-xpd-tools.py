"""Load TJ Barrett's autonomous-workflow plans for the Queue Server from xpd-tools.

They used to be defined here and in 97-xray_uvvis.py. xpd-tools now carries them
verbatim (xpd_tools.optimization.qserver, NSLS2/xpd-tools#44); install() hands them
the devices and helpers this profile defines and puts xray_uvvis_acquire,
uvvis_acquire and xray_acquire (and everything else those files defined) back into
this namespace. Plan changes are made in xpd-tools and reach here through the
xpd-tools pin in pixi.lock.
"""

from xpd_tools.optimization.qserver import install

install(globals())
