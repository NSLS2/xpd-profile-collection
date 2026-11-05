""" Register XPD tools plans into the queueserver namespace"""

''' from xpd_tools.optimization.plans import (
	create_uvvis_plan,
	create_xray_plan,
	create_xray_screened_plan,
	create_xray_uvvis_plan
 )'''


"""
Hack method to be replaced with XPD-tools managed plans.

Done Nov 5 by TB to be able to run experiments.






Standalone worker plans for the current xpd-tools config-passing path.


Plan coverage
-------------
uvvis_acquire      → this file  (xpd-tools plan, new config kwarg path)
xray_acquire       → this file  (xpd-tools plan, new config kwarg path)
xray_uvvis_acquire → 97-xray_uvvis.py  (old flow_config path, untouched)

How it works
------------
The host's build_agent.build() sends::

    acquisition_plan      = "uvvis_acquire" | "xray_acquire"
    acquisition_plan_kwargs = {"config": build_agent.to_config()}

Each wrapper below reconstructs a BuildAgent from the arriving config dict,
binds it to the device objects built here at worker startup, and delegates to
the real xpd-tools plan.  Cross-trial state (VolumeTracker, quality signals)
is cached in the closure keyed by (plan_name, config_fingerprint), so it
persists across trials of the same campaign and resets cleanly if the config
changes (e.g. a syringe swap between campaigns).

Device notes
------------
- Pumps / QEPro / LED / shutters come from build_halide_devices() (v2 pump API).
- pe1c (area detector) is injected from the profile-collection namespace for
  xray_acquire.  Guarded with try/except so a uvvis-only or mock worker still
  loads if pe1c is absent.
- wrap_xray_run adapts the beamline's periodic_dark_02(plan) to the xpd-tools
  signature (plan, no_dark).  Guarded the same way.

Environment variables
---------------------
XPD_HALIDE_MOCK  (optional, default "0")
    Set to "1" to use simulated devices instead of live EPICS connections.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Build xpd-tools device wrappers (v2 pump API; no config file needed)
# ---------------------------------------------------------------------------

from xpd_tools.optimization.devices import build_halide_devices  # noqa: E402

_mock = os.environ.get("XPD_HALIDE_MOCK", "0").strip().lower() in ("1", "true", "yes")
if _mock:
    _logger.warning("XPD_HALIDE_MOCK is set -- using simulated devices, NOT real hardware.")

_devices = build_halide_devices(mock=_mock)

# Inject the live area detector for xray_acquire.
# Guarded so a uvvis-only / mock worker still loads cleanly if pe1c is absent.
try:
    _devices["xray_detector"] = pe1c   # noqa: F821 (profile-collection global from 80-areadetector.py)
    _logger.info("xray_acquire: pe1c injected as xray_detector.")
except NameError:
    _logger.warning(
        "pe1c not found in worker namespace -- xray_acquire will raise if called. "
        "Ensure 80-areadetector.py loads before 98-hack.py."
    )


def _wrap_xray_run(plan, no_dark):
    """Adapt the beamline's periodic_dark_02 to xpd-tools' (plan, no_dark) signature."""
    if no_dark:
        return plan
    try:
        return periodic_dark_02(plan)  # noqa: F821 (profile-collection global from 94-CHL-plans.py)
    except NameError:
        _logger.warning("periodic_dark_02 not found -- xray run will proceed without dark frames.")
        return plan


# ---------------------------------------------------------------------------
# 2. Per-campaign plan cache: (plan_name, config_fingerprint) -> bound plan
#
#    Caching means VolumeTracker.measure_sec and quality signals survive
#    across trials.  A new config (syringe swap, geometry change) gets its
#    own fresh entry automatically.
# ---------------------------------------------------------------------------

_cache: dict[tuple[str, str], object] = {}


def _fingerprint(config: dict) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, default=str).encode()
    ).hexdigest()


def _get_bound_plan(plan_name: str, config: dict):
    key = (plan_name, _fingerprint(config))
    if key in _cache:
        return _cache[key]

    from xpd_tools.optimization.agent import BuildAgent  # lazy import

    agent = BuildAgent.from_config(config)
    expected = agent._acquisition_plan_name()
    if expected != plan_name:
        raise ValueError(
            f"Worker called '{plan_name}' but the arriving config has "
            f"evaluation_method={agent.evaluation_method!r} which maps to "
            f"'{expected}'.  Make sure the host's BuildAgent uses the matching "
            "evaluation_method for this plan."
        )

    _logger.info(
        "Binding '%s' from config (evaluation_method=%r, sources=%r)",
        plan_name,
        agent.evaluation_method,
        [s.pump for s in (agent.sources or [])],
    )

    xray_plans = {"xray_acquire", "xray_screened_acquire", "xray_uvvis_acquire"}
    wrap = _wrap_xray_run if plan_name in xray_plans else None
    plans = agent.register_acquisition_plans(_devices, wrap_xray_run=wrap)
    _cache[key] = plans[plan_name]
    return _cache[key]


# ---------------------------------------------------------------------------
# 3. Worker-facing plan callables (discovered by queueserver via globals())
# ---------------------------------------------------------------------------

def uvvis_acquire(suggestions, actuators, sensors=None, config=None, md=None):
    """UV-Vis optimization acquisition plan (xpd-tools config-passing path)."""
    
    _logger.info("ARRIVING config experiment.source=%r", (config or {}).get("experiment", {}).get("sources"))
    
    if config is None:
        raise ValueError(
            "uvvis_acquire requires a 'config' kwarg containing build_agent.to_config(). "
            "Ensure the host's build_agent.build() is up to date."
        )
    yield from _get_bound_plan("uvvis_acquire", config)(suggestions, actuators, sensors, md)


def xray_acquire(suggestions, actuators, sensors=None, config=None, md=None):
    """X-ray-only optimization acquisition plan (xpd-tools config-passing path).

    Note: requires pe1c (area detector) and periodic_dark_02 to be present in
    the worker namespace.  Validate before running an xray campaign.
    """
    if config is None:
        raise ValueError(
            "xray_acquire requires a 'config' kwarg containing build_agent.to_config(). "
            "Ensure the host's build_agent.build() is up to date."
        )
    yield from _get_bound_plan("xray_acquire", config)(suggestions, actuators, sensors, md)


