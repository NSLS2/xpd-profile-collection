from xpdacq.beamtime import configure_area_det
from xpdacq.xpdacq import periodic_dark
from xpdacq.xpdacq import _inject_qualified_dark_frame_uid, _inject_calibration_md, _inject_analysis_stage
import bluesky.preprocessors as bpp

def ct_dark(dets: list, exposure: float):
    yield from periodic_dark(ct(dets, exposure))
    ## needs to add close shutter
    
    
    
# issue:
#     To add: 
#           1. close shutter
#           2. Auto sbustract dark
#           3. Metadata (v)
#     To check: 
#           1. configure detector (v)




def _pre_plan(dets, exposure):
    """Handle detector exposure time + xpdan required metadata"""

    xpd_configuration["area_det"] = dets[0]
    
    # if 'pilatus1' not in dets[0].name:
    #     raise ValueError('This plan is for pilatus but not pilatus in dets')

    # setting up area_detector
    # from xpdacq.beamtime import _configure_area_det
    for ad in (d for d in dets if hasattr(d, "cam")):
        (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exposure)
    # else:
    #     acq_time = 0
    #     computed_exposure = exposure
    #     num_frame = 0

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



def trigger_areaDet(dets, exposure, stream_name, sample_name, md):
    _md = md or {}
    _md['sample_name'] = sample_name
    sp_md = yield from _pre_plan(dets, exposure)
    sp_md["sp_plan_name"] = "trigger_areaDet",
    _md.update(sp_md)

    @bpp.stage_decorator(dets)
    @bpp.run_decorator(md=_md)
    def trigger_and_wait() -> MsgGenerator:
        for det in dets:
            ret = {}
            yield from bps.trigger(det, wait=True)
            yield from bps.create(name=stream_name)
            reading = (yield from bps.read(det))
            # yield from bps.read(Grid_X)
            # print(f"reading = {reading}")
            # ret.update(reading)
            return (yield from bps.save())
        
    return (yield from periodic_dark(trigger_and_wait()))



def scan_with_dark(dets, exposure, stream_name='primary', sample_name='test', md=None):
    ## while passing plan as a generator, no need to add "yield from"
    grand_plan = trigger_areaDet(dets, exposure, stream_name, sample_name, md)
    # grand_plan = trigger_areaDet(dets, exposure, stream_name, sample_name, md)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage)
    return (yield from grand_plan)



def xray_uvvis_test(det1, det2, exposure, *args, md=None, num_abs=10, num_flu=10, sample_type = 'test',
                    pump_list=None, precursor_list=None, mixer=None, note=None, **kwargs):
    """Trigger the two detctors (det1: pe1c, det2: qepro): det2 first and then det1.
        
    Generate a scan containing three stream names: ['scattering', 'absorbance', 'fluorescence']

    Args:
        det1 (ophyd.Device): xray detector (example: pe1c)
        det2 (ophyd.Device): Uv-Vis detector (example: qepro)
        md (dict, optional): metadata.
        num_abs (int, optional): numbers of absorption spectra
        num_flu (int, optional): numbers of fluorescence spectra
        sample_type (str, optional): sample name
        pump_list (list, optional): list of pumps as ophyd.Device (example: [dds1_p1, dds1_p2, dds2_p1, dds2_p2])
        precursor_list (list, optional): list of precursors name (example: ['CsPbOA', 'TOABr', 'ZnI2', 'Toluene'])
        mixer (list, optional): list of mixers (example: ['30 cm', '60 cm'])
        note (str, optional): addtional info. Defaults to None.
    """
    # if (pump_list != None and precursor_list != None):
    #     _md = {"pumps" : [pump.name for pump in pump_list],
    #            "precursors" : precursor_list,
    #            "infuse_rate" : [pump.read_infuse_rate.get() for pump in pump_list],
    #            "infuse_rate_unit" : [pump.read_infuse_rate_unit.get() for pump in pump_list],
    #            "pump_status" : [pump.status.get() for pump in pump_list],
    #            "uvvis" :[det2.integration_time.get(), det2.num_spectra.get(), det2.buff_capacity.get()],
    #            "mixer": mixer,
    #            "sample_type": sample_type,
    #            "sample_name": sample_type,
    #            "detectors": [det1.name, det2.name], 
    #            "note" : note if note else "None"}
    #     _md.update(md or {})

    sp_md = yield from _pre_plan([det1], exposure)

    if (pump_list == None and precursor_list == None):
        _md = { #"uvvis" :[det2.integration_time.get(), det2.num_spectra.get(), det2.buff_capacity.get()],
                "mixer": ['exsitu measurement'],
                "sample_type": sample_type, 
                "sample_name": sample_type,
                #"detectors": [det1.name, det2.name], 
                "note" : note if note else "None"}
        _md.update(md or {})
        
    _md.update(sp_md)

    
    # def Absorption():
    #     spectrum_type='Absorbtion'
    #     correction_type='Reference'
    #     if LED.get()=='Low' and UV_shutter.get()=='High' and det2.correction.get()==correction_type and det2.spectrum_type.get()==spectrum_type:
    #         pass
    #     else:
    #         # yield from bps.abs_set(qepro.correction, correction_type, wait=True)
    #         # yield from bps.abs_set(qepro.spectrum_type, spectrum_type, wait=True)
    #         yield from bps.mv(det2.correction, correction_type, det2.spectrum_type, spectrum_type)
    #         yield from bps.mv(LED, 'Low', UV_shutter, 'High')
    #         yield from bps.sleep(2)

    #     for i in range(num_abs):
    #         yield from bps.trigger(det2, wait=True)

    #         yield from bps.create(name="absorbance")
    #         reading = (yield from bps.read(det2))
    #         # print(f"reading = {reading}")
    #         # ret.update(reading)
    #         yield from bps.save()  # TODO: check if it's needed, most likely yes.
    #         # yield from bps.sleep(2)
            
    
    
    # def fluorescence():
    #     spectrum_type='Corrected Sample'
    #     correction_type='Dark'
    #     if LED.get()=='High' and UV_shutter.get()=='Low' and det2.correction.get()==correction_type and det2.spectrum_type.get()==spectrum_type:
    #         pass
    #     else:
    #         # yield from bps.abs_set(qepro.correction, correction_type, wait=True)
    #         # yield from bps.abs_set(qepro.syield from bps.sleep(xray_time)pectrum_type, spectrum_type, wait=True)
    #         yield from bps.mv(det2.correction, correction_type, det2.spectrum_type, spectrum_type)
    #         yield from bps.mv(LED, 'High', UV_shutter, 'Low')
    #         yield from bps.sleep(2)

    #     for i in range(num_flu):  # TODO: fix the number of triggers
    #         yield from bps.trigger(det2, wait=True)

    #         yield from bps.create(name="fluorescence")
    #         reading = (yield from bps.read(det2))
    #         # print(f"reading = {reading}")
    #         # ret.update(reading)
    #         yield from bps.save()  # TODO: check if it's needed, most likely yes.
    #         # yield from bps.sleep(2)

    #     yield from bps.mv(LED, 'Low', UV_shutter, 'Low')
    #     try:  
    #         yield from stop_group([pump_list[-1]])
    #         print(f'\nUV-Vis acquisition finished and stop infusing of {pump_list[-1].name} for toluene dilution\n')
    #     except (TypeError):
    #         print(f'\n{pump_list = }. No pump_list!! \n')
            
            
            
    def scattering():
        yield from bps.trigger(det1, wait=True)
        # yield from bps.sleep(det1_time)
        yield from bps.create(name="scattering")
        reading = (yield from bps.read(det1))
        # print(f"reading = {reading}")
        # ret.update(reading)
        return (yield from bps.save())
    
    
    @bpp.stage_decorator([det1, det2])
    # @bpp.stage_decorator([det1])
    @bpp.run_decorator(md=_md)
    def trigger_two_detectors():  # TODO: rename appropriately
        ret = {}

        # TODO: write your fast procedure here, don't use bp.count/bp.scan here as they open separate runs.
        # Use `trigger_and_read` instead.
        # Tested on 2023/02/16: bps.trigger works for qepro


        # For absorbance: spectrum_type='Absorbtion', correction_type='Reference'
        # For fluorescence: spectrum_type='Corrected Sample', correction_type='Dark'

        ## Start to collecting absrobtion
        # t0 = time.time()
        # yield from Absorption()
        
        ## Start to collecting fluorescence
        # yield from fluorescence()

        ## Start to collecting scattering
        return (yield from periodic_dark(scattering()))
        
    grand_plan = trigger_two_detectors()
    # grand_plan = trigger_areaDet([det1], exposure, 'scattering', 'test', _md)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_qualified_dark_frame_uid)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_calibration_md)
    grand_plan = bpp.msg_mutator(grand_plan, _inject_analysis_stage)
    # yield from trigger_two_detectors()
    return (yield from grand_plan)
    
