from random import sample

from xpdacq.beamtime import configure_area_det
from xpdacq.xpdacq import periodic_dark
from xpdacq.xpdacq import _inject_qualified_dark_frame_uid, _inject_calibration_md, _inject_analysis_stage
import bluesky.preprocessors as bpp

def ct_dark(dets: list, exposure: float):
    return (yield from periodic_dark(ct(dets, exposure)))
    ## needs to add close shutter
    

    
# Issues on 2025/11/10 --> All fixed by CHL and HZ:
#     To add: 
#           1. close shutter (v)
#           2. Auto sbustract dark (v)
#           3. Metadata (v)
#     To check: 
#           1. configure detector (v)



## A pre-plan to configure the area detector
def _pre_plan(dets, exposure, frame_acq_time=None):
    """Handle detector exposure time + xpdan required metadata"""

    try:
        xpd_configuration["area_det"] = dets[0]

    except (NameError, KeyError):
        pass

    
    ## Change frame acquisition time (not using glbl)
    if (type(frame_acq_time) is float) or (type(frame_acq_time) is int):
        for det in dets:
            yield from bps.mv(det.cam.acquire_time, frame_acq_time)


    # if 'pilatus1' not in dets[0].name:
    #     raise ValueError('This plan is for pilatus but not pilatus in dets')

    # setting up area_detector
    # from xpdacq.beamtime import _configure_area_det
    for ad in (d for d in dets if hasattr(d, "cam")):
        (num_frame, acq_time, computed_exposure) = yield from configure_area_det(ad, exposure, frame_acq_time)
    # else:
    #     acq_time = 0
    #     computed_exposure = exposure
    #     num_frame = 0

    acq_time = float(acq_time)
    computed_exposure = float(computed_exposure)
    num_frame = int(num_frame)

    sp = {
        "time_per_frame": acq_time,
        "num_frames": num_frame,
        "requested_exposure": exposure,
        "computed_exposure": computed_exposure,
        "type": "generator",
        "uid": str(uuid.uuid4()),
        "plan_name": "bps.trigger",
    }

    _md = ChainMap(
        {
            "sp_time_per_frame": acq_time,
            "sp_num_frames": num_frame,
            "sp_requested_exposure": exposure,
            "sp_computed_exposure": computed_exposure,
            "sp_type": "bps.trigger",
            "sp_uid": str(uuid.uuid4()),
            "sp_plan_name": "trigger",
            "sp_detector": dets[0].name,
            "detectors": [area_det.name for area_det in dets],
            # "data_keys": "pe1c_image",
        },
    )

    # update md
    # _md.update({"sp": sp, **{f"sp_{k}": v for k, v in sp.items()}})
    _md.update({"sp": sp, })
    print(_md)

    return _md




def trigger_areaDet(dets, exposure, stream_name, md, no_dark, jogging=[], frame_acq_time=None, user_config={}):
    _md = md or {}
    # _md['sample_name'] = sample_name
    sp_md = yield from _pre_plan(dets, exposure, frame_acq_time=frame_acq_time)
    sp_md["sp_plan_name"] = "trigger_areaDet",
    _md.update(sp_md)
    _md.update({'user_config':user_config})

    if len(jogging) == 3:
        _md["plan_name"] = "jog_areaDet"
        _md["jog_md"] = {"start": jogging[1], "stop": jogging[2], "motor": jogging[0].name}
        jogging_motor = jogging[0]
    else:
        jogging_motor = sample_y

    # if 'pilatus' in dets[0].name:
    #     motors = [Grid_X, Grid_Y, Grid_Z]
    #     motors_field = ['Grid_X', 'Grid_Y', 'Grid_Z']
    
    # elif 'pe1' in dets[0].name:
    #     motors = [Det_1_X, Det_1_Y, Det_1_Z]
    #     motors_field = ['Det_1_X', 'Det_1_Y', 'Det_1_Z']
    
    # else:
    #     print(f'pilatus or pe1 not in {dets[0].name = }, set motors and motors_field to []')
    #     motors = []
    #     motors_field = []



    # nonlocal start, stop
    @bpp.reset_positions_decorator([jogging_motor.velocity])
    def inner_jog(gp, motor, start, stop):
        yield from bps.mv(motor, start)  # got to initial position
        yield from bps.mv(motor.velocity, abs(stop-start)/(exposure), timeout=1)  # set velocity
        # gp = short_uid("rocker")
        yield from bps.abs_set(motor, stop, group=gp)  # set motor to move towards end


    # table = LiveTable(motors_field, stream_name=stream_name, default_prec=0)
    # @bpp.subs_decorator(table)
    @bpp.stage_decorator(dets)
    @bpp.run_decorator(md=_md)
    def trigger_and_wait() -> MsgGenerator:
        for det in dets:

            nonlocal jogging
            if len(jogging) == 3:
                print(f'Star to jog using {jogging[0].name} from {jogging[1]} mm to {jogging[2]} mm')
                gp = short_uid("rocker")
                yield from inner_jog(gp, motor=jogging[0], start=jogging[1], stop=jogging[2])

            yield from bps.trigger(det, wait=True)
            yield from bps.create(name=stream_name)
            yield from bps.read(det)
            # yield from bps.read(motors[0])
            # yield from bps.read(motors[1])
            # yield from bps.read(motors[2])
            yield from bps.save()
    
    if not no_dark:
        yield from periodic_dark(trigger_and_wait())
    else:
        yield from open_shutter_stub()
        yield from trigger_and_wait()
        yield from close_shutter_stub()
        


from xpdacq.xpdacq import (_inject_qualified_dark_frame_uid, 
                           _inject_calibration_md, 
                           _inject_analysis_stage, 
                           _validate_dark, 
                           _auto_load_calibration_file, 
)

def scan_with_dark(dets: list, 
                   exposure: float=0.1, 
                   sample_ID: int=0, 
                   sample_info: dict={}, 
                   md: dict={}, 
                   stream_name: str='primary', 
                   no_dark: bool=False, 
                   jogging:list=[], 
                   frame_acq_time: float=0.1, 
                   user_config: dict={},
                   ):
    """Take a scan with an aera detector for PDF or XRD

    Args:
        dets (list): 
            list of detector ophyd object, e.g., [piatus1] or [pe1c]

        exposure (float, optional): 
            total exposure (measurement) time in seconds.  
            Defaults to 0.1.

        sample_ID (int, optional): 
            sample index returned in bt.list(). 
            Defaults to 0.

        sample_info (dict, optional): 
            when sample_ID is not given or found, pass sample_name and composition_string as dict here. 
            e.g., sample_info = {'sample_name':'CeO2_quartz', 'composition_string':'CeO2'}
            Defaults to {}.

        md (dict, optional): 
            additional metadata.
            e.g., md = {'note':'dummy test'} 
            Defaults to {}.

        stream_name (str, optional): 
            stream name in the event document, 'primary' is recommended.
            Defaults to 'primary'.

        no_dark (bool, optional): 
            if no_dark = True, the dark scan will be skipped, especially for pilatus. 
            Defaults to False.

        jogging (list, optional): 
            If jogging, three elemetns needs to be defined as [jog_motor, start, stop].
            e.g.,  jogging = [OT_stage_2_X, 0.5, 3.7]
            Defaults to [].

        frame_acq_time (float, optional): 
            Change frame acquistion time if needed, only for pe1c. 
            Defaults to 0.1.

        user_config (dict, optional): 
            Pass self-defined configuration info to pdfstream.
            e.g.,  user_config = {'auto_mask': False, 'qmaxinst':28, 'qmax':28.0, 'rpoly':0.7,
                    'user_mask': '/nsls2/auto-storage/pdf/pdfhack/legacy/processed/xpdacq_data/user_data/config_base/Mask.npy',    
                    'method': 'splitpixel'}
            Defaults to {}.

    Returns:
        str: uid

    Yields:
        msg: Msg
    """

    ## Inject sample metadata from Excel spreadsheet
    try:
        sample_meta:dict = bt.samples.sel(sample_ID)

    ## Inject sample metadata manually from sample_info
    except (KeyError, IndexError):
        sample_meta:dict = sample_info

    print(f'\n***** sample_name = {sample_meta["sample_name"]} *****')

    ## Check composition string
    try:
        print(f'\n***** composition_string = {sample_meta["composition_string"]} *****\n')
    except KeyError:
        sample_meta["composition_string"] = 'Ni1.0'
        print(f'\n***** composition_string = {sample_meta["composition_string"]} (dummy) *****\n')

    md.update(sample_meta)

    ## while passing plan as a generator, no need to add "yield from"
    grand_plan = trigger_areaDet(dets, exposure, stream_name, md, no_dark, 
                                 jogging=jogging, frame_acq_time=frame_acq_time, 
                                 user_config=user_config)
    
    if not no_dark:
        grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid)
    
    grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage)
    return (yield from grand_plan)


# Define custom commands for sample loading/unloading.

class xrun_md():
    def inject_xrun_md(self, *args, **kwargs):
        """A custom command to inject md into the RunEngine's md."""
        # This is a placeholder method. The actual implementation will depend on how you want to inject metadata.
        pass

xx = xrun_md()

from bluesky.utils import single_gen
def inject_xrun_md():
    # TODO: I think this can be simpler.
    return (yield from single_gen(Msg('inject_xrun_md', xx)))

async def _inject_xrun_md(msg):
    msg.obj.inject_xrun_md(*msg.args, **msg.kwargs)

# Register these custom command with the RunEngine.
RE.register_command('inject_xrun_md', _inject_xrun_md)



from ophyd.sim import det, noisy_det
def show_msg_command(dets: list=[det], 
                     stream_name: str='primary', 
                     md: dict={},):
    _md = md or {}
    @bpp.stage_decorator(dets)
    @bpp.run_decorator(md=_md)
    def trigger_and_wait() -> MsgGenerator:
        for det in dets:
            yield from inject_xrun_md()
            yield from bps.trigger(det, wait=True)
            yield from bps.create(name=stream_name)
            yield from bps.read(det)
            # print(f"\n\n===== {msg.command = } =====\n\n")
    
    yield from trigger_and_wait()
    for msg in trigger_and_wait():
        print(f"\n\n===== {msg.command = } =====\n\n")


def periodic_dark_02(plan):
    """
    a plan wrapper that takes a plan and inserts `take_dark`

    The `take_dark` plan is inserted on the fly before the beginning of
    any new run after a period of time defined by glbl['dk_window'] has passed.
    """
    need_dark = True

    def insert_take_dark(msg):
        nonlocal need_dark
        qualified_dark_uid = _validate_dark(expire_time=glbl["dk_window"])
        area_det = xpd_configuration["area_det"]

        if (not need_dark) and (not qualified_dark_uid):
            need_dark = True
        if need_dark and (not qualified_dark_uid) and msg.command == "inject_xrun_md" and (
            "dark_frame" not in msg.kwargs
        ):
            # We are about to start a new 'run' (e.g., a count or a scan).
            # Insert a dark frame run first.
            need_dark = False
            # Annoying detail: the detector was probably already staged.
            # Unstage it (if it wasn't staged, nothing will happen) and
            # then take_dark() and then re-stage it.
            return (
                bpp.pchain(
                    bps.unstage(area_det),
                    take_dark(),
                    bps.stage(area_det),
                    bpp.single_gen(msg),
                    open_shutter_stub(),
                ),
                None,
            )
        elif msg.command == "inject_xrun_md" and "dark_frame" not in msg.kwargs:
            return (
                bpp.pchain(
                    bpp.single_gen(msg),
                    open_shutter_stub()
                ),
                None,
            )
        else:
            # do nothing if (not need_dark)
            return None, None

    return (yield from bpp.plan_mutator(plan, insert_take_dark))




def _inject_qualified_dark_frame_uid_02(msg):
    """Inject the dark frame uid in start."""
    if msg.command == "inject_xrun_md" and msg.kwargs.get("dark_frame") is not True:
        dark_uid = _validate_dark(glbl["dk_window"])
        msg.kwargs["sc_dk_field_uid"] = dark_uid
    return msg



def _inject_calibration_md_02(msg):
    """Inject the calibration data in start."""
    if msg.command == "inject_xrun_md":
        exp_hash_uid = glbl.get("exp_hash_uid")
        # inject client uid to all runs
        msg.kwargs.setdefault("detector_calibration_client_uid", exp_hash_uid)
        if "is_calibration" in msg.kwargs:
            # inject server uid if it's calibration run
            msg.kwargs.setdefault("detector_calibration_server_uid", exp_hash_uid)
        else:
            # load calibration param if exists
            calibration_md = _auto_load_calibration_file()
            if calibration_md:
                injected_calib_dict = dict(calibration_md)
                # inject calibration md
                msg.kwargs.setdefault("calibration_md", injected_calib_dict)
    return msg




def _inject_analysis_stage_02(msg):
    """specify at which stage the documents is processed"""
    if msg.command == "inject_xrun_md":
        msg.kwargs["analysis_stage"] = "raw"
    return msg



def _inner_Absorption(det2, num_abs):
	spectrum_type='Absorbtion'
	correction_type='Reference'
	if LED.get()=='Low' and UV_shutter.get()=='High' and det2.correction.get()==correction_type and det2.spectrum_type.get()==spectrum_type:
		pass
	else:
		# yield from bps.abs_set(qepro.correction, correction_type, wait=True)
		# yield from bps.abs_set(qepro.spectrum_type, spectrum_type, wait=True)
		yield from bps.mv(det2.correction, correction_type, det2.spectrum_type, spectrum_type)
		yield from bps.mv(LED, 'Low', UV_shutter, 'High')
		yield from bps.sleep(2)

	for i in range(num_abs):
		yield from bps.trigger(det2, wait=True)

		yield from bps.create(name="absorbance")
		yield from bps.read(det2)
		yield from bps.save()  # TODO: check if it's needed, most likely yes.
		# yield from bps.sleep(2)
            


def _inner_fluorescence(det2, num_flu):
	spectrum_type='Corrected Sample'
	correction_type='Dark'
	if LED.get()=='High' and UV_shutter.get()=='Low' and det2.correction.get()==correction_type and det2.spectrum_type.get()==spectrum_type:
		pass
	else:
		# yield from bps.abs_set(qepro.correction, correction_type, wait=True)
		# yield from bps.abs_set(qepro.syield from bps.sleep(xray_time)pectrum_type, spectrum_type, wait=True)
		yield from bps.mv(det2.correction, correction_type, det2.spectrum_type, spectrum_type)
		yield from bps.mv(LED, 'High', UV_shutter, 'Low')
		yield from bps.sleep(2)

	for i in range(num_flu):  # TODO: fix the number of triggers
		yield from bps.trigger(det2, wait=True)

		yield from bps.create(name="fluorescence")
		yield from bps.read(det2)
		yield from bps.save()  # TODO: check if it's needed, most likely yes.
		# yield from bps.sleep(2)

	yield from bps.mv(LED, 'Low', UV_shutter, 'Low')

            


## Design for xray_uvvis_RE plan, remove the run_decorator since the run_decorator will be added in xray_uvvis_RE
def _inner_scattering(dets, exposure, frame_acq_time=0.2, stream_name='primary', md={}, no_dark=False, jogging=[], user_config={}):
    _md = md or {}
    # _md['sample_name'] = sample_name
    sp_md = yield from _pre_plan(dets, exposure, frame_acq_time=frame_acq_time)
    sp_md["sp_plan_name"] = "trigger_areaDet",
    _md.update(sp_md)
    _md.update({'user_config':user_config})

    if len(jogging) == 3:
        _md["plan_name"] = "jog_areaDet"
        _md["jog_md"] = {"start": jogging[1], "stop": jogging[2], "motor": jogging[0].name}
        jogging_motor = jogging[0]
    else:
        jogging_motor = sample_y   #OT_stage_2_Y for PDF, sample_y for XRD


    # nonlocal start, stop
    @bpp.reset_positions_decorator([jogging_motor.velocity])
    def inner_jog(gp, motor, start, stop):
        yield from bps.mv(motor, start)  # got to initial position
        yield from bps.mv(motor.velocity, abs(stop-start)/(exposure), timeout=1)  # set velocity
        # gp = short_uid("rocker")
        yield from bps.abs_set(motor, stop, group=gp)  # set motor to move towards end


    # table = LiveTable(motors_field, stream_name=stream_name, default_prec=0)
    # @bpp.subs_decorator(table)
    # @bpp.stage_decorator(dets)
    # @bpp.run_decorator(md=_md)
    def trigger_and_wait() -> MsgGenerator:
        yield from inject_xrun_md()
        
        for det in dets:
            
            nonlocal jogging
            if len(jogging) == 3:
                print(f'Star to jog using {jogging[0].name} from {jogging[1]} mm to {jogging[2]} mm')
                gp = short_uid("rocker")
                yield from inner_jog(gp, motor=jogging[0], start=jogging[1], stop=jogging[2])

            yield from bps.trigger(det, wait=True)
            yield from bps.create(name=stream_name)
            yield from bps.read(det)
            # yield from bps.read(motors[0])
            # yield from bps.read(motors[1])
            # yield from bps.read(motors[2])
            yield from bps.save()
    
    # grand_plan = trigger_and_wait()
    
    # if not no_dark:
    #     # yield from periodic_dark(trigger_and_wait())
    #     grand_plan = periodic_dark_02(trigger_and_wait())
    #     grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid_02)
    #     grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md_02)
    #     grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage_02)
    #     yield from grand_plan
    
    # else:
    #     yield from open_shutter_stub()
    #     grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid_02)
    #     grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md_02)
    #     grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage_02)
    #     yield from grand_plan
    #     yield from close_shutter_stub()
    
    yield from trigger_and_wait()



def xray_uvvis_RE(det1: ophyd.Device, 
                  det2: ophyd.Device, 
                  exposure: float, 
                  *args, 
                  frame_acq_time: float=0.2, 
                  md: dict=None, 
                  num_abs: int=10, 
                  num_flu: int=10, 
                  stream_name: str='scattering', 
                  sample_type: str = 'test', 
                  pump_list: list=None, 
                  precursor_list: list=None, 
                  mixer: list=None, 
                  note: dict=None, 
                  no_dark: bool=False, 
                  **kwargs, 
                  ):
    
    """Trigger the two detctors (det1: pe1c, det2: qepro): det2 first and then det1.
        
    Generate a scan containing three stream names: ['scattering', 'absorbance', 'fluorescence']

    Args:
        det1 (ophyd.Device): xray detector (example: pe1c)
        det2 (ophyd.Device): Uv-Vis detector (example: qepro)
        frame_acq_time (float, optional): frame acquisition time. Defaults to 0.2.
        md (dict, optional): metadata.
        num_abs (int, optional): numbers of absorption spectra
        num_flu (int, optional): numbers of fluorescence spectra
        sample_type (str, optional): sample name
        pump_list (list, optional): list of pumps as ophyd.Device (example: [dds1_p1, dds1_p2, dds2_p1, dds2_p2])
        precursor_list (list, optional): list of precursors name (example: ['CsPbOA', 'TOABr', 'ZnI2', 'Toluene'])
        mixer (list, optional): list of mixers (example: ['30 cm', '60 cm'])pump_list
        note (str, optional): addtional info. Defaults to None.
    """
    
    # print(f'\n===== {[det1.name, det2.name, 'xxxxx'] = } =====\n')
    
    if (pump_list != None and precursor_list != None):
        _md = {"pumps" : [pump.name for pump in pump_list],
               "precursors" : precursor_list,
               "infuse_rate" : [pump.read_infuse_rate.get() for pump in pump_list],
               "infuse_rate_unit" : [pump.read_infuse_rate_unit.get() for pump in pump_list],
               "pump_status" : [pump.status.get() for pump in pump_list],
               "uvvis" :[det2.integration_time.get(), det2.num_spectra.get(), det2.buff_capacity.get()],
               "mixer": mixer,
               "sample_type": sample_type,
               "sample_name": sample_type,
               "detectors_in_use": [det1.name, det2.name], 
               "note" : note if note else "None"}
        _md.update(md or {})

    sp_md = yield from _pre_plan([det1], exposure, frame_acq_time=frame_acq_time)

    if (pump_list == None and precursor_list == None):
        _md = { #"uvvis" :[det2.integration_time.get(), det2.num_spectra.get(), det2.buff_capacity.get()],
                "mixer": ['exsitu measurement'],
                "sample_type": sample_type, 
                "sample_name": sample_type,
                #"detectors": [det1.name, det2.name], 
                "note" : note if note else "None"}
        _md.update(md or {})
        
    _md.update(sp_md)
            
    
    @bpp.stage_decorator([det1, det2])
    @bpp.run_decorator(md=_md)
    def trigger_two_detectors():  # TODO: rename appropriately

        ## Start to collecting absrobtion
        # t0 = time.time()
        yield from _inner_Absorption(det2, num_abs, **kwargs)
        
        ## Start to collecting fluorescence
        yield from _inner_fluorescence(det2, num_flu, **kwargs)
        
        try:
            yield from stop_group([pump_list[-1]])
            print(f'\nUV-Vis acquisition finished and stop infusing of {pump_list[-1].name} for toluene dilution\n')
        except TypeError:
            print(f'\n{pump_list = }. No pump_list!! \n')

        ## Start to collecting scattering
        yield from _inner_scattering([det1], exposure, frame_acq_time=frame_acq_time, stream_name=stream_name, no_dark=no_dark, **kwargs)
        
    # periodic_dark has to wrap a plan which is a complete run (where run_decorator is added).
    grand_plan = periodic_dark(trigger_two_detectors())
    grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage)
    return (yield from grand_plan)
    # yield from trigger_two_detectors()
    
