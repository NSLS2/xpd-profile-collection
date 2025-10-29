### This plan is named 9999-* to have it after 999-load.py where xpdacq is configured ####
###  Created by Sanjit Ghose 28th Aug, 2017 during new BS/xpdAcq/an upgrades ########

from xpdacq.beamtime import _configure_area_det
import os
import numpy as np
import itertools
import bluesky.plans as bp
import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp

from bluesky.plans import (scan, count, list_scan, adaptive_scan)
from bluesky.preprocessors import subs_wrapper, reset_positions_wrapper
from bluesky.callbacks import LiveTable, LivePlot
from bluesky.plan_tools import print_summary

####  Plan to run Gas/RGA2 over xpdacq protocols of samples ########

gas.gas_list = ['He', 'N2', 'CO2', 'Air']


def gas_plan(gas_in, rga_masses=['mass1', 'mass2', 'mass3', 'mass4', 'mass5', 'mass6']):
    """The plan to switch gases.

    Parameters
    ----------
    gas_in : string
        e.g., 'He', default is 'He'
        These gas must be in `gas.gas_list` but they may be in any order.
    rga_masses: list, optional
        a list of rga masses appearing in a live table

    Examples
    --------

    >>> RE(gas_plan(gas_in='He', rga_masses=['mass4', 'mass6']))
    """
    print('Warning: check the gas list!')

    for i in range(1, 9+1):
        getattr(rga, f'mass{i}').kind = 'normal'

    for m in rga_masses:
        getattr(rga, m).kind = 'hinted'

    ## switch gas
    yield from bps.mv(gas, gas_in)

    ## ScanPlan you need
    yield from bp.count([gas.current_gas, rga])


def gas_plan_with_detector(gas_in, rga_masses=['mass1', 'mass2', 'mass3', 'mass4', 'mass5', 'mass6'], det=None, exp_time=5, num_exp=1, delay=1):
    """The plan to switch gases with a detector.

    Parameters
    ----------
    gas_in : string
        e.g., 'He', default is 'He'
        These gas must be in `gas.gas_list` but they may be in any order.
    rga_masses: list, optional
        a list of rga masses appearing in a live table
    det : ophyd obj, optional
        detector to use
    exp_time : float, optional
        exposure time in seconds
    num_exp : integer, optional
        number of exposures
    delay : float, optional
        delay between exposures in seconds

    Examples
    --------

    >>> RE(gas_plan_with_detector(gas_in='He', rga_masses=['mass4', 'mass6']))
    """
    if det is None:
        det = pe1c

    print('Warning: check the gas list!')

    for i in range(1, 9+1):
        getattr(rga, f'mass{i}').kind = 'normal'

    for m in rga_masses:
        getattr(rga, m).kind = 'hinted'

    det.stats1.kind = 'hinted'
    det.stats1.total.kind = 'hinted'

    ## switch gas
    yield from bps.mv(gas, gas_in)

    # configure the exposure time first
    _configure_area_det(exp_time)   # secs of exposure time

    ## ScanPlan you need
    yield from bp.count([gas.current_gas, rga, det], num=num_exp, delay=delay)


def run_and_save(sample_num = 0):
    data_dir = "/direct/XF28ID2/pe2_data/xpdUser/tiff_base/"
    file_name = data_dir + "sample_num_" + str(sample_num) + ".csv"
    xrun(sample_num, gas_plan)
    h = db[-1]
    tb = h.table()
    tb.to_csv(path_or_buf =file_name, columns = ['time', 'gas_current_gas', 'rga_mass1',
                              'rga_mass2', 'rga_mass3', 'rga_mass4', 'rga_mass5',
                              'rga_mass6', 'rga_mass7', 'rga_mass8', 'rga_mass9'])

    integrate_and_save_last()
