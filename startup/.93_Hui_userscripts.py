# -*- coding: utf-8 -*-
"""
Created on Thu Aug 13 15:58:10 2020

@author: hzhong
"""

# -*- coding: utf-8 -*-
"""
Plan to run multiple sample under remote condition
This plan uses xpdacq protocol
"""

from xpdacq.beamtime import _configure_area_det
from xpdacq.beamtime import open_shutter_stub, close_shutter_stub
from collections import ChainMap, OrderedDict
import pandas as pd
import datetime
import functools
import time
from bluesky.callbacks import LiveFit
from bluesky.callbacks.mpl_plotting import LiveFitPlot
import numpy as np
from urllib import request
import json
from os import chmod
from pandas.core.common import flatten


def xpd_mscan(sample_list, posx_list, exp_time, posy_list=None, num=1, delay_num=0, delay=0, smpl_h=None, flt_h=None, flt_l=None,
                motorx=sample_x, motory=sample_y, dets=None):
    """ Perform multi-sample scans by moving samples to predefined x (and y positions if needed), applying filters,
    and executing a scan plan.

    Example:

        >>> samples = [1, 2, 3]
        >>> x_positions = [10, 20, 30]
        >>> y_positions = [5, 15, 25] 
        >>> exp_time = 5
        >>> special_samples = [1, 3]
        >>> special_filter = [1, 0, 0, 0]
        >>> default_filter = [0, 0, 0, 0]
        if all samples are at the same y position, posy_list is NOT needed      
        >>> xpd_m2dscan(samples, x_positions, exp_time, delay=2, smpl_h=special_samples, flt_h=special_filter, flt_l=default_filter)
        if posy_list is needed  
        >>> xpd_m2dscan(samples, x_positions, exp_time, posy_list=y_positions,delay=2, smpl_h=special_samples, flt_h=special_filter, flt_l=default_filter)
        if all samples use the same filter set which has been set manually
        >>> xpd_m2dscan(samples, x_positions, exp_time, posy_list=y_positions, delay=2)
        if all samples are at the same y position, and use the same filter set which has been set manually
        >>> xpd_m2dscan(samples, x_positions, exp_time, delay=2)        

    multi-sample scan plan, parameters:
        sample_list (list): list of all samples in the sample holder
        posx_lis: list of sample x positions, sample_list, posx_list should be match
        posy_list(Optional): list of sample y positions, sample_list, posx_list and posy_listshould be match
        motorx, motory: motors which moves sample holder, default is sample_x and sample_y
        exp_time : total exposure time for each sample, in seconds
        num: number of data at each time
        delay_num : sleep time in between each data if multiple data are taken at each time
        delay: delay time in between each sample
        smpl_h: list of samples which needs special filter set flt_h
        flt_h: filter set for samples in smpl_h
        flt_l: filter set for rest of the samples
    """
    # Input validation
    
    if len(sample_list) != len(posx_list):
        raise ValueError("sample_list, posx_list must have the same length")
    if posy_list and (len(posx_list) != len(posy_list)):
        raise ValueError("posx_list and posy_list must have the same length if posy_list is provided")

    
    # Ensure that if smpl_h is provided, both flt_h and flt_l are provided
    if smpl_h is not None and (flt_h is None or flt_l is None):
        raise ValueError("If smpl_h is provided, both flt_h and flt_l must also be provided.")

    if smpl_h is None:
        smpl_h = []
    if dets is None:
        dets = []
    
    area_det = xpd_configuration['area_det']
    det = [area_det] + dets

    delay_num1 = delay_num + exp_time

    length = len(sample_list)
    print('Total sample numbers:', length)

    for sample, posx, posy in zip(sample_list, posx_list, posy_list or [None] * len(posx_list)):
        print(f'Move sample {sample} to position ({posx}, {posy})')
        move_to_position(posx, posy, motorx=motorx, motory=motory)
        if sample in smpl_h:
            if flt_h is not None:
                xpd_flt_set(flt_h)
        else:
            if flt_l is not None:
                xpd_flt_set(flt_l)
        # Delay between samples
        time.sleep(delay)
        #run the scan plan
        print(f'Running scan plan for sample {sample}')
        plan = ct_motors_plan(det, exp_time, num=num, delay=delay_num1)
        xrun(sample, plan)    

    print('Multi-sample scan complete.')

def move_to_position(posx, posy=None, motorx=sample_x, motory=sample_y):
    """Helper to move motors to the specified position."""
    motorx.move(posx)
    if posy is not None:
        motory.move(posy)

def xpd_battery(smpl_list, posx_list, exp_time, posy_list=None, num=1, delay_num=0, cycle=1, delay=0, motorx=sample_x, motory=sample_y, dets=None):
    """ battery cycling experiment for multiple cells, each at different x and y positions

     
    Example: No posylist needed

        >>> samples = [1, 2, 3]
        >>> x_positions = [10, 20, 30]
        >>> exp_time = 5
        >>> xpd_battery(samples, x_positions, exp_time, cycle=2, delay=2)
    Example: posylist needed
        >>> samples = [1, 2, 3]
        >>> x_positions = [10, 20, 30]
        >>> y_positions = [5, 15, 25]
        >>> exp_time = 5
        # Perform a battery cycling scan with 2 cycles and a 2-second delay between each sample move
        >>> xpd_batteryxy(samples, x_positions, exp_time, posylist=y_positions, exp_time, cycle=2, delay=2)

    Parameters:
        smpl_list (list): List of sample IDs that need to be scanned.
        posx_list (list): List of x positions corresponding to each sample in `smpl_list`.
        posy_list (list): List of y positions corresponding to each sample in `smpl_list`.
        exp_time : total exposure time for each sample, in seconds
        num: number of data at each time
        delay_num : sleep time in between each data if multiple data are taken at each time
        cycle (int, optional): The number of times to cycle through the samples. Default is 1.
        delay (int or float, optional): Time delay (in seconds) between moving each sample and running the scan.
            Default is 0 (no delay).
        motorx (object, optional): Motor object used to move the sample holder along the x-axis. Default is `sample_x`.
        motory (object, optional): Motor object used to move the sample holder along the y-axis. Default is `sample_y`.

    """

    # Input validation
    if len(smpl_list) != len(posx_list):
        raise ValueError("smpl_list, posx_list must have the same length")
    if posy_list and (len(posx_list) != len(posy_list)):
        raise ValueError("posxlist and posylist must have the same length if posylist is provided")

    if dets is None:
        dets = []
    
    area_det = xpd_configuration['area_det']
    det = [area_det] + dets

    delay_num1 = delay_num + exp_time

    length = len(smpl_list)
    print(f'Total sample numbers: {length}')

    for i in range(cycle):
        print(f"Starting cycle {i + 1}/{cycle}")
        # Loop through each sample and perform the scan
        for smpl, posx, posy in zip(smpl_list, posx_list, posy_list or [None] * len(posx_list)):
            print(f'Cycle {i + 1}, moving sample {smpl} to position (x = {posx}, y = {posy})')
            move_to_position(posx, posy, motorx=motorx, motory=motory)
            time.sleep(delay)
            plan = ct_motors_plan(det, exp_time, num=num, delay=delay_num1)
            xrun(smpl, plan) 



def linescan(smpl, exp_time, xstart, xend, xpoints, motor=sample_y, md=None, dets=None):

    """  line scan by moving a motor between `xstart` and `xend` in `xpoints` steps and recording measurements.

    Example:
        >>> linescan(1, 5.0, 0, 10, 5, motor=sample_y)

    Parameters
        smpl (int): Sample ID to be measured.
        exp_time (float): Total exposure time (in seconds) for each measurement point.
        xstart (float): Starting position of the line scan.
        xend (float): End position of the line scan.
        xpoints (int): Number of points to measure along the line.
        motor (object, optional): Motor object used to move the sample. Default is `sample_y`.
        md (dict, optional): Metadata to be associated with the scan. Default is None.
        det (list, optional): List of extra detectors to record during the scan. Default is None.

    """
    # Log the scan details
    print(f'Starting line scan for sample {smpl}')
    print(f'Line scan parameters: xstart={xstart}, xend={xend}, xpoints={xpoints}, exp_time={exp_time}s')

    # Create the scan plan
    plan = lineplan(exp_time, xstart, xend, xpoints, motor=motor, md=md, dets=dets)
    xrun(smpl, plan)


def mlinescan(smplist, poslist, exp_time, lstart, lend, lpoints, pos_motor=sample_x, lmotor=sample_y,
              smpl_h=None, flt_l=None, flt_h=None, dets=None, md=None):
    """ Perform line scans for multiple samples. For each sample, the function moves the sample to a specified position
     and measures multiple points along a line using a motor.

     Example:
         >>> samples = [1, 2, 3]
         >>> positions = [10, 20, 30]
         >>> mlinescan(samples, positions, 5.0, 0, 10, 5)

     Parameters
         smplist (list): List of sample IDs to be measured.
         poslist (list): List of sample positions corresponding to `smplist`.
         exp_time (float): Total exposure time (in seconds) for each measurement point.
         lstart (float): Starting position of the line scan.
         lend (float): End position of the line scan.
         lpoints (int): Number of points to measure along the line.
         pos_motor (object, optional): Motor object used to move samples to their positions. Default is `sample_x`.
         lmotor (object, optional): Motor object used to perform the line scan. Default is `sample_y`.
         smpl_h (list, optional): List of samples requiring special filter sets. Default is None.
         flt_h (list, optional): Filter set for the samples in `smpl_h`. Default is None.
         flt_l (list, optional): Filter set for all other samples. Default is None.
         det (list, optional): List of extra detectors to record during the scan. Default is None.
         md (dict, optional): Metadata to be associated with the scan. Default is None.

     """
    # Input validation
    assert len(smplist) == len(poslist), "sample_list and pos_list must have the same length"

    # Ensure that if smpl_h is provided, both flt_h and flt_l are provided
    if smpl_h is not None and (flt_h is None or flt_l is None):
        raise ValueError("If smpl_h is provided, both flt_h and flt_l must also be provided.")

    if dets is None:
        dets = []
    if smpl_h is None:
        smpl_h = []

    # Combine the position motor with other detectors if any
    dets = [pos_motor] + dets
    length = len(smplist)
    print(f'Total sample numbers:{length}')

    for smpl, pos in zip(smplist, poslist):
        print(f'Moving sample {smpl} to position {pos}')
        pos_motor.move(pos)

        # Apply filters if necessary
        if smpl in smpl_h:
            if flt_h is not None:
                xpd_flt_set(flt_h)
        else:
            if flt_l is not None:
                xpd_flt_set(flt_l)

        plan = lineplan(exp_time, lstart, lend, lpoints, motor=lmotor, md=md, dets=dets)
        xrun(smpl, plan)




def gridscan(smpl, exp_time, xstart, xstop, xpoints, ystart, ystop, ypoints,
             motorx=sample_x, motory=sample_y, md=None, dets=None):
    """
        Perform a grid scan by moving a sample across a grid of x and y points.

        Example:
            >>> gridscan(1, 5, 0, 10, 5, 0, 10, 5)
        Parameters:
            smpl (int): Sample ID to be measured.
            exp_time (float): Total exposure time (in seconds) for each measurement point.
            xstart (float): Starting position on the x-axis.
            xstop (float): End position on the x-axis.
            xpoints (int): Number of points to measure along the x-axis.
            ystart (float): Starting position on the y-axis.
            ystop (float): End position on the y-axis.
            ypoints (int): Number of points to measure along the y-axis.
            motorx (object, optional): Motor object used to move the sample along the x-axis. Default is `sample_x`.
            motory (object, optional): Motor object used to move the sample along the y-axis. Default is `sample_y`.
            md (dict, optional): Metadata to be associated with the scan. Default is None.
            det (list, optional): List of extra detectors to record during the scan. Default is None.

        """

    #log the scannig process
    print(f"Starting grid scan for sample {smpl}...")
    print(f"X-axis: from {xstart} to {xstop}, points: {xpoints}")
    print(f"Y-axis: from {ystart} to {ystop}, points: {ypoints}")
    print(f"Exposure time per point: {exp_time} seconds")

    # Create the grid scan plan and execute
    plan = gridplan(exp_time, xstart, xstop, xpoints, ystart, ystop, ypoints, motorx=motorx, motory=motory, md=md, dets=dets)
    xrun(smpl, plan)


def mgridscan(smplist, exp_time, xcenter_list, xrange, xpoints, ycenter_list, yrange, ypoints, delay=1,
              motorx=sample_x, motory=sample_y, smpl_h=None, flt_l=None, flt_h=None, md=None, dets=None):

    """ Perform grid scan for multiple samples.

        Example:
            >>> samples = [1, 2, 3]
            >>> x_centers = [10, 20, 30]
            >>> y_centers = [5, 15, 25]
            >>> mgridscan(samples, 5.0, x_centers, 10, 5, y_centers, 10, 5)

        Parameters:
            smplist (list): List of sample IDs to be measured.
            exp_time (float): Total exposure time (in seconds) for each measurement point.
            xcenter_list (list): List of x-axis center positions for samples.
            xrange (float): Total range to scan along the x-axis.
            xpoints (int): Number of points along the x-axis.
            ycenter_list (list): List of y-axis center positions for samples.
            yrange (float): Total range to scan along the y-axis.
            ypoints (int): Number of points along the y-axis.
            delay (int or float, optional): Time delay (in seconds) between each sample. Default is 1 second.
            motorx (object, optional): Motor object to move the sample along the x-axis. Default is `sample_x`.
            motory (object, optional): Motor object to move the sample along the y-axis. Default is `sample_y`.
            smpl_h (list, optional): List of samples requiring special filters. Default is None.
            flt_h (list, optional): Filter set for the samples in `smpl_h`. Default is None.
            flt_l (list, optional): Filter set for all other samples. Default is None.
            md (dict, optional): Metadata to be associated with the scan. Default is None.
            det (list, optional): Extra detectors to record during the scan. Default is None.

        """

    # Input validation
    if len(smplist) != len(xcenter_list) or len(xcenter_list) != len(ycenter_list):
        raise ValueError("smplist, xcenter_list, and ycenter_list must have the same length")

    # Ensure that if smpl_h is provided, both flt_h and flt_l are provided
    if smpl_h is not None and (flt_h is None or flt_l is None):
        raise ValueError("If smpl_h is provided, both flt_h and flt_l must also be provided.")

    if smpl_h is None:
        smpl_h = []

    length = len(smplist)
    print(f'Total number of samples: {length}')

    for smpl, xcenter, ycenter in zip(smplist, xcenter_list, ycenter_list):
        print(f'Moving sample {smpl} to center position (x = {xcenter}, y = {ycenter})')
        motorx.move(xcenter)
        motory.move(ycenter)

        # Define x and y start/stop positions for the grid scan
        xstart = xcenter - xrange / 2
        xstop = xcenter + xrange / 2
        ystart = ycenter - yrange / 2
        ystop = ycenter + yrange / 2

        # Apply filters based on sample
        if smpl in smpl_h:
            if flt_h is not None:
                print(f'Applying special filter set {flt_h} for sample {smpl}')
                xpd_flt_set(flt_h)
        else:
            if flt_l is not None:
                print(f'Applying default filter set {flt_l} for sample {smpl}')
                xpd_flt_set(flt_l)

        # Add delay after moving the sample and setting filters
        time.sleep(delay)

        # Log the scanning process
        print(f"Starting grid scan for sample {smpl}...")
        print(f"X-axis: from {xstart} to {xstop}, points: {xpoints}")
        print(f"Y-axis: from {ystart} to {ystop}, points: {ypoints}")
        print(f"Exposure time per point: {exp_time} seconds")

        # Create the grid scan plan and execute the scan
        plan = gridplan(exp_time, xstart, xstop, xpoints, ystart, ystop, ypoints, motorx=motorx, motory=motory, md=md,
                        dets=dets)
        xrun(smpl, plan)


def xyposscan(smpl, exp_time, posxlist, posylist, motorx=sample_x, motory=sample_y, md=None, dets=None):

    """ Perform a multiple points scan for one sample by moving to predefined x and y positions.

        Parameters:
            smpl (str or int): Sample ID.
            exp_time (float): Total exposure time (in seconds) for each measurement.
            posxlist (list): List of x positions for the sample.
            posylist (list): List of y positions for the sample.
            motorx (object, optional): Motor object to move the sample along the x-axis. Default is `sample_x`.
            motory (object, optional): Motor object to move the sample along the y-axis. Default is `sample_y`.
            md (dict, optional): Metadata to be associated with the scan. Default is None.
            det (list, optional): Extra detectors to record during the scan. Default is None.

        Example:
            >>> xyposscan(1, 5.0, [0, 10, 20], [0, 15, 25])

    """

    # Ensure posxlist and posylist have the same length
    if len(posxlist) != len(posylist):
        raise ValueError("posxlist and posylist must have the same length")

    # Logging the initial information
    print(f"Starting XY position scan for sample {smpl}...")
    print(f"Number of positions: {len(posxlist)}")
    print(f"Exposure time per position: {exp_time} seconds")

    # Create the plan using xyposplan and execute the plan using xrun
    plan = xyposplan(exp_time, posxlist, posylist, motorx=motorx, motory=motory, md=md, dets=dets)
    xrun(smpl, plan)


#_____2 detectors scripts


def mrun_2det(smplist_pdf, smplist_xrd, posxlist, exp_pdf, exp_xrd, posylist=None, smpl_h=None, delay=1,
               pdf_pos=[0, 255], xrd_pos=[400, 275], num_pdf=1, num_xrd=1, pdf_flt_h=None, pdf_flt=None, xrd_flt=None,
               motorx=sample_x, motory=sample_y, pdf_frame_acq=0.2, xrd_frame_acq=0.2, dets=[pe1_z], confirm=True):
    '''
    Multiple samples, do pdf and xrd for one sample, then move to the next sample
    Parameters:
        smplist_pdf: List of sample names for PDF measurement.
        smplist_xrd: List of sample names for XRD measurement.
        posxlist: List of positions of each sample.
        exp_pdf: Total exposure time for PDF measurement (seconds).
        exp_xrd: Total exposure time for XRD measurement (seconds).
        posylist: Optional list of Y positions for the samples (default: None for 1D positioning).
        smpl_h: List of high-scattering samples needing special filters for PDF (optional).
        delay: Delay time between each sample during PDF measurements (default: 1 second).
        pdf_pos: Position of the PDF detector [pe1_x, pe1_z].
        xrd_pos: Position of the XRD detector [pe1_x, pe1_z].
        num_pdf: Number of data points to take for PDF measurements.
        num_xrd: Number of data points to take for XRD measurements.
        pdf_flt_h: Filter set for high-scattering PDF samples (default: None).
        pdf_flt: Filter set for normal PDF samples (default: None).
        xrd_flt: Filter set for XRD samples (default: None).
        motorx: Motor to move samples, default is sample_x.
        pdf_frame_acq: Frame acquisition time for PDF detector (default: 0.2).
        xrd_frame_acq: Frame acquisition time for XRD detector (default: 0.2).
        dets: List of detectors and motors to record in the data table.
    '''

    # Validate list lengths for sample list and position list
    if len(smplist_pdf) != len(smplist_xrd) or len(posxlist) != len(smplist_xrd):
        raise ValueError("smplist_pdf, smplist_xrd, posxlist must have the same length")

    if posylist and (len(posxlist) != len(posylist)):
        raise ValueError("posxlist and posylist must have the same length if posylist is provided")
    
    # Validate filter settings if high scattering samples are provided
    if smpl_h is not None and (pdf_flt_h is None or pdf_flt is None):
        raise ValueError("If smpl_h is provided, both pdf_flt_h and pdf_flt must also be provided.")

    # Ensure that if pdf_flt is provided, xrd_flt are provided
    if pdf_flt is not None and xrd_flt is None:
        raise ValueError("If pdf_flt is provided, both xrd_flt must also be provided.")

    # Ask the user confirm detector positions
    if confirm is True:
        confirmation = input(
            f"Confirm detector positions:\n"
            f"  - PDF Position = {pdf_pos}\n"
            f"  - XRD Position = {xrd_pos}\n"
            f"Proceed with these settings? (y/n): ").strip().lower()

        if confirmation not in ['y', 'yes']:
            print("User chose not to proceed with the measurements.")
            return  # Exit the function if the user doesn't confirm

    if smpl_h is None:
        smpl_h = []

    if posylist is not None:
        dets = dets + [motorx, motory]
    else:
        dets = dets + [motorx]

    for smpl_xrd, smpl_pdf, posx, posy in zip(smplist_xrd, smplist_pdf, posxlist, posylist or [None] * len(posxlist)):
        print(f' {smpl_xrd}, {smpl_pdf}, in position {posx}')
        motorx.move(posx)
        if posy is not None:
            motory.move(posy)
        time.sleep(delay)
        # Determine the appropriate filter set for PDF
        pdf_flt_selected = pdf_flt_h if smpl_pdf in smpl_h else pdf_flt

        # Run the PDF and XRD measurements using run_2det
        run_2det(
            smpl_pdf=smpl_pdf,
            smpl_xrd=smpl_xrd,
            exp_pdf=exp_pdf,
            exp_xrd=exp_xrd,
            pdf_pos=pdf_pos,
            xrd_pos=xrd_pos,
            num_pdf=num_pdf,
            num_xrd=num_xrd,
            pdf_flt=pdf_flt_selected,
            xrd_flt=xrd_flt,
            dets=dets,
            pdf_frame_acq=pdf_frame_acq,
            xrd_frame_acq=xrd_frame_acq,
            confirm=False
        )

def mrun_2det_batch(smplist_pdf, smplist_xrd, posxlist, posylist=None, 
                      exp_pdf=None, exp_xrd=None, delay=1, 
                      smpl_h=None, pdf_pos=[0, 255], xrd_pos=[400, 275], 
                      num_pdf=1, num_xrd=1, pdf_flt_h=None, 
                      pdf_flt=None, xrd_flt=None, motorx=sample_x, 
                      motory=sample_y, pdf_frame_acq=0.2, 
                      xrd_frame_acq=0.2, dets=None, 
                      pdf_only_posx=None, xrd_only_posx=None,
                      scan_order="pdf_first", confirm=True):
    '''
    Function for performing PDF and/or XRD batch measurements, measure all sample PDF first, then XRD. 
    Supporting both 1D and 2D positioning, and handling samples requiring only PDF or only XRD measurements.

    Parameters:
        smplist_pdf: List of sample names for PDF measurement.
        smplist_xrd: List of sample names for XRD measurement.
        posxlist: List of X positions for the samples.
        posylist: Optional list of Y positions for the samples (default: None for 1D positioning).
        exp_pdf: Exposure time for PDF measurement (default: None if no PDF measurement is required).
        exp_xrd: Exposure time for XRD measurement (default: None if no XRD measurement is required).
        delay: Delay time between each measurement (default: 1 second).
        smpl_h: List of high-scattering samples needing special filters for PDF (optional).
        pdf_pos, xrd_pos: Positions of PDF and XRD detectors, respectively.
        num_pdf, num_xrd: Number of data points for PDF and XRD measurements.
        pdf_flt_h: Filter set for high-scattering PDF samples (default: None).
        pdf_flt: Filter set for normal PDF samples (default: None).
        xrd_flt: Filter set for XRD samples (default: None).
        motorx, motory: Motors to move samples in X and Y directions, respectively.
        pdf_frame_acq, xrd_frame_acq: Frame acquisition times for PDF and XRD detectors (default: 0.2).
        dets: List of detectors and motors to record in the data table.
        pdf_only_posx: List of samples requiring PDF measurements only (default: None).
        xrd_only_posx: List of samples requiring XRD measurements only (default: None).
        scan_order: Specify the order of scans, either "xrd_first" or "pdf_first" (default: "xrd_first").
        confirm: Whether to prompt for confirmation of settings (default: True).
    '''
    
    # Validate sample list lengths
    if len(smplist_pdf) != len(posxlist):
        raise ValueError("smplist_pdf and posxlist must have the same length")
    if len(smplist_xrd) != len(posxlist):
        raise ValueError("smplist_xrd and posxlist must have the same length")
    if posylist and (len(posxlist) != len(posylist)):
        raise ValueError("posxlist and posylist must have the same length if posylist is provided")

    # Initialize optional parameters
    if pdf_only_posx is None:
        pdf_only_posx = []
    if xrd_only_posx is None:
        xrd_only_posx = []
    if dets is None:
        dets=[]
    if posylist is not None:
        dets = dets + [motorx, motory]
    else:
        dets = dets + [motorx]

    # Confirm settings
    if confirm:
        confirmation = input(
            f"Confirm detector positions:\n"
            f"  - PDF Position = {pdf_pos}\n"
            f"  - XRD Position = {xrd_pos}\n"
            f"Proceed with these settings? (y/n): ").strip().lower()

        if confirmation not in ['y', 'yes']:
            print("User chose not to proceed with the measurements.")
            return

    # Disable automatic calibration loading
    glbl["auto_load_calib"] = False

    # Load calibration files
    xrd_calib = load_calibration_md('config_base/xrd.poni')
    pdf_calib = load_calibration_md('config_base/pdf.poni')

    # Detector positions
    #pdf_pe1x, pdf_pe1z = pdf_pos
    #xrd_pe1x, xrd_pe1z = xrd_pos
    _, xrd_pe1z = xrd_pos
    def move_to_position(posx, posy=None):
        """Helper to move motors to the specified position."""
        motorx.move(posx)
        if posy is not None:
            motory.move(posy)

    def perform_xrd_scan():
        """Perform XRD measurements."""
        if not exp_xrd:
            return
        print('Starting XRD scan...')
        set_xrd(xrd_pos=xrd_pos, frame_acq_time=xrd_frame_acq, confirm=False)
        for smpl, posx, posy in zip(smplist_xrd, posxlist, posylist or [None] * len(posxlist)):
            if posx in pdf_only_posx:
                continue  # Skip PDF-only samples
            print(f'XRD: sample: {smpl}, position: ({posx}, {posy})')
            move_to_position(posx, posy)
            plan = plan_with_calib([pe2c] + dets, exp_xrd, num_xrd, xrd_calib)
            xrun(smpl, plan)

    def perform_pdf_scan():
        """Perform PDF measurements."""
        if not exp_pdf:
            return
        print('Starting PDF scan...')
        set_pdf(pdf_pos=pdf_pos, safe_out=xrd_pe1z, frame_acq_time=pdf_frame_acq, confirm=False)
        for smpl, posx, posy in zip(smplist_pdf, posxlist, posylist or [None] * len(posxlist)):
            if posx in xrd_only_posx:
                continue  # Skip XRD-only samples
            print(f'PDF: sample: {smpl}, position: ({posx}, {posy})')
            move_to_position(posx, posy)
            if smpl in (smpl_h or []):
                xpd_flt_set(pdf_flt_h)
            elif pdf_flt is not None:
                xpd_flt_set(pdf_flt)
            time.sleep(delay)
            plan = plan_with_calib([pe1c] + dets, exp_pdf, num_pdf, pdf_calib)
            xrun(smpl, plan)

    # Execute scans based on the specified order
    if scan_order == "xrd_first":
        perform_xrd_scan()
        perform_pdf_scan()
    elif scan_order == "pdf_first":
        perform_pdf_scan()
        perform_xrd_scan()
    else:
        raise ValueError("Invalid scan_order. Use 'xrd_first' or 'pdf_first'.")

    # Reset calibration loading
    glbl["auto_load_calib"] = True


def run_2det(smpl_pdf, smpl_xrd, exp_pdf, exp_xrd, pdf_pos=[0, 255], xrd_pos=[400, 275], num_pdf=1, num_xrd=1,
             pdf_flt=None, xrd_flt=None, pdf_frame_acq=0.2, xrd_frame_acq=0.2, dets=None, confirm=True):
    '''
      Perform PDF and XRD measurements for one sample using two detectors.

    Parameters:
        smpl_pdf: sample names for PDF measurement.
        smpl_xrd: sample names for XRD measurement.
        exp_pdf: Total exposure time for PDF measurement (seconds).
        exp_xrd: Total exposure time for XRD measurement (seconds).
        pdf_pos: Position of the PDF detector [pe1_x, pe1_z].
        xrd_pos: Position of the XRD detector [pe1_x, pe1_z].
        num_pdf: Number of data points to take for PDF measurements.
        num_xrd: Number of data points to take for XRD measurements.
        pdf_flt: Filter set for normal PDF samples (default: None).
        xrd_flt: Filter set for XRD samples (default: None).
        motor: Motor to move samples, default is sample_x.
        pdf_frame_acq: Frame acquisition time for PDF detector (default: 0.2).
        xrd_frame_acq: Frame acquisition time for XRD detector (default: 0.2).
        dets: List of detectors and motors to record in the data table.

      Returns:
      --------
      None
    '''

    # Input Validation
    if pdf_flt is not None and xrd_flt is None:
        raise ValueError("If pdf_flt is provided, xrd_flt must be provided.")

    if confirm is True:
        # Ask the user to double-check the pdf_pos and xrd_pos values
        confirmation = input(
            f"Confirm detector positions:\n"
            f"  - PDF Position = {pdf_pos}\n"
            f"  - XRD Position = {xrd_pos}\n"
            f"Proceed with these settings? (y/n): ").strip().lower()

        if confirmation not in ['y', 'yes']:
            print("User chose not to proceed with the measurements.")
            return  # Exit the function if the user doesn't confirm
    
    if dets is None:
        dets=[]
        
    # Disable auto-loading calibration
    glbl["auto_load_calib"] = False

    # Load calibration files for both PDF and XRD
    xrd_calib = load_calibration_md('config_base/xrd.poni')
    pdf_calib = load_calibration_md('config_base/pdf.poni')

    #pdf_pe1x, pdf_pe1z = pdf_pos
    #xrd_pe1x, xrd_pe1z = xrd_pos
    _, xrd_pe1z = xrd_pos
    # PDF Scan
    print('pdf scan')
    # set PDF configuration
    set_pdf(pdf_pos=pdf_pos, safe_out=xrd_pe1z, frame_acq_time=pdf_frame_acq, confirm=False)

    if pdf_flt is not None:
        xpd_flt_set(pdf_flt)  # set filter for pdf if provided
    plan = plan_with_calib([pe1c] + dets, exp_pdf, num_pdf, pdf_calib)
    xrun(smpl_pdf, plan)

    # XRD Scan
    print('xrd scan')
    set_xrd(xrd_pos=xrd_pos, frame_acq_time=xrd_frame_acq, confirm=False)

    if xrd_flt is not None:
        xpd_flt_set(xrd_flt)

    plan = plan_with_calib([pe2c] + dets, exp_xrd, num_xrd, xrd_calib)
    xrun(smpl_xrd, plan)
    # Re-enable auto-loading calibration
    glbl["auto_load_calib"] = True


def set_xrd(xrd_pos=[400, 280], frame_acq_time=0.2, confirm=True):

    ''' Set the acquisition system for XRD measurements.

    This function moves the PE1 detector out of the way by adjusting the x and z positions and
    configures the XPD system to use the PE2C detector with the specified frame acquisition time.

    Parameters:
        xrd_pos (list): Position of the PE1 detector [pe1_x, pe1_z] for XRD measurement Default is [400, 280].
        frame_acq_time (float): frame acquisition time. Default is 0.2
    '''
    xrd_pe1x, xrd_pe1z = xrd_pos

    if confirm is True:
        # Ask the user to double-check the pdf_pos and xrd_pos values
        confirmation = input(
            f"Confirm detector positions:\n"
            f"  - XRD Position = {xrd_pos}\n"
            f"Proceed with these settings? (y/n): ").strip().lower()
        
        if confirmation not in ['y', 'yes']:
            print("User chose not to proceed with the measurements.")
            return  # Exit the function if the user doesn't confirm
    
    if not (is_motor_at_position(pe1_x, xrd_pe1x)):
        print(f"Setting up PE2 detector for XRD measurement. Moving PE1 out.")
        pe1_z.move(xrd_pe1z)
        pe1_x.move(xrd_pe1x)
    else:
        print(f'PE1 is in position, setting up PE2 detector for XRD measurement')

    xpd_configuration['area_det'] = pe2c

    #if glbl['frame_acq_time'] != frame_acq_time:
    glbl['frame_acq_time'] = frame_acq_time
    time.sleep(3)    


def set_pdf(pdf_pos=[0, 255], safe_out=280, frame_acq_time=0.2, confirm=True):

    ''' Set up the acquisition system for PDF (Pair Distribution Function) measurements.

    This function moves the PE1 detector to the specified positions for PDF measurements
    and updates the XPD configuration to use PE1C as the area detector with the specified
    frame acquisition time.

    Parameters:
        pdf_pos (list): Position of the PE1 detector [pe1_x, pe1_z] for PDF measurement, Default is [0, 255].
        safe_out (float): The safe z position to move PE1 to before adjusting x and z. Default is 280.
        frame_acq_time (float): The frame acquisition time to set in the global configuration. Default is 0.2 seconds.

    '''
    if confirm is True:
        # Ask the user to double-check the pdf_pos and xrd_pos values
        confirmation = input(
            f"Confirm detector positions:\n"
            f"  - PDF Position = {pdf_pos}\n"
            f"  - safe z out = {safe_out}\n"
            f"Proceed with these settings? (y/n): ").strip().lower()
        if confirmation not in ['y', 'yes']:
            print("User chose not to proceed with the measurements.")
            return  # Exit the function if the user doesn't confirm

    pdf_pe1x, pdf_pe1z = pdf_pos
    if not (is_motor_at_position(pe1_x, pdf_pe1x)) or not (is_motor_at_position(pe1_z, pdf_pe1z)):
        print(f"Setting up PE1 detector for PDF measurement. Moving PE1 to position {pdf_pos}.")
        pe1_z.move(safe_out)
        pe1_x.move(pdf_pe1x)
        pe1_z.move(pdf_pe1z)
    else:
        print(f"PE1 in position, setting up PE1 detector for PDF measurement.")
    
    xpd_configuration['area_det'] = pe1c

    #if glbl['frame_acq_time'] != frame_acq_time:
    glbl['frame_acq_time'] = frame_acq_time
    time.sleep(3)  


def run_xrd(smpl, exp_xrd, num=1, xrd_pos=[400, 280], calib_file='config_base/xrd.poni',
            frame_acq_time=0.2, dets=None, confirm=True):
    ''' Run one XRD measurement with specified calib_file,
        setup xrd configuration first if was not in xrd configuration yet.

    Parameters:
        smpl (int): Sample index to run the XRD measurement on.
        exp_xrd (float): Total exposure time (in seconds).
        num (int, optional): Number of measurements to take. Default is 1.
        xrd_pos (list, optional): List of PE1 x and z positions. Default is [400, 280].
        calib_file (str, optional): Path to the calibration file for XRD measurement. Default is 'config_base/xrd.poni'.
        frame_acq_time (float, optional): Frame acquisition time. Default is 0.2.
        dets (list, optional): Extra detectors (e.g., temperature controller, motor positions) to read. Default is None.


    '''

    if dets is None:
        dets = []

    set_xrd(xrd_pos=xrd_pos, frame_acq_time=frame_acq_time, confirm=confirm)

    # Disable automatic calibration loading
    glbl["auto_load_calib"] = False

    # Load the calibration file
    try:
        xrd_calib = load_calibration_md(calib_file)
        print(f"Calibration file {calib_file} loaded successfully.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Calibration file '{calib_file}' not found.")
    except Exception as e:
        raise RuntimeError(f"Failed to load calibration file: {e}")

    # Run the measurement plan with calibration
    plan = plan_with_calib([pe2c] + dets, exp_xrd, num, xrd_calib)
    xrun(smpl, plan)

    # Re-enable automatic calibration loading
    glbl["auto_load_calib"] = True


def run_pdf(smpl, exp_pdf, num=1, pdf_pos=[0, 255], safe_out=280, calib_file='config_base/pdf.poni',
            frame_acq_time=0.2, dets=[pe1_z], confirm=True):

    ''' Run one PDF measurement, moving the PE1 detector to the specified position
        and configuring the system for PDF measurements.

    Parameters:
        smpl (int): Sample index to run the PDF measurement on.
        exp_pdf (float): Total exposure time (in seconds).
        num (int, optional): Number of measurements to take. Default is 1.
        pdf_pos (list, optional): List of PE1 x and z positions for the PDF measurement. Default is [0, 255].
        safe_out (float, optional): The safe z position to move PE1 to before adjusting x and z. Default is 280.
        calib_file (str, optional): Path to the calibration file for the PDF measurement. Default is 'config_base/pdf.poni'.
        frame_acq_time (float, optional): Frame acquisition time. Default is 0.2 seconds.
        dets (list, optional): Extra detectors (e.g., temperature controller, motor positions). Default is [pe1_z].

    '''
    # set PDF configuration
    set_pdf(pdf_pos=pdf_pos, safe_out=safe_out, frame_acq_time=frame_acq_time, confirm=confirm)

    # Disable automatic calibration loading
    glbl["auto_load_calib"] = False

    # Load the calibration file
    try:
        pdf_calib = load_calibration_md(calib_file)
        print(f"Calibration file {calib_file} loaded successfully.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Calibration file '{calib_file}' not found.")
    except Exception as e:
        raise RuntimeError(f"Failed to load calibration file: {e}")

    # Run the measurement plan with calibration
    plan = plan_with_calib([pe1c] + dets, exp_pdf, num, pdf_calib)
    xrun(smpl, plan)

    # Re-enable automatic calibration loading
    glbl["auto_load_calib"] = True

def is_motor_at_position(motor, target_position, tolerance=0.01):
    """
    Check if a motor is at the specified target position within a tolerance.

    Parameters:
        motor: The motor object to check (e.g., `pe1_x`).
        target_position (float): The target position to compare against.
        tolerance (float): The allowable deviation from the target position.

    Returns:
        bool: True if the motor is within the tolerance of the target position, False otherwise.
    """
    return abs(motor.position - target_position) <= tolerance
