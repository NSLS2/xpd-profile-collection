from xpdacq.beamtime import configure_area_det
from xpdacq.xpdacq import periodic_dark

def ct_dark(dets: list, exposure: float):
    yield from periodic_dark(ct(dets, exposure))
    
    