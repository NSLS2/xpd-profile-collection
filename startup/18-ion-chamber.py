import time as ttime
from collections import deque

import numpy as np
from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO, Kind, Signal
from ophyd.status import SubscriptionStatus

A_2_NA_SCALE_FACTOR = 1000000000


class IonChamber(Device):
    amps = Cpt(EpicsSignalRO, "Amps", kind=Kind.omitted)
    coulombs = Cpt(EpicsSignalRO, "Coulombs", kind=Kind.omitted)
    # TODO: Update this when type of readback is fixed from string to float
    # period = Cpt(EpicsSignal, read_pv="ReadPeriod", write_pv="SetPeriod", add_prefix=("read_pv", "write_pv"), kind=Kind.config)
    period = Cpt(EpicsSignal, "SetPeriod", kind=Kind.config)
    period_rb = Cpt(EpicsSignal, "ReadPeriod", kind=Kind.omitted)
    trigger_count = Cpt(EpicsSignalRO, "TriggerCount", kind=Kind.omitted)
    num_trigs_avg = Cpt(EpicsSignalRO, "NumTrigsSeen", auto_monitor = True, kind=Kind.omitted)

    initiate = Cpt(EpicsSignal, "Init", kind=Kind.omitted)  # Initiate button
    stop_signal = Cpt(EpicsSignal, "Abort", kind=Kind.omitted)  # Stop button
    save_signal = Cpt(EpicsSignal, "Save", kind=Kind.omitted)  # Save button
    scale_factor = Cpt(EpicsSignal, "ScaleFactor", kind=Kind.config) # Scale factor for average output
    clear_averages = Cpt(EpicsSignal, "ResetCurrentSum", kind=Kind.omitted)

    amps_mean = Cpt(EpicsSignal, "AverageCurrent", kind=Kind.hinted)
    #coulombs_mean = Cpt(EpicsSignal, "AverageCoulombs", kind=Kind.hinted)
    coulombs_mean = Cpt(EpicsSignal, "AverageCoulombs", kind=Kind.omitted)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trigs_to_average = 20
        self.timeout_tolerance = 2
        self.stage_sigs["scale_factor"] = A_2_NA_SCALE_FACTOR


    def stage(self, *args, **kwargs):
        self.stop_signal.put(0)
        self.expected_acq_time = self.period.get() * self.trigs_to_average + self.timeout_tolerance
        # while self.period_rb.get() != self.period.get():
        #     ttime.sleep(0.1)

        ttime.sleep(0.1)
        super().stage(*args, **kwargs)

    def trigger(self):
        
        def cb(value, old_value, **kwargs):
            if value >= self.trigs_to_average and not old_value >= self.trigs_to_average:
                self.stop_signal.put(1)
                return True
            else:
                return False

        # Make sure all averages are reset to zero.
        self.clear_averages.put(0)

        st = SubscriptionStatus(self.num_trigs_avg, callback=cb, run=False)
        self.initiate.put(1)

        return st

    def unstage(self, *args, **kwargs):
        super().unstage(*args, **kwargs)
        #self.stop_signal.put(1)
        # self.stop_signal.put(0)


ion_chamber = IonChamber("XF:28IDC-BI{IC101}", name="ion_chamber")
