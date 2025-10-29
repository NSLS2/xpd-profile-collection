import os
import numpy as np
from bluesky.plan_stubs import (abs_set, )
from bluesky.plans import (scan, count, list_scan, adaptive_scan)
from bluesky.preprocessors import (subs_wrapper, pchain,
                                   reset_positions_wrapper)
from bluesky.callbacks import LiveTable, LivePlot, LiveFit, LiveFitPlot
from bluesky.plan_tools import print_summary

from lmfit import Model, Parameter
from lmfit.models import VoigtModel, LinearModel
from lmfit.lineshapes import voigt


def MED(init_gas, other_gas, minT, maxT, num_steps, num_steady, num_trans, num_loops=2):
    """
    1. Start flowing the initial gas.
    2. Scan the temperature from minT to maxT in `num_steps` evenly-spaced steps.
    3. Hold temperature at maxT and take  `num_steady` images.
    4. Repeat (2) and (3) `num_loops` times.
    5. Switch the gas to `other_gas` and take `num_trans` acquisitions.
    6. Switch it back and take another `num_trans` acquisitions.

    Examples
    --------
    Set the gasses. They can be in any other, nothing to do with
    the order they are used in the plan.
    >>> gas.gas_list = ['O2', 'CO2']

    Optionally, preview the plan.
    >>> print_summary(MED('O2', 'C02', 200, 300, 21, 20, 60))

    Execute it.
    >>> RE(MED('O2', 'C02', 200, 300, 21, 20, 60))

    """
    # Step 1
    yield from abs_set(gas, init_gas)
    # Steps 2 and 3 in a loop.
    for _ in range(num_loops):
        yield from subs_wrapper(scan([pe1, gas.current_gas], eurotherm, minT, maxT, num_steps),
                            LiveTable([eurotherm, gas.current_gas]))
        yield from subs_wrapper(count([pe1], num_steady), LiveTable([]))
    # Step 4
    yield from abs_set(gas, other_gas)
    yield from subs_wrapper(count([pe1], num_steady), LiveTable([]))
    # Step 6
    yield from abs_set(gas, init_gas)
    yield from subs_wrapper(count([pe1], num_steady), LiveTable([]))







"""
Simulatanous rocking multiple motors while detector is collecting
"""

import asyncio
import itertools

from ophyd import Signal
from bluesky import Msg
from bluesky.utils import ts_msg_hook

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp

def multi_rock_per_shot(dets):
    def build_future(status):
        p_event = asyncio.Event(**RE._loop_for_kwargs)
        loop = asyncio.get_running_loop()

        def done_callback(status=None):
            task = loop.call_soon_threadsafe(p_event.set)

        status.add_callback(done_callback)

        return asyncio.ensure_future(p_event.wait())

    ### SET THIS TO YOUR REAL HARDWARE
    # x =
    # y =
    # th = 
    
    status_objects = {}
    future_factories = {}

    theta_gen = itertools.cycle([55, 65])
    x_gen = itertools.cycle([44, 46])
    yield Msg('checkpoint')
    th_satus = yield from bps.abs_set(th, next(theta_gen))
    th_future = build_future(th_satus)
    for d in dets:
        yield from bps.trigger(d, group='detectors')
    for y_target in np.linspace(-1, 1, 5):
        y_status = yield from bps.abs_set(y, y_target)
        y_future = build_future(y_status)

        while True:
            yield Msg(
                "wait_for",
                None,
                [lambda: y_future, lambda: th_future],
                return_when="FIRST_COMPLETED",
            )
            if th_satus.done:
                th_satus = yield from bps.abs_set(th, next(theta_gen))
                th_future = build_future(th_satus)
            if y_status.done:
                break

        x_target = next(x_gen)
        x_status = yield from bps.abs_set(x, x_target)
        x_future = build_future(x_status)

        while True:
            yield Msg(
                "wait_for",
                None,
                [lambda: x_future, lambda: th_future],
                return_when="FIRST_COMPLETED",
            )
            if th_satus.done:
                th_satus = yield from bps.abs_set(th, next(theta_gen))
                th_future = build_future(th_satus)
            if x_status.done:
                break
        yield from bps.wait(group='detectors')

    # create the event!
    yield from bps.create('primary')
    ret = {}  # collect and return readings to give plan access to them
    for d in dets:
        reading = (yield from bps.read(d))
        if reading is not None:
            ret.update(reading)
    yield from bps.save()                       
    return ret

"""
xpd_configuration['area_det']=pe2c
glbl['frame_acq_time']=0.2
glbl['dk_window']=3000
RE(_configure_area_det(120))
#x = diff_x
#y = diff_y
#th = th
%time uid = RE(count([pe2c],per_shot=multi_rock_per_shot))[0]
"""





