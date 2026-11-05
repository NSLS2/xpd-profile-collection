"""Register the xpd-tools autonomous-workflow plans with the Queue Server.

The plans live in xpd-tools (``xpd_tools.optimization.worker``); this file only
binds them to this profile's area detector and dark-frame handling, so plan
changes are made, reviewed and tested in xpd-tools, and reach the worker by
bumping the xpd-tools pin in ``pixi.toml``/``pixi.lock``.

Registered names (this file loads after ``97-xray_uvvis.py``, so these replace
its ``xray_uvvis_acquire`` for the agent): ``uvvis_acquire``, ``xray_acquire``,
``xray_screened_acquire``, ``xray_uvvis_acquire``.

The agent must be built with ``build_agent.build(send_config=True)`` so each
queued step carries ``config=build_agent.to_config()``.  The worker rebuilds the
campaign from that config and keeps the bound plan per config, so syringe volume
tracking carries across the steps of one campaign.

Environment: ``XPD_HALIDE_MOCK=1`` builds simulated pumps/QEPro/shutters.
"""

import os

import bluesky.preprocessors as bpp
from xpdacq.xpdacq import (
    _inject_analysis_stage,
    _inject_calibration_md,
    _inject_qualified_dark_frame_uid,
    periodic_dark,
)
from xpd_tools.optimization.worker import register_worker_plans


def _wrap_xray_run(plan, no_dark):
    """Dark frames and xpdacq metadata for X-ray runs, as in 97-xray_uvvis.py."""
    if not no_dark:
        plan = periodic_dark(plan)
    for mutator in (
        _inject_qualified_dark_frame_uid,
        _inject_calibration_md,
        _inject_analysis_stage,
    ):
        plan = bpp.msg_mutator(plan, mutator)
    return plan


register_worker_plans(
    globals(),
    xray_detector=pe1c,  # noqa: F821 -- 80-areadetector.py
    wrap_xray_run=_wrap_xray_run,
    mock=os.environ.get("XPD_HALIDE_MOCK", "0").strip().lower() in ("1", "true", "yes"),
)
