"""
UV-Vis-only and X-ray-only acquisition plan variants.

Registers ``uvvis_acquire`` and ``xray_acquire`` into the queueserver worker
namespace so the blop agent can submit them by name.  Both are thin variants
of ``xray_uvvis_acquire`` from ``97-xray_uvvis.py`` and share all of its
helpers (``steady_state_flow``, ``_wash_loop``, ``measure_absorbance``,
``measure_pl``, ``measure_scattering``, ``_pl_with_quality_gate``,
``_resolve_pumps``, ``_resolve_pumps_from_dofs``, ``_make_sample_name``,
TypedDicts, DEFAULT_* dicts) which are already in the worker namespace from
the earlier startup file.

Deploy:
    Copy this file to the same startup/ directory as 97-xray_uvvis.py.
    Restart the RE manager so both names appear in existing_plans.
    ``user_group_permissions.yaml`` already allows ``:.*`` for primary/root —
    no permissions change needed.

Differences from xray_uvvis_acquire
------------------------------------
uvvis_acquire:
  - No XrayConfig parameter; pe1c never touched.
  - Stages [qepro] only.
  - Runs PL quality gate + absorbance; no measure_scattering.
  - No _inject_* / periodic_dark wrappers.
  - run_key = "uvvis_acquire"

xray_acquire:
  - No QualityConfig parameter; qepro never touched.
  - Stages [pe1c] only; runs _pre_plan(pe1c) for detector config metadata.
  - Runs measure_scattering only; no PL / absorbance.
  - Keeps _inject_* / periodic_dark logic gated on xray_no_dark.
  - run_key = "xray_acquire"

Bug-fixes vs original xray_uvvis_acquire end-of-plan stop_group call:
  - wash_pumps defaults to [] when do_wash is False (was NameError).
  - dilute_pump defaults to [] when post_dilute is False (was TypeError on + None).
"""


# ---------------------------------------------------------------------------
# uvvis_acquire
# ---------------------------------------------------------------------------


def uvvis_acquire(
    suggestions: list[dict],
    actuators,
    sensors=None,
    md=None,
    *,
    flow_config: FlowConfig | None = None,
    wash_config: WashConfig | None = None,
    quality_config: QualityConfig | None = None,
):
    """UV-Vis-only acquisition plan (no X-ray).

    Runs the full pump synthesis sequence and collects fluorescence + absorbance
    via the QEPro spectrometer.  pe1c is never staged or triggered.

    Blop AcquisitionPlan signature::

        uvvis_acquire(suggestions, actuators, sensors=None, md=None)

    Parameters
    ----------
    suggestions : list[dict]
        One-element list from the optimizer; dict maps DOF names to rates.
    actuators : list
        Ignored (blop protocol requirement).
    sensors : list | None
        Ignored (blop protocol requirement).
    md : dict | None
        Extra metadata merged into the run header.
    flow_config : FlowConfig | None
        Overrides for DEFAULT_FLOW_CONFIG.
    wash_config : WashConfig | None
        Overrides for DEFAULT_WASH_CONFIG.
    quality_config : QualityConfig | None
        Overrides for DEFAULT_QUALITY_CONFIG.

    Returns
    -------
    str
        UID of the Bluesky run.
    """
    flow: FlowConfig = {**DEFAULT_FLOW_CONFIG, **(flow_config or {})}
    wash: WashConfig = {**DEFAULT_WASH_CONFIG, **(wash_config or {})}
    quality: QualityConfig = {**DEFAULT_QUALITY_CONFIG, **(quality_config or {})}

    syringe_list        = flow["syringe_list"]
    syringe_mater_list  = flow["syringe_mater_list"]
    target_vol_list     = flow["target_vol_list"]
    set_target_list     = flow["set_target_list"]
    rate_unit           = flow["rate_unit"]
    mixer_lengths_cm    = flow["mixer_lengths_cm"]
    resident_t_ratio    = flow["resident_t_ratio"]
    precursor_list      = flow["precursor_list"]
    precursor_prefix_list = flow["precursor_prefix_list"]
    post_dilute         = flow["post_dilute"]
    dof_to_pump         = flow["dof_to_pump"]
    dilute_pump_name    = flow["dilute_pump_name"]
    post_dilute_ratio   = flow["post_dilute_ratio"]
    post_dilute_wait_sec = flow["post_dilute_wait_sec"]

    do_wash    = wash["do_wash"]
    use_good_bad = quality["use_good_bad"]
    good_target  = quality["good_target"]
    max_bad      = quality["max_bad"]
    num_abs      = quality["num_abs"]
    num_flu      = quality["num_flu"]

    if len(suggestions) != 1:
        raise RuntimeError(
            f"uvvis_acquire expects exactly 1 suggestion, got {len(suggestions)}"
        )
    suggestion = suggestions[0]

    dof_names = []
    for n in precursor_prefix_list:
        for k in suggestion.keys():
            if n in k:
                dof_names.append(k)
    rate_list = [float(suggestion[name]) for name in dof_names]

    pump_list   = _resolve_pumps_from_dofs(dof_names, dof_to_pump)
    sample_type = _make_sample_name(rate_list, precursor_prefix_list)

    _md = {
        "sample_type": sample_type,
        "sample_name": sample_type,
        "infuse_rates": rate_list,
        "dof_names": dof_names,
        "precursors": precursor_list[: len(pump_list)],
        "pumps": [p.name for p in pump_list],
        "detectors": ["qepro"],
    }
    _md.update(md or {})

    monitor = (
        PLQualityMonitor(qepro, stream_name="fluorescence") if use_good_bad else None
    )
    subs = {"descriptor": [monitor], "event": [monitor]} if monitor else {}

    dilute_pump = _resolve_pumps(dilute_pump_name) if post_dilute else []

    @bpp.subs_decorator(subs)
    @bpp.set_run_key_decorator("uvvis_acquire")
    @bpp.baseline_decorator(pump_list)
    @bpp.stage_decorator([qepro])
    @bpp.run_decorator(md=_md)
    def acquisition():
        yield from _pl_with_quality_gate(qepro, monitor, num_flu, good_target, max_bad)
        yield from measure_absorbance(qepro, num_abs)
        yield from bps.mv(LED, "Low", UV_shutter, "Low")
        if post_dilute and dilute_pump:
            yield from stop_group([dilute_pump[-1]])
            dilute_pump[-1].stop_pump()
            print(f"\nUV-Vis done. Stopping {dilute_pump_name[-1]}\n")

    uid = yield from steady_state_flow(
        acquisition(),
        pump_list=pump_list,
        rate_list=rate_list,
        syringe_list=syringe_list[: len(pump_list)],
        target_vol_list=target_vol_list[: len(pump_list)],
        set_target_list=set_target_list[: len(pump_list)],
        syringe_mater_list=syringe_mater_list[: len(pump_list)],
        mixer_lengths_cm=mixer_lengths_cm,
        resident_t_ratio=resident_t_ratio,
        post_dilute=post_dilute,
        dilute_pump=dilute_pump or None,
        dilute_rate_ratio=post_dilute_ratio,
        dilute_wait_sec=post_dilute_wait_sec,
    )

    wash_pumps = []
    if do_wash and wash["pump_names"]:
        wash_pumps = _resolve_pumps(wash["pump_names"])
        yield from _wash_loop(
            wash_pumps,
            wash["syringe_list"],
            wash["rate_list"],
            wash["duration_sec"],
            syringe_mater_list=wash["syringe_mater_list"],
            target_vol_list=wash["target_vol_list"],
            set_target_list=wash["set_target_list"],
            rate_unit=rate_unit,
        )

    yield from stop_group(wash_pumps + pump_list + dilute_pump)
    return uid


# ---------------------------------------------------------------------------
# xray_acquire
# ---------------------------------------------------------------------------


def xray_acquire(
    suggestions: list[dict],
    actuators,
    sensors=None,
    md=None,
    *,
    flow_config: FlowConfig | None = None,
    xray_config: XrayConfig | None = None,
    wash_config: WashConfig | None = None,
):
    """X-ray-only acquisition plan (no UV-Vis / QEPro).

    Runs the full pump synthesis sequence and collects one scattering frame
    from pe1c.  qepro is never staged or triggered.

    Blop AcquisitionPlan signature::

        xray_acquire(suggestions, actuators, sensors=None, md=None)

    Parameters
    ----------
    suggestions : list[dict]
        One-element list from the optimizer; dict maps DOF names to rates.
    actuators : list
        Ignored (blop protocol requirement).
    sensors : list | None
        Ignored (blop protocol requirement).
    md : dict | None
        Extra metadata merged into the run header.
    flow_config : FlowConfig | None
        Overrides for DEFAULT_FLOW_CONFIG.
    xray_config : XrayConfig | None
        Overrides for DEFAULT_XRAY_CONFIG.
    wash_config : WashConfig | None
        Overrides for DEFAULT_WASH_CONFIG.

    Returns
    -------
    str
        UID of the Bluesky run.
    """
    flow: FlowConfig = {**DEFAULT_FLOW_CONFIG, **(flow_config or {})}
    xray: XrayConfig = {**DEFAULT_XRAY_CONFIG, **(xray_config or {})}
    wash: WashConfig = {**DEFAULT_WASH_CONFIG, **(wash_config or {})}

    syringe_list        = flow["syringe_list"]
    syringe_mater_list  = flow["syringe_mater_list"]
    target_vol_list     = flow["target_vol_list"]
    set_target_list     = flow["set_target_list"]
    rate_unit           = flow["rate_unit"]
    mixer_lengths_cm    = flow["mixer_lengths_cm"]
    resident_t_ratio    = flow["resident_t_ratio"]
    precursor_list      = flow["precursor_list"]
    precursor_prefix_list = flow["precursor_prefix_list"]
    post_dilute         = flow["post_dilute"]
    dof_to_pump         = flow["dof_to_pump"]
    dilute_pump_name    = flow["dilute_pump_name"]
    post_dilute_ratio   = flow["post_dilute_ratio"]
    post_dilute_wait_sec = flow["post_dilute_wait_sec"]

    xray_exposure      = xray["exposure"]
    xray_frame_acq_time = xray["frame_acq_time"]
    xray_stream_name   = xray["stream_name"]
    xray_no_dark       = xray["no_dark"]

    do_wash = wash["do_wash"]

    if len(suggestions) != 1:
        raise RuntimeError(
            f"xray_acquire expects exactly 1 suggestion, got {len(suggestions)}"
        )
    suggestion = suggestions[0]

    dof_names = []
    for n in precursor_prefix_list:
        for k in suggestion.keys():
            if n in k:
                dof_names.append(k)
    rate_list = [float(suggestion[name]) for name in dof_names]

    pump_list   = _resolve_pumps_from_dofs(dof_names, dof_to_pump)
    sample_type = _make_sample_name(rate_list, precursor_prefix_list)

    # Configure area detector and collect scan-plan metadata
    sp_md = yield from _pre_plan([pe1c], xray_exposure, frame_acq_time=xray_frame_acq_time)

    _md = {
        "sample_type": sample_type,
        "sample_name": sample_type,
        "infuse_rates": rate_list,
        "dof_names": dof_names,
        "precursors": precursor_list[: len(pump_list)],
        "pumps": [p.name for p in pump_list],
        "detectors": ["pe1c"],
    }
    _md.update(md or {})
    _md.update(sp_md)

    dilute_pump = _resolve_pumps(dilute_pump_name) if post_dilute else []

    @bpp.set_run_key_decorator("xray_acquire")
    @bpp.baseline_decorator(pump_list)
    @bpp.stage_decorator([pe1c])
    @bpp.run_decorator(md=_md)
    def acquisition():
        if post_dilute and dilute_pump:
            yield from stop_group([dilute_pump[-1]])
            dilute_pump[-1].stop_pump()
            print(f"\nStopping {dilute_pump_name[-1]} before X-ray\n")
        yield from measure_scattering(pe1c, stream_name=xray_stream_name)

    # Apply dark-frame / metadata injectors the same way xray_uvvis_acquire does
    if xray_no_dark:
        grand_plan = acquisition()
        grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid)
        grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md)
        grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage)
        inner_plan = grand_plan
    else:
        grand_plan = periodic_dark(acquisition())
        grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid)
        grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md)
        grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage)
        inner_plan = grand_plan

    uid = yield from steady_state_flow(
        inner_plan,
        pump_list=pump_list,
        rate_list=rate_list,
        syringe_list=syringe_list[: len(pump_list)],
        target_vol_list=target_vol_list[: len(pump_list)],
        set_target_list=set_target_list[: len(pump_list)],
        syringe_mater_list=syringe_mater_list[: len(pump_list)],
        mixer_lengths_cm=mixer_lengths_cm,
        resident_t_ratio=resident_t_ratio,
        post_dilute=post_dilute,
        dilute_pump=dilute_pump or None,
        dilute_rate_ratio=post_dilute_ratio,
        dilute_wait_sec=post_dilute_wait_sec,
    )

    wash_pumps = []
    if do_wash and wash["pump_names"]:
        wash_pumps = _resolve_pumps(wash["pump_names"])
        yield from _wash_loop(
            wash_pumps,
            wash["syringe_list"],
            wash["rate_list"],
            wash["duration_sec"],
            syringe_mater_list=wash["syringe_mater_list"],
            target_vol_list=wash["target_vol_list"],
            set_target_list=wash["set_target_list"],
            rate_unit=rate_unit,
        )

    yield from stop_group(wash_pumps + pump_list + dilute_pump)
    return uid