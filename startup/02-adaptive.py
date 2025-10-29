"""Plan for running gpcam AE with a gradient TiCu sample."""
import uuid
import itertools
import time

import numpy as np

from ophyd import Device, Signal, Component as Cpt

import bluesky.preprocessors as bpp
import bluesky.plan_stubs as bps
import bluesky.plans as bp
from bluesky.utils import short_uid
from queue import Empty
import pprint


def future_count(detectors, num=1, delay=None, *, per_shot=None, md=None):
    """
    Take one or more readings from detectors.
    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    num : integer, optional
        number of readings to take; default is 1
        If None, capture data until canceled
    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.
    per_shot : callable, optional
        hook for customizing action of inner loop (messages per step)
        Expected signature ::
           def f(detectors: Iterable[OphydObj]) -> Generator[Msg]:
               ...
    md : dict, optional
        metadata
    Notes
    -----
    If ``delay`` is an iterable, it must have at least ``num - 1`` entries or
    the plan will raise a ``ValueError`` during iteration.
    """
    if num is None:
        num_intervals = None
    else:
        num_intervals = num - 1
    _md = {
        "detectors": [det.name for det in detectors],
        "num_points": num,
        "num_intervals": num_intervals,
        "plan_args": {"detectors": list(map(repr, detectors)), "num": num},
        "plan_name": "count",
        "hints": {},
    }
    _md.update(md or {})
    _md["hints"].setdefault("dimensions", [(("time",), "primary")])

    if per_shot is None:
        per_shot = bps.one_shot

    @bpp.stage_decorator(detectors)
    @bpp.run_decorator(md=_md)
    def inner_count():
        return (
            yield from bps.repeat(partial(per_shot, detectors), num=num, delay=delay)
        )

    return (yield from inner_count())


def _xpd_pre_plan(dets, exposure):
    """Handle detector exposure time + xpdan required metadata"""

    def configure_area_det(det, exposure):
        '''Configure an area detector in "continuous mode"'''

        def _check_mini_expo(exposure, acq_time):
            if exposure < acq_time:
                raise ValueError(
                    "WARNING: total exposure time: {}s is shorter "
                    "than frame acquisition time {}s\n"
                    "you have two choices:\n"
                    "1) increase your exposure time to be at least"
                    "larger than frame acquisition time\n"
                    "2) increase the frame rate, if possible\n"
                    "    - to increase exposure time, simply resubmit"
                    " the ScanPlan with a longer exposure time\n"
                    "    - to increase frame-rate/decrease the"
                    " frame acquisition time, please use the"
                    " following command:\n"
                    "    >>> {} \n then rerun your ScanPlan definition"
                    " or rerun the xrun.\n"
                    "Note: by default, xpdAcq recommends running"
                    "the detector at its fastest frame-rate\n"
                    "(currently with a frame-acquisition time of"
                    "0.1s)\n in which case you cannot set it to a"
                    "lower value.".format(
                        exposure,
                        acq_time,
                        ">>> glbl['frame_acq_time'] = 0.5  #set" " to 0.5s",
                    )
                )

        # todo make
        ret = yield from bps.read(det.cam.acquire_time)
        if ret is None:
            acq_time = 1
        else:
            acq_time = ret[det.cam.acquire_time.name]["value"]
        _check_mini_expo(exposure, acq_time)
        if hasattr(det, "images_per_set"):
            # compute number of frames
            num_frame = np.ceil(exposure / acq_time)
            yield from bps.mov(det.images_per_set, num_frame)
        else:
            # The dexela detector does not support `images_per_set` so we just
            # use whatever the user asks for as the thing
            # TODO: maybe put in warnings if the exposure is too long?
            num_frame = 1
        computed_exposure = num_frame * acq_time

        # print exposure time
        print(
            "INFO: requested exposure time = {} - > computed exposure time"
            "= {}".format(exposure, computed_exposure)
        )
        return num_frame, acq_time, computed_exposure

    # setting up area_detector
    for ad in (d for d in dets if hasattr(d, "cam")):
        (num_frame, acq_time, computed_exposure) = yield from configure_area_det(
            ad, exposure
        )
    else:
        acq_time = 0
        computed_exposure = exposure
        num_frame = 0

    sp = {
        "time_per_frame": acq_time,
        "num_frames": num_frame,
        "requested_exposure": exposure,
        "computed_exposure": computed_exposure,
        "type": "ct",
        "uid": str(uuid.uuid4()),
        "plan_name": "ct",
    }

    # update md
    _md = {"sp": sp, **{f"sp_{k}": v for k, v in sp.items()}}

    return _md


def rocking_ct(dets, exposure, motor, start, stop, *, num=1, md=None):
    """Take a count while "rocking" the y-position"""
    _md = md or {}
    sp_md = yield from _xpd_pre_plan(dets, exposure)
    _md.update(sp_md)

    @bpp.reset_positions_decorator([motor.velocity])
    def per_shot(dets):
        nonlocal start, stop
        yield from bps.mv(motor.velocity, abs(stop - start) / exposure)
        gp = short_uid("rocker")
        yield from bps.abs_set(motor, stop, group=gp)
        yield from bps.trigger_and_read(dets)
        yield from bps.wait(group=gp)
        start, stop = stop, start

    return (yield from future_count(dets, md=_md, per_shot=per_shot, num=num))


def stepping_ct(dets, exposure, motor, start, stop, *, md=None, num=3):
    """Take data at several points along the y-direction"""
    _md = md or {}
    sp_md = yield from _xpd_pre_plan(dets, exposure)
    _md.update(sp_md)

    return (yield from bp.scan(dets, motor, start, stop, num, md=_md))


def adaptive_plan(
    dets,
    first_point,
    *,
    to_recommender,
    from_recommender,
    md=None,
    transform_pair,
    real_motors,
    snap_function=None,
    reccomender_timeout=1,
    exposure=30,
    max_runs=1,
    take_data=None,
    num=None,
    rocking_range=2,
):
    """
    Execute an adaptive scan using an inter-run recommendation engine.

    Parameters
    ----------
    dets : List[OphydObj]
       The detector to read at each point.  The dependent keys that the
       recommendation engine is looking for must be provided by these
       devices.

    first_point : tuple[float, int, int]
       The first point of the scan.  These values will be passed to the
       forward function and the objects passed in real_motors will be moved.

       The order is (Ti_frac, temperature, annealing_time)

    to_recommender : Callable[document_name: str, document: dict]
       This is the callback that will be registered to the RunEngine.

       The expected contract is for each event it will place either a
       dict mapping independent variable to recommended value or None.

       This plan will either move to the new position and take data
       if the value is a dict or end the run if `None`

    from_recommender : Queue
       The consumer side of the Queue that the recommendation engine is
       putting the recommendations onto.

    md : dict[str, Any], optional
       Any extra meta-data to put in the Start document

    take_reading : plan
        function to do the actual acquisition ::

           def take_reading(dets, md={}):
                yield from ...

        Callable[List[OphydObj], Optional[Dict[str, Any]]] -> Generator[Msg]

        This plan must generate exactly 1 Run

        Defaults to `bluesky.plans.count`

    transform_pair : TransformPair

       Expected to have two attributes 'forward' and 'inverse'

       The forward transforms from "data coordinates" (Ti fraction,
       temperature, annealing time) to "beam line" (x/y motor
       position) coordinates ::

          def forward(Ti, temperature, time):
               return x, y

       The inverse transforms from "beam line" (x/y motor position)
       coordinates to "data coordinates" (Ti fraction, temperature,
       annealing time) ::

          def inverse(x, y):
               return Ti_frac, temperature, annealing_time

    snap_function : Callable, optional
        "snaps" the requested measurement to the nearest available point ::

           def snap(Ti, temperature, time):
               returns snapped_Ti, snapped_temperature, snapped_time

    reccomender_timeout : float, optional

        How long to wait for the reccomender to respond before giving
        it up for dead.

    """
    if take_data is None:
        take_data=rocking_ct

    # unpack the real motors
    x_motor, y_motor = real_motors
    # make the soft pseudo axis
    ctrl = Control(name="ctrl")
    pseudo_axes = tuple(getattr(ctrl, k) for k in ctrl.component_names)
    # convert the first_point variable to from we will be getting from
    # queue
    first_point = {m.name: v for m, v in zip(pseudo_axes, first_point)}

    _md = {
        "batch_id": str(uuid.uuid4()),
        "ticu_adaptive": {
            "rocking_range": rocking_range,
            "take_data": take_data.__name__,
            "snapped": snap_function is not None,
            "snap_tolerance": (
                getattr(snap_function, "tols") if snap_function is not None else {}
            ),
            "num": num if num is not None else "None",
        },
    }

    _md.update(md or {})

    take_data_kwargs = {}
    if num is not None:
        take_data_kwargs["num"] = num

    plan_start_time = time.time()
    plan_stop_time = plan_start_time + (12 * 60 * 60)

    @bpp.subs_decorator(to_recommender)
    def gp_inner_plan():
        # drain the queue in case there is anything left over from a previous
        # run
        while True:
            try:
                from_recommender.get(block=False)
            except Empty:
                break
        uids = []
        next_point = first_point
        for j in itertools.count():
            # extract the target position as a tuple
            target = tuple(next_point[k.name] for k in pseudo_axes)
            print(f"next point: {pprint.pformat(next_point)}")
            # if we have a snapping function use it
            if snap_function is not None:
                target = snap_function(*target)
            print(f"snapped target: {target}")
            # compute the real target
            real_target = transform_pair.forward(*target)
            print(f"real target: {real_target}")

            # move to the new position
            t0 = time.time()
            yield from bps.mov(*itertools.chain(*zip(real_motors, real_target)))
            t1 = time.time()
            print(f"move to target took {t1-t0:0.2f}s")

            # read back where the motors really are
            real_x = yield from _read_the_first_key(x_motor)
            real_y = yield from _read_the_first_key(y_motor)
            print(f"real x and y: {real_x}, {real_y}")

            # compute the new (actual) pseudo positions
            pseudo_target = transform_pair.inverse(real_x, real_y)
            print(f"pseudo target: {pseudo_target}")
            # and set our local synthetic object to them
            yield from bps.mv(*itertools.chain(*zip(pseudo_axes, pseudo_target)))

            # kick off the next actually measurement!
            uid = yield from take_data(
                dets + list(real_motors) + [ctrl],
                exposure,
                y_motor,
                real_y - rocking_range,
                real_y + rocking_range,
                md={
                    **_md,
                    "batch_count": j,
                    "adaptive_step": {
                        "requested": next_point,
                        "snapped": {k.name: v for k, v in zip(pseudo_axes, target)},
                    },
                },
                **take_data_kwargs,
            )
            uids.append(uid)

            # ask the reccomender what to do next
            t0 = time.time()
            next_point = from_recommender.get(timeout=reccomender_timeout)
            t1 = time.time()
            print(f"waited {t1-t0:.2f}s for recommendation")

            print(f"batch count: {j}")
            if next_point is None:
                print("no recommendation - stopping")
                return
            elif j >= (max_runs - 1):
                print(f"stopping after batch_count reached {j}")
                return
            elif time.time() > plan_stop_time:
                print(f"stopping after {time.time() - plan_start_time:.2f}s")
            else:
                print(f"keep going!")

        return uids

    return (yield from gp_inner_plan())


class SignalWithUnits(Signal):
    """Soft signal with units tacked on."""

    def __init__(self, *args, units, **kwargs):
        super().__init__(*args, **kwargs)
        self._units = units

    def describe(self):
        ret = super().describe()
        ret[self.name]["units"] = self._units
        ret[self.name]["source"] = "derived"
        return ret


class Control(Device):
    """Soft device to inject computed pseudo positions."""

    Ti = Cpt(SignalWithUnits, value=0, units="percent TI", kind="hinted")
    temp = Cpt(SignalWithUnits, value=0, units="degrees C", kind="hinted")
    annealing_time = Cpt(SignalWithUnits, value=0, units="s", kind="hinted")
    thickness = Cpt(SignalWithUnits, value=0, units="enum", kind="hinted")


def _read_the_first_key(obj):
    """Helper to get 'the right' reading."""
    reading = yield from bps.read(obj)
    if reading is None:
        return None
    hints = obj.hints.get("fields", [])
    if len(hints):
        key, *_ = hints
    else:
        key, *_ = list(reading)
    return reading[key]["value"]
