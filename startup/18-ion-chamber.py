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
    trigger_count = Cpt(EpicsSignalRO, "TriggerCount", auto_monitor = True, kind=Kind.omitted)

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

        ttime.sleep(0.1)
        super().stage(*args, **kwargs)

    def trigger(self):
        #print("!!! Starting trigger")
        self.acq_time_start = ttime.time()
        
        # TODO: perform collection of individual amps readings based on user specified period of time
        def cb(value, old_value, **kwargs):
            #print(f"{value}, {old_value}")
            if ttime.time() > self.acq_time_start + self.expected_acq_time:
                #self.stop_signal.put(1)
                print("Ion chamber is stuck! Breaking...")
                return True
            elif value >= self.trigs_to_average and not old_value >= self.trigs_to_average:
                self.stop_signal.put(1)
                return True
            else:
                return False
            # if value == 0:  
            #     self.reset_to_zero = True
            #     return False
            # # First make sure that we see a reset trigger count = 0                
            # elif not self.reset_to_zero:
            #     return False
            # # print(f"{old_value} -> {value}\n{kwargs}")
            # # print(f"### max_counts = {self.max_counts.get()}")
            # elif int(value) < self.max_counts.get():
            #     if int(value) != int(old_value):
            #         print(f"{value} ---- {self.max_counts.get()}")
            #         print(f"{ttime.monotonic()} collecting timestamps, amps, coulombs")
            #         # self._timestamps.append(ttime.time())
            #         self._timestamps.append(kwargs["timestamp"])
            #         self._amps_list.append(self.amps.get())
            #         self._coulombs_list.append(self.coulombs.get())
            #     return False
            # else:
            #     # print(f"**** {value}")
            #     print("last addition")
            #     self._timestamps.append(kwargs["timestamp"])
            #     self._amps_list.append(self.amps.get() * A_2_NA_SCALE_FACTOR)
            #     self._coulombs_list.append(self.coulombs.get())
            #     print(f"{ttime.monotonic()} finished collecting")
            #     self.timestamps.put(list(self._timestamps))
            #     self.amps_list.put(list(self._amps_list))
            #     self.coulombs_list.put(list(self._coulombs_list))
            #     print(f"^^^ {len(list(self._amps_list))}")

            #     self.amps_mean.put(np.mean(self._amps_list))
            #     self.coulombs_mean.put(np.mean(self._coulombs_list))

            #     self.stop_signal.put(1)
            #     self.reset_to_zero = False
                
            #     print(f"{ttime.monotonic()} finished single averaging set")
            #     return True


        # Make sure all averages are reset to zero.
        self.clear_averages.put(1)

        st = SubscriptionStatus(self.trigger_count, callback=cb, run=False)
        self.initiate.put(1)

        #print("!!! Initiated")

        return st

    def unstage(self, *args, **kwargs):
        super().unstage(*args, **kwargs)
        #self.stop_signal.put(1)
        # self.stop_signal.put(0)


ion_chamber = IonChamber("XF:28IDC-BI{IC101}", name="ion_chamber")
