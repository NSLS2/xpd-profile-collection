"Define all the motors on the beamline"

from ophyd import EpicsMotor
import ophyd
from ophyd import EpicsSignal

th_cal = EpicsMotor('XF:28IDC-ES:1{Dif:2-Ax:Th}Mtr', name='th_cal')
tth_cal = EpicsMotor('XF:28IDC-ES:1{Dif:2-Ax:2Th}Mtr', name='tth_cal')
ecal_x = EpicsMotor('XF:28IDC-ES:1{Dif:2-Ax:X}Mtr', name='ecal_x')
ecal_y = EpicsMotor('XF:28IDC-ES:1{Dif:2-Ax:Y}Mtr', name='ecal_y')

# Tim test with Sanjit. Delete it if anything goes wrong
ss_stg2_x = EpicsMotor('XF:28IDC-ES:1{Stg:Smpl2-Ax:X}Mtr', name='ss_stg2_x')
# Sanjit Inlcuded this. Delete it if anything goes wrong
ss_stg2_y = EpicsMotor('XF:28IDC-ES:1{Stg:Smpl2-Ax:Y}Mtr', name='ss_stg2_y')
ss_stg2_z = EpicsMotor('XF:28IDC-ES:1{Stg:Smpl2-Ax:Z}Mtr', name='ss_stg2_z')

# long travel sample stage 
sample_x = EpicsMotor('XF:28IDC-ES:1{SampArray-Ax:X}Mtr', name='sample_x')
sample_y = EpicsMotor('XF:28IDC-ES:1{SampArray-Ax:Y}Mtr', name='sample_y')


# Sample stage stack axes
ss_fine_x = EpicsMotor('XF:28IDD-ES:2{Stg:Stack-Ax:Xfine}Mtr', name='ss_fine_x')
ss_fine_y = EpicsMotor('XF:28IDD-ES:2{Stg:Stack-Ax:Yfine}Mtr', name='ss_fine_y')
ss_hrm = EpicsMotor('XF:28IDD-ES:2{Stg:Stack-Ax:Htth}Mtr', name = 'ss_hrm')
ss_cam_x = EpicsMotor('XF:28IDD-ES:2{Cam:Mnt-Ax:X}Mtr', name = 'ss_cam_x')

# RPI DIFFRACTOMETER motors ### Change th only after changing in other plans
th = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:Th}Mtr', name='th')
#tth = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:2ThI}Mtr', name='tth')
diff_x = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:X}Mtr', name='diff_x')
diff_y = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:Y}Mtr', name='diff_y')
diff_tth_i = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:2ThI}Mtr', name='diff_tth_i')
diff_tth_o = EpicsMotor('XF:28IDC-ES:1{Dif:1-Ax:2ThO}Mtr', name='diff_tth_o')

hrm_y = EpicsMotor('XF:28IDC-OP:1{Mono:HRM-Ax:Y}Mtr', name='hrm_y')
hrm_b = EpicsMotor('XF:28IDC-OP:1{Mono:HRM-Ax:P}Mtr', name='hrm_b')
hrm_r = EpicsMotor('XF:28IDC-OP:1{Mono:HRM-Ax:R}Mtr', name='hrm_r')

# PE detector motions
pe1_x = EpicsMotor('XF:28IDC-ES:1{Det:PE1-Ax:X}Mtr', name='pe1_x')
pe1_z = EpicsMotor('XF:28IDC-ES:1{Det:PE1-Ax:Z}Mtr', name='pe1_z')

# Pinhole motions
pinhole_x = EpicsMotor('XF:28IDC-ES:1{PinHole:XRD-Ax:X}Mtr', name='pinhole_x')
pinhole_y = EpicsMotor('XF:28IDC-ES:1{PinHole:XRD-Ax:Y}Mtr', name='pinhole_y')

# MAD motions
mad_pitch=EpicsMotor('XF:28IDC-ES:1{MAD:DMS-Ax:Pitch}Mtr', name='mad_pitch')


shctl1 = EpicsMotor('XF:28IDC-ES:1{Sh2:Exp-Ax:5}Mtr', name='shctl1')
fs = shctl1 #added by dan

class FilterBank(ophyd.Device):
    flt1 = ophyd.Component(EpicsSignal, '1-Cmd', string=True)
    flt2 = ophyd.Component(EpicsSignal, '2-Cmd', string=True)
    flt3 = ophyd.Component(EpicsSignal, '3-Cmd', string=True)
    flt4 = ophyd.Component(EpicsSignal, '4-Cmd', string=True)

fb = FilterBank('XF:28IDC-OP:1{Fltr}Cmd:Opn', name='fb')
p_diode = EpicsSignal('XF:28IDC-BI:1{IM:02}Pos-Cmd', name='p_diode', string=True)
