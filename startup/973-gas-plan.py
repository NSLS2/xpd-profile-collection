import numpy as np
import bluesky.plans as bp
import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp

from bluesky.callbacks import LiveTable, LivePlot
from xpdacq.beamtime import (_configure_area_det, shutter_step,
                             open_shutter_stub, close_shutter_stub,
                             _nstep)
from xpdacq.xpdacq_conf import xpd_configuration

####  Plan to run Gas/RGA2 over xpdacq protocols of samples ########

gas.gas_list = ['He', 'N2', 'CO2', 'Air']  # gas is set during the startup
default_mass_list = ['mass1', 'mass2', 'mass3', 'mass4', 'mass5', 'mass6']


def set_gas(gas_in):
    """short plan to set the gas"""
    yield from bps.mv(gas, gas_in)


def configure_gas_mass_hint(mass_list):
    """configure hints on gas device"""
    print('Warning: check the gas list!')
    for i in range(1, 9+1):
        getattr(rga, f'mass{i}').kind = 'normal'
    for m in mass_list:
        getattr(rga, m).kind = 'hinted'

#NOTE: both plans are transient, they should really be Tramp and tseries
#with user specified detectors.

def Tramp_gas_plan(detectors, gas_in, exp_time, Tstart, Tstop, Tstep,
                   rga_masses=default_mass_list):
    """
    Tramp-type scan with rga gas reading

    Parameters
    ----------
    detectors: list
        List of detectors will be triggered and recored.
    gas_in : string
        e.g., 'He', default is 'He'
        These gas must be in `gas.gas_list` but they may be in any order.
    exp_time : float, optional
        exposure time in seconds
    Tstart : float
        starting point of temperature sequence.
    Tstop : float
        stoping point of temperature sequence.
    Tstep : float
        step size between Tstart and Tstop of this sequence.
    rga_masses: list, optional
        a list of rga masses will be appearing in a live table

    Examples
    --------
    >>> plan = Tramp_gas_plan([pe1c, rga], 'He', 5, 300, 350, 5)
    >>> xrun(<sample ind>, plan)
    """
    ## configure hints on gas device
    configure_gas_mass_hint(rga_masses)

    ## switch gas
    yield from set_gas(gas_in)

    # configure the exposure time first
    (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exp_time)
    (Nsteps, computed_step_size) = _nstep(Tstart, Tstop, Tstep)
    area_det = xpd_configuration['area_det']
    temp_controller = xpd_configuration['temp_controller']
    xpdacq_md = {'sp_time_per_frame': acq_time,
                 'sp_num_frames': num_frame,
                 'sp_requested_exposure': exp_time,
                 'sp_computed_exposure': computed_exposure,
                 'sp_type': 'Tramp',
                 'sp_startingT': Tstart,
                 'sp_endingT': Tstop,
                 'sp_requested_Tstep': Tstep,
                 'sp_computed_Tstep': computed_step_size,
                 'sp_Nsteps': Nsteps,
                 'sp_plan_name': 'Tramp'}
    plan = bp.scan(detectors, temp_controller, Tstart, Tstop,
                   Nsteps, per_step=shutter_step, md=xpdacq_md)
    plan = bpp.subs_wrapper(plan, LiveTable(detectors))
    yield from plan


def tseries_gas_plan(detectors, gas_in, exp_time, delay=1, num_exp=1,
                     rga_masses=default_mass_list):
    """
    tseries-type scan with rga gas reading

    Parameters
    ----------
    detectors: list
        List of detectors will be triggered and recored.
    gas_in : string
        e.g., 'He', default is 'He'
        These gas must be in `gas.gas_list` but they may be in any order.
    exp_time : float, optional
        exposure time in seconds
    num_exp : integer, optional
        number of exposures
    delay : float, optional
        delay between exposures in seconds
    rga_masses: list, optional
        a list of rga masses appearing in a live table

    Examples
    --------

    >>> plan = tseries_gas_plan([pe1c, rga], 'He', 5, 10, 2)
    >>> xrun(<sample ind>, plan)
    """
    ## configure hints on gas device
    configure_gas_mass_hint(rga_masses)

    ## switch gas
    yield from set_gas(gas_in)

    # configure the exposure time first
    (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exp_time)
    real_delay = max(0, delay - computed_exposure)
    period = max(computed_exposure, real_delay + computed_exposure)
    print('INFO: requested delay = {}s  -> computed delay = {}s'
          .format(delay, real_delay))
    print('INFO: nominal period (neglecting readout overheads) of {} s'
          .format(period))
    xpdacq_md = {'sp_time_per_frame': acq_time,
                 'sp_num_frames': num_frame,
                 'sp_requested_exposure': exp_time,
                 'sp_computed_exposure': computed_exposure,
                 'sp_plan_name': 'tseries'}

    plan = bp.count(detectors, num_exp, delay, md=xpdacq_md)
    plan = bpp.subs_wrapper(plan, LiveTable(detectors))
    def inner_shutter_control(msg):
        if msg.command == 'trigger':
            def inner():
                yield from open_shutter_stub()
                yield msg
            return inner(), None
        elif msg.command == 'save':
            return None, close_shutter_stub()
        else:
            return None, None
    plan = bpp.plan_mutator(plan, inner_shutter_control)
    yield from plan

