from ophyd import (Device,
                   Component as Cpt,
                   EpicsSignal, EpicsSignalRO, Signal)
from bluesky.preprocessors import (
    run_decorator, stage_decorator, finalize_decorator,
    monitor_during_decorator)

import bluesky.plan_stubs as bps
from bluesky.utils import short_uid
import pandas as pd
import time
import itertools
from bluesky.preprocessors import subs_decorator
#### Funtions for tseries type run with shuuter control and triggering other Ophyd Devices
from xpdacq.beamtime import open_shutter_stub, close_shutter_stub

import bluesky.plans as bp
import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp

def inner_shutter_control(msg):
    if msg.command == "trigger":
        def inner():
            yield from open_shutter_stub()
            yield msg
        return inner(), None
    elif msg.command == "save":
        return None, close_shutter_stub()
    else:
        return None, None



class CurrentSetterEpicSignal(EpicsSignal):
    def stop(self, success=False):
        self.parent.enabled.put(0)


class CurrentEnable(EpicsSignal):
    def stop(self, success=False):
        self.put(0)


class FlashRampInternals(Device):
    next_sp = Cpt(EpicsSignalRO, 'I:Next-SP')
    next_min = Cpt(EpicsSignalRO, 'I:Next-Min')
    sp1 = Cpt(EpicsSignalRO, 'I:OutMain-SP1')
    sp = Cpt(EpicsSignalRO, 'I:OutMain-SP')
    scheduler = Cpt(EpicsSignalRO, 'I:Scheduler')


class FlakySignal(EpicsSignal):
    def get(self, *args, **kwargs):
        N = 5
        for j in range(N):
            v = super().get(*args, **kwargs)
            if v is not None:
                return v
        else:
            raise RuntimeError(
                f"{self}.get got {N} None readings?!?")
    

class FlashPower(Device):
    # stuff from PSU sorensonxg850.template
    current = Cpt(EpicsSignalRO, 'I-I', kind='hinted')
    voltage = Cpt(EpicsSignalRO, 'E-I', kind='hinted')

    current_sp = Cpt(CurrentSetterEpicSignal,
                     'I-Lim',
                     write_pv='I-Lim')
    voltage_sp = Cpt(FlakySignal,
                     'E:OutMain-RB',
                     write_pv='E:OutMain-SP',
                     tolerance=.01)

    enabled = Cpt(CurrentEnable,
                  'Enbl:OutMain-Sts',
                  write_pv='Enbl:OutMain-Cmd',
                  kind='omitted',
                  string=True)

    remote_lockout = Cpt(EpicsSignal,
                         'Enbl:Lock-Sts',
                         write_pv='Enbl:Lock-Cmd',
                         string=True,
                         kind='config')

    foldback_mode = Cpt(EpicsSignal,
                        'Mode:Fold-Sts',
                        write_pv='Mode:Fold-Sel',
                        string=True,
                        kind='config')

    over_volt_val = Cpt(EpicsSignal,
                        'E:OverProt-RB',
                        write_pv='E:OverProt-SP',
                        kind='config')

    protection_reset = Cpt(
        EpicsSignal, 'Reset:FoldProt-Cmd',
        kind='omitted')

    status = Cpt(EpicsSignalRO, 'Sts:Opr-Sts')

    # stuff from ramp_rate.db
    ramp_rate = Cpt(EpicsSignal,
                    'I-RampRate-RB',
                    write_pv='I-RampRate-I',
                    kind='config')

    delta = Cpt(EpicsSignalRO,
                'I-Delta',
                kind='config')

    mode = Cpt(EpicsSignal, 'UserMode-I',
               string=True,
               kind='config')

    ramp_done = Cpt(EpicsSignalRO,
                    'CurrRamp-Done',
                    kind='omitted')

    _internals = Cpt(FlashRampInternals, '', kind='omitted')

    def unstage(self):
        ret = super().unstage()
        self.enabled.put(0)
        return ret

    def stop(self, success=False):
        # for safety
        self.enabled.put(0)


class KeithlyMMChannel(Device):
    chanafunc = Cpt(EpicsSignal, "ChanAFunc")
    chanaresults = Cpt(EpicsSignal, "ChanAResults")
    chanatimes = Cpt(EpicsSignal, "ChanATimes")
    chanaenable = Cpt(EpicsSignal, "ChanAEnable")

    chanbfunc = Cpt(EpicsSignal, "ChanBFunc")
    chanbresults = Cpt(EpicsSignal, "ChanBResults")
    chanbtimes = Cpt(EpicsSignal, "ChanBTimes")
    chanbenable = Cpt(EpicsSignal, "ChanBEnable")


class KeithlyMM(Device):
    # these are the ones documented in the readme
    readtype = Cpt(EpicsSignal, "ReadType", kind='config',
                   string=True)
    # the readme says you get one or the other which seems odd?
    readcurr = Cpt(EpicsSignal, "ReadCurr", kind='hinted')
    readvolt = Cpt(EpicsSignal, "ReadVolt", kind='hinted')

    synctype = Cpt(EpicsSignal, "SyncType", kind='config')

    # other records in db file, not sure what to do with
    test = Cpt(EpicsSignal, "test", kind='omitted')

    timetotal = Cpt(EpicsSignal, "TimeTotal", kind='omitted')

    # this looks like a way to buffer in device?
    scaninterval = Cpt(EpicsSignal, "ScanInterval", kind='omitted')
    numchannels = Cpt(EpicsSignal, "NumChannels", kind='omitted')
    scancount = Cpt(EpicsSignal, "ScanCount", kind='omitted')

    func = Cpt(EpicsSignal, "Func", kind='omitted')

    # these seems important?
    scanresults = Cpt(EpicsSignal, "ScanResults", kind='omitted')
    timestamp = Cpt(EpicsSignal, "Timestamp", kind='omitted')
    timestampfrac = Cpt(EpicsSignal, "TimestampFrac", kind='omitted')
    timestampint = Cpt(EpicsSignal, "TimestampInt", kind='omitted')

    readtypeseq = Cpt(EpicsSignal, "ReadTypeSeq", kind='omitted')


MM = KeithlyMM('XF:28IDC-ES{KDMM6500}', name='MM')
flash_power = FlashPower('XF:28ID2-ES:1{PSU:SRS}', name='flash_power')

[setattr(getattr(flash_power._internals, n), 'kind', 'hinted') for n in flash_power._internals.component_names]
[setattr(getattr(flash_power._internals, n), 'name', n) for n in flash_power._internals.component_names]
flash_power._internals.kind = 'omitted'

flash_power._internals.scheduler.kind = 'omitted'
flash_power.current.name = 'I'
flash_power.voltage.name = 'V'
flash_power.current_sp.name = 'Isp'


def _setup_mm(mm_mode):

    if mm_mode == 'Current':
        monitor_during = [MM.readcurr]
        yield from bps.mv(MM.readtype, mm_mode)        
    elif mm_mode == 'Voltage':
        monitor_during = [MM.readvolt]
        yield from bps.mv(MM.readtype, mm_mode)                
    elif mm_mode == 'none':
        monitor_during = []
    else:
        raise ValueError(f'you passed mm_mode={mm_mode} '
                         'but the value must be one of '
                         '{"Current", "Voltage"}')

    return monitor_during


def _inner_loop(dets, exposure_count, delay, deadline, per_step,
                stream_name, done_signal=None):
    """Helper plan for the inner loop of the sinter plans

    This is very much like the repeat plan, but has less
    delay input types and more logic about finishing on a deadline.

    Parameters
    ----------
    dets : List[OphydObj]
        The detectors passed to per_step

    exposure_count : int
        The maximum number of times to call per_step

    delay : float
        The target delay between subsequent starts of per_step.

    deadline : float
         Wall time to be done by.  Under no condition take longer
         than this to completely run through plan.

    per_step : Callable[List[OphydObj], Optional[str]] -> Generator[Msg]
        The plan to run 'per step'.

        This is the signature of triger_and_read

    primary : str
        Passed to per_step

    done_signal : Signal, optional
        If passed, will exit early when goes to 1
    """
    if done_signal is not None:

        from bluesky.utils import first_key_heuristic 
        signal_key = first_key_heuristic(done_signal)
        def _check_signal():
            val = yield from bps.read(done_signal)
            if val is None:
                return True
            val = val[signal_key]['value']
            return bool(val)
    else:
        _check_signal = None

    for j in range(exposure_count):
        start_time = time.monotonic()

        yield from bps.checkpoint()
        # if things get bogged down in data collection, bail early!
        if start_time > deadline:
            print(f'{start_time} > {deadline} bail!')
            break

        # this triggers the cameras
        yield from per_step(dets, stream_name)

        stop_time = time.monotonic()
        exp_actual = stop_time - start_time
        sleep_time = delay - exp_actual

        yield from bps.checkpoint()
        if _check_signal is not None:
            done = yield from _check_signal()
            if done:
                return
        if stop_time + sleep_time > deadline:
            yield from bps.sleep(deadline - stop_time)
            return
        else:
            yield from bps.sleep(delay - exp_actual)


def flash_step(VIT_table, total_exposure, md, *,
               dets=None,
               delay=1,
               mm_mode='Current',
               per_step=None,
               control_shutter=True):
    """
    Run a step-series of current/voltage.

    The current/voltage profile will look something like: ┌┐_┌┐_┌┐_

    Parameters
    ----------
    VIT_table : pd.DataFrame
       The required columns are {"I", "V", "t"} which are
       the current, voltage, and hold time respectively.

    total_exposure : float
        The total exposure time for the detector.

        This is set via _configure_area_detector which is
        implicitly coupled to xpd_configuration['area_det']

    md : dict
        The metadata to put into the runstart.  Will have
        some defaults added

    dets : List[OphydObj], optional
        The detectors to trigger at each point.

        If None, defaults to::

          [xpd_configuration['area_det']]

    delay : float, optional
        The time lag between subsequent data acquisition

    mm_mode : {'Current', 'Voltage'}, optional
        The thing to measure from the Keithly multimeter.

    per_step : Callable[List[OphydObj], Optional[str]] -> Generator[Msg], optional
        The inner-most data acquisition loop.

        This plan will be repeated as many times as possible (with
        the target *delay* between starting the plan.

        If the plan take longer than *delay* to run it will
        immediately be restarted.

    control_shutter : bool, optional
        If the plan should try to open and close the shutter

        defaults to True
    """
    if per_step is None:
        per_step = bps.trigger_and_read
    if total_exposure > delay:
        raise RuntimeError(
            f"You asked for total_exposure={total_exposure} "
            f"with a delay of delay={delay} which is less ")    
    if dets is None:
        dets = [xpd_configuration['area_det']]
    
    all_dets = dets + [flash_power, eurotherm]
    req_cols = ['I', 'V', 't']
    if not all(k in VIT_table for k in req_cols):
        raise ValueError(f"input table must have {req_cols}")

    monitor_during = yield from _setup_mm(mm_mode)

    VIT_table = pd.DataFrame(VIT_table)
    # TODO put in default meta-data
    md.setdefault('hints', {})
    md['hints'].setdefault('dimensions', [(('time',), 'primary')])
    md['plan_name'] = 'flash_step'
    md['plan_args'] = {'VIT_table': {k: v.values for k,v in VIT_table.items()},
                       'delay': delay,
                       'total_exposure': total_exposure}
    md['detectors'] = [det.name for det in dets]                       

    @subs_decorator(bec)
    # paranoia to be very sure we turn the PSU off
    @finalize_decorator(lambda: bps.mov(flash_power.enabled, 0))
    # this arms the detectors
    @stage_decorator(all_dets)
    # this sets up the monitors of the multi-meter
    @monitor_during_decorator(monitor_during)
    # this opens the run and puts the meta-data in it
    @run_decorator(md=md)
    def flash_step_field_inner():
        # set everything to zero at the top
        yield from bps.mv(flash_power.current_sp, 0,
                          flash_power.voltage_sp, 0)
        # put in "Duty Cycle" mode so current changes immediately
        yield from bps.mv(flash_power.mode, 'Duty-Cycle')

        # take a measurement on the way in
        yield from per_step(all_dets, 'primary')

        # turn it on!
        yield from bps.mv(flash_power.enabled, 1)

        last_I = last_V = np.nan
        for _, row in VIT_table.iterrows():
            tau = row['t']
            exposure_count = int(max(1, tau // delay))
            print('initial per step call')
            yield from per_step(all_dets, 'primary')
            next_I = row['I']
            next_V = row['V']
            print('set IV')
            if next_I != last_I:
                yield from bps.mv(flash_power.current_sp, next_I)
                last_I = next_I
            if next_V != last_V:
                yield from bps.mv(flash_power.voltage_sp, next_V)
                last_V = next_V                
            print('finsh setting IV')
            deadline = time.monotonic() + tau
            yield from _inner_loop(all_dets, exposure_count,
                                   delay, deadline, per_step,
                                   'primary')
            print('finished inner loop call')

        print('final shot')
        # take a measurement on the way out
        yield from per_step(all_dets, 'primary')

        print('turning off')
        # turn it off!
        # there are several other places we turn this off, but better safe
        yield from bps.mv(flash_power.enabled, 0)

    # HACK to get at global state
    yield from _configure_area_det(total_exposure)
    plan = flash_step_field_inner()
    if control_shutter:
        return (yield from bpp.plan_mutator(
                    plan, inner_shutter_control))
    else:
        return (yield from plan)


def flash_ramp(start_I, stop_I, ramp_rate, voltage,
               total_exposure,
               md,
               *,
               dets=None,
               delay=1, mm_mode='Current',
               hold_time=0,
               per_step=None,
               control_shutter=True):
    """
    Run a current ramp

    The current profile will look something like: /|

    Parameters
    ----------
    start_I, stop_I : float
        The start and end points of the current ramp

        In mA

    ramp_rate : float
        The rate of current change.

        In mA/min

    voltage : float
        The voltage limit through the current ramp.

    total_exposure : float
        The total exposure time for the detector.

        This is set via _configure_area_detector which is
        implicitly coupled to xpd_configuration['area_det']

    md : dict
        The metadata to put into the runstart.  Will have
        some defaults added

    dets : List[OphydObj], optional
        The detectors to trigger at each point.

        If None, defaults to::

          [xpd_configuration['area_det']]

    delay : float, optional
        The time lag between subsequent data acquisition

    mm_mode : {'Current', 'Voltage'}, optional
        The thing to measure from the Keithly multimeter.

    hold_time : float, optional
       How long to hold at the top of the ramp, defalts to 0

    per_step : Callable[List[OphydObj], Optional[str]] -> Generator[Msg], optional
        The inner-most data acquisition loop.

        This plan will be repeated as many times as possible (with
        the target *delay* between starting the plan.

        If the plan take longer than *delay* to run it will
        immediately be restarted.

    control_shutter : bool, optional
        If the plan should try to open and close the shutter

        defaults to True
    """
    if per_step is None:
        per_step = bps.trigger_and_read
    if dets is None:
        dets = [xpd_configuration['area_det']]
    if total_exposure > delay:
        raise RuntimeError(
            f"You asked for total_exposure={total_exposure} "
            f"with a delay of delay={delay} which is less ")
    # mA -> A
    start_I = start_I / 1000
    stop_I = stop_I / 1000
    if stop_I < start_I:
        raise ValueError("IOC can not ramp backwards")
    fudge_factor = 1
    ramp_rate *= fudge_factor
    all_dets = dets + [flash_power, eurotherm]
    monitor_during = yield from _setup_mm(mm_mode)

    expected_time = abs((stop_I - start_I) / (ramp_rate/(fudge_factor*60*1000)))
    exposure_count = int(max(1,  expected_time // delay))

    md.setdefault('hints', {})
    md['hints'].setdefault('dimensions', [(('time',), 'primary')])
    md['plan_name'] = 'flash_ramp'
    md['plan_args'] = {'start_I': start_I, 'stop_I': stop_I,
                       'ramp_rate': ramp_rate, 'voltage': voltage,
                       'delay': delay,
                       'total_exposure': total_exposure}
    md['detectors'] = [det.name for det in dets]

    @subs_decorator(bec)
    # paranoia to be very sure we turn the PSU off
    @finalize_decorator(lambda: bps.mov(flash_power.enabled, 0))
    # this arms the detectors
    @stage_decorator(all_dets)
    # this sets up the monitors of the multi-meter
    @monitor_during_decorator(monitor_during)
    # this opens the run and puts the meta-data in it
    @run_decorator(md=md)
    def flash_ramp_inner():
        # set everything to zero at the top
        yield from bps.mv(flash_power.current_sp, 0,
                          flash_power.voltage_sp, 0,
                          flash_power.ramp_rate, ramp_rate)
        # put in "Duty Cycle" mode so current changes immediately
        yield from bps.mv(flash_power.mode, 'Duty-Cycle')
        # take one shot on the way in
        yield from per_step(all_dets, 'primary')
        # turn it on!
        yield from bps.mv(flash_power.enabled, 1)

        # TODO
        # what voltage limit to start with ?!
        yield from bps.mv(flash_power.current_sp, start_I,
                          flash_power.voltage_sp, voltage)
        # put in "Current Ramp" to start the ramp
        yield from bps.mv(flash_power.mode, 'Current Ramping')
        # set the target to let it go
        gid = short_uid()
        yield from bps.abs_set(flash_power.current_sp, stop_I,
                               group=gid)
        yield from bps.mv(flash_power.voltage_sp, voltage)
        

        yield from _inner_loop(all_dets, exposure_count, delay,
                               time.monotonic() + expected_time * 1.1,
                               per_step, 'primary',
                               done_signal=flash_power.ramp_done)

        if hold_time > 0:
            yield from _inner_loop(all_dets,
                                   int(max(1, hold_time // delay)),
                                   delay,
                                   time.monotonic() + hold_time,
                                   per_step, 'primary')
        
        # take one shot on the way out
        yield from per_step(all_dets, 'primary')
        yield from bps.wait(gid)
        # turn it off!
        # there are several other places we turn this off, but better safe
        yield from bps.mv(flash_power.enabled, 0)
        
    # HACK to get at global state
    yield from _configure_area_det(total_exposure)        
    plan = flash_ramp_inner()
    if control_shutter:
        return (yield from bpp.plan_mutator(
                    plan, inner_shutter_control))
    else:
        return (yield from plan)

def sawtooth_factory(motor, start, stop, step_size):
    """Generate a per-step function that move the motor in a sawtooth



    It is assumed to be near the start on the first step where this is
    called.

    The motion will look like /|/|/|/|

    Parameter
    ---------
    motor : setabble
        The motor to move.

    start, stop : float
        The range to move the motor between

    step_size : float
        The size of steps to take between the measurements

    Returns
    -------
    per_step : Callable[List[OphydObj], str] -> Generator[Msg]
    """
    if stop < start:
        start, stop = stop, start

    num_pos = int((stop - start) // step_size)
    j = itertools.count()
    last_group = None

    def x_motion_per_step(dets, stream_name):
        nonlocal last_group
        if last_group is not None:
            yield from bps.wait(last_group)
        yield from bps.trigger_and_read(dets, stream_name)
        last_group = short_uid()
        target = start + step_size * (next(j) % num_pos)
        yield from bps.abs_set(motor, target, group=last_group)

    return x_motion_per_step


def pyramid_factory(motor, start, stop, step_size):
    r"""Generate a per-step function that moves the motor in triangle wave

    It is assumed to be near the start on the first step where this is
    called.

    The motion will look like /\/\/\/\

    Parameter
    ---------
    motor : setabble
        The motor to move.

    start, stop : float
        The range to move the motor between

    step_size : float
        The size of steps to take between the measurements

    Returns
    -------
    per_step : Callable[List[OphydObj], str] -> Generator[Msg]
    """
    if stop < start:
        start, stop = stop, start
    last_group = None
    last_pos = start

    def x_motion_per_step(dets, stream_name):
        nonlocal last_group
        nonlocal last_pos
        nonlocal step_size

        if last_group is not None:
            yield from bps.wait(last_group)

        yield from bps.trigger_and_read(dets, stream_name)

        last_group = short_uid()

        if not start < last_pos + step_size < stop:
            step_size *= -1
        last_pos += step_size

        yield from bps.abs_set(motor, last_pos, group=last_group)

    return x_motion_per_step
