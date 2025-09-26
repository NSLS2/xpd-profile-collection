def ion_chamber_in(y=36):
    " move ion chamber in to the beam"
    #ecal_x.move(x)
    ecal_y.move(y)

def ion_chamber_out(y=-10):
    """ move ion chamber out to let laser in"""
    #ecal_x.move(x)
    ecal_y.move(y)

def takeone(sample, exp_time, num=1, delay_num=0, dets=[ion_chamber] ):
    """ take one data, collect both det and ion_chamber data

    parameter:
    sample (int): sample name(index) in sample list
    dets (list): list of detectors, default: [ion_chamber]
    exp_time (float): exposure time in seconds

    """
    area_det = xpd_configuration['area_det']
    dets=[area_det] + dets
    delay_num = delay_num + exp_time
    plan = ct_motors_plan(dets, exp_time, num=num, delay=delay_num)
    xrun(sample, plan)


def plan_with_calib(dets, exp_time, num, calib_file, md=None):
    """ plan for a scan with detectors and apply calibration from a file.

    Args:
        dets (list): List of detectors to be used during the scan.
        exp_time (float): Exposure time (in seconds) for each reading.
        num (int): Number of readings to take.
        calib_file (str): Path to the calibration file.

    Example:
        plan_with_calib([pec1, det2], 5.0, 10, calib_file='xrd.poni')
    """
    # Configure the area detector
    (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exp_time)

    # Metadata handling
    _md = {

        "sp_time_per_frame": acq_time,
        "sp_num_frames": num_frame,
        "sp_requested_exposure": exp_time,
        "sp_computed_exposure": computed_exposure,
    }

    _md.update(md or {})

    if ion_chamber in dets:
        yield from bps.mv(ecal_y, 36)
        if ion_chamber.period.get()!= acq_time:
            yield from bps.mv(ion_chamber.period, acq_time)
        ion_chamber.trigs_to_average = num_frame

    motors = dets[1:]
    plan = count_with_calib(dets, num, calibration_md=calib_file, md=_md)
    plan = bpp.subs_wrapper(plan, LiveTable(motors))
    yield from plan


def count_with_calib(detectors: list, num: int = 1, delay: float = None, *, calibration_md: dict = None,
                     md: dict = None):
    """
    Take one or more readings from detectors with shutter control and calibration metadata injection.

    Parameters
    ----------
    detectors : list
        list of 'readable' objects

    num : integer, optional
        number of readings to take; default is 1

        If None, capture data until canceled

    delay : iterable or scalar, optional
        Time delay in seconds between successive readings; default is 0.

    calibration_md :
        The calibration data in a dictionary. If not applied, the function is a normal `bluesky.plans.count`.

    md : dict, optional
        metadata

    Notes
    -----
    If ``delay`` is an iterable, it must have at least ``num - 1`` entries or
    the plan will raise a ``ValueError`` during iteration.
    """
    if md is None:
        md = dict()
    if calibration_md is not None:
        md["calibration_md"] = calibration_md

    def _per_shot(_detectors):
        yield from open_shutter_stub()
        yield from bps.one_shot(_detectors)
        yield from close_shutter_stub()
        return

    try:
        plan = bp.count(detectors, num, delay, md=md, per_shot=_per_shot)
        sts = yield from plan
    except Exception as error:
        raise error
    return sts


def ct_motors_plan(dets, exp_time, num=1, delay=0, md=None):
    """plan for performing multiple readings of detectors (e.g., temperature controller, motor positions) and display results
    in real-time using LiveTable.

    Parameters:
        dets (list): List of detectors to be read during the scan (e.g., area detector, temperature controller, motors).
        exp_time (float): Exposure time (in seconds) for each reading.
        num (int, optional): Number of readings to take. Default is 1.
        delay (float, optional): Delay (in seconds) between successive readings. Default is 0.
        md (dict, optional): Additional metadata to attach to the scan. Default is None.

    Example:
        ct_motors_plan([area_det, T_controller, motor], 5.0, num=10, delay=1)

    """
    # Configure the area detector
    (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exp_time)

    # Metadata handling
    _md = {

        "sp_time_per_frame": acq_time,
        "sp_num_frames": num_frame,
        "sp_requested_exposure": exp_time,
        "sp_computed_exposure": computed_exposure,
    }

    _md.update(md or {})

    if ion_chamber in dets:
        yield from bps.mv(ecal_y, 36)
        if ion_chamber.period.get()!= acq_time:
            yield from bps.mv(ion_chamber.period, acq_time)
        ion_chamber.trigs_to_average = num_frame

    motors = dets[1:]
    plan = bp.count(dets, num, delay, md=_md)
    plan = bpp.subs_wrapper(plan, LiveTable(motors))
    plan = bpp.plan_mutator(plan, inner_shutter_control)
    yield from plan


def lineplan(exp_time, xstart, xend, xpoints, motor=None, md=None, dets=None):
    """ plan for 1D line scan by moving a motor between two positions and recording measurements at multiple points.

    Parameters:
        exp_time (float): Total exposure time (in seconds) for each measurement point.
        xstart (float): Starting position for the motor.
        xend (float): Ending position for the motor.
        xpoints (int): Number of points to measure along the line.
        motor (object, optional): Motor object to move the sample along the line. Default is `sample_y`.
        md (dict, optional): Additional metadata to attach to the scan.
        dets (list, optional): List of extra detectors to record during the scan.

    Example:
        lineplan(5.0, 0, 10, 5, motor=sample_y)

    """
    if motor is None:
        motor = sample_y

    if dets is None:
        dets = []
    # Configure the area detector
    (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exp_time)

    # Metadata handling
    _md = {

        "sp_time_per_frame": acq_time,
        "sp_num_frames": num_frame,
        "sp_requested_exposure": exp_time,
        "sp_computed_exposure": computed_exposure,
    }
    _md.update(md or {})

    if ion_chamber in dets:
        yield from bps.mv(ecal_y, 36)
        if ion_chamber.period.get()!= acq_time:
            yield from bps.mv(ion_chamber.period, acq_time)
        ion_chamber.trigs_to_average = num_frame

    area_det = xpd_configuration['area_det']

    plan = bp.scan([area_det] + dets, motor, xstart, xend, xpoints, md=_md)
    plan = bpp.subs_wrapper(plan, LiveTable([motor] + dets))
    plan = bpp.plan_mutator(plan, inner_shutter_control)
    yield from plan


def gridplan(exp_time, xstart, xstop, xpoints, ystart, ystop, ypoints, motorx=None, motory=None, md=None,
             dets=None):

    """ plan for 2D grid scan by moving two motors across specified ranges and collecting data using detectors.

    Example:
        gridplan(5.0, 0, 10, 5, 0, 10, 5)

    Parameters:
        exp_time (float): Total exposure time (in seconds) for each measurement point.
        xstart (float): Starting position for the x-axis (motorx).
        xstop (float): Ending position for the x-axis (motorx).
        xpoints (int): Number of points to measure along the x-axis.
        ystart (float): Starting position for the y-axis (motory).
        ystop (float): Ending position for the y-axis (motory).
        ypoints (int): Number of points to measure along the y-axis.
        motorx (object, optional): Motor object to move the sample along the x-axis. Default is `sample_x`.
        motory (object, optional): Motor object to move the sample along the y-axis. Default is `sample_y`.
        md (dict, optional): Additional metadata to attach to the scan.
        dets (list, optional): List of extra detectors to record during the scan.
    """
    if motorx is None:
        motorx = sample_x

    if motory is None:
        motory=sample_y

    if dets is None:
        dets = []

    # Configure the ara detector
    (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exp_time)

    # Metadata
    _md = {
        "sp_time_per_frame": acq_time,
        "sp_num_frames": num_frame,
        "sp_requested_exposure": exp_time,
        "sp_computed_exposure": computed_exposure,
    }
    _md.update(md or {})

    if ion_chamber in dets:
        if ion_chamber.period.get()!= acq_time:
            yield from bps.mv(ion_chamber.period, acq_time)
        ion_chamber.trigs_to_average = num_frame

    area_det = xpd_configuration['area_det']

    plan = bp.grid_scan([area_det]+dets, motory, ystart, ystop, ypoints, motorx, xstart, xstop, xpoints, True, md=_md)
    plan = bpp.subs_wrapper(plan, LiveTable([motorx, motory]+dets))
    plan = bpp.plan_mutator(plan, inner_shutter_control)
    yield from plan


def xyposplan(exp_time, posxlist, posylist, motorx=None, motory=None, md=None, dets=None):
    """ plan for a scan over a set of predefined x and y positions.

    Parameters:
        exp_time (float): Total exposure time (in seconds) for each measurement.
        posxlist (list): List of x positions for the sample.
        posylist (list): List of y positions for the sample.
        motorx (object, optional): Motor object to move the sample along the x-axis. Default is `sample_x`.
        motory (object, optional): Motor object to move the sample along the y-axis. Default is `sample_y`.
        md (dict, optional): Additional metadata to attach to the scan.
        dets (list, optional): List of extra detectors to record during the scan.

    Example:
        plan = xyposplan(5, [10, 13, 20], [1.2, 1.3, 1.4])

       """
    # Input validation
    if len(posxlist) != len(posylist):
        raise ValueError("posxlist and posylist must have the same length")

    if motorx is None:
        motorx = sample_x

    if motory is None:
        motory=sample_y

    if dets is None:
        dets = []

    # Configure detector
    (num_frame, acq_time, computed_exposure) = yield from _configure_area_det(exp_time)

    # Metadata
    _md = {

        "sp_time_per_frame": acq_time,
        "sp_num_frames": num_frame,
        "sp_requested_exposure": exp_time,
        "sp_computed_exposure": computed_exposure,
    }
    _md.update(md or {})
    area_det = xpd_configuration['area_det']

    if ion_chamber in dets:
        yield from bps.mv(ecal_y, 36)
        if ion_chamber.period.get()!= acq_time:
            yield from bps.mv(ion_chamber.period, acq_time)
        ion_chamber.trigs_to_average = num_frame

    plan = bp.list_scan([area_det]+dets, motorx, posxlist, motory, posylist, md=_md)
    plan = bpp.subs_wrapper(plan, LiveTable([motorx, motory]+dets))
    plan = bpp.plan_mutator(plan, inner_shutter_control)
    yield from plan

def take_one_dark(sample, exp_time, dets=[ion_chamber]):
    """ take one data with dark image, then set dark window to 1000 minutes

    parameter:
    sample (int): sample name(index) in sample list
    dets (list): list of detectors
    exp_time (float): exposure time in seconds

    """
    area_det = xpd_configuration['area_det']
    dets=[area_det] + dets
    glbl['dk_window'] = 0.1
    plan = ct_motors_plan(dets, exp_time)
    xrun(sample, plan)
    glbl['dk_window'] = 1000
    print("dark window is set to 1000 minutes")
# ------------------------------------------------------------------------------------------------------------------------
from packaging import version

def append_compatible(df, new_data, sort=False):
    """
    Append new_data to df in a way that's compatible with different pandas versions.

    Parameters:
        df (DataFrame): The original DataFrame to append data to.
        new_data (DataFrame): The new data to append to the original DataFrame.
        sort (bool): Whether to sort columns or not (for pandas <= 1.4.x).

    Returns:
        DataFrame: The resulting DataFrame after appending new_data.
    """
    pandas_version = pd.__version__

    if version.parse(pandas_version) >= version.parse("2.0.0"):
        # For pandas >= 2.0.0
        return df._append(new_data, sort=sort)
    else:
        # For pandas < 2.0.0
        return df.append(new_data, sort=sort)

def save_tb_xlsx(sample_name, starttime, endtime, readable_time=False):
    data_dir = "./tiff_base/"

    if not readable_time:
        startstring = datetime.datetime.fromtimestamp(float(starttime)).strftime('%Y-%m-%d %H:%M:%S')
        endstring = datetime.datetime.fromtimestamp(float(endtime)).strftime('%Y-%m-%d %H:%M:%S')
    else:
        startstring = starttime
        endstring = endtime

    hdrs = db(since=startstring, until=endstring)
    timestamp = time.time()
    timestring_filename = datetime.datetime.fromtimestamp(float(timestamp)).strftime('%Y%m%d_%H%M%S')
    file_name = data_dir + 'sample_' + str(sample_name) + '_' + timestring_filename + ".xlsx"
    print(len(list(hdrs)))

    DBout = None  # Initialize DBout
    for idx, hdr in enumerate(hdrs):
        try:
            tb = hdr.table()
            uid6 = hdr.start['uid'][0:6]
            tb['uid6'] = uid6
            if idx == 0:
                DBout = tb
            else:
                # Use append_compatible to handle Pandas version differences
                DBout = append_compatible(DBout, tb, sort=False)

        except IndexError:
            pass
    with pd.ExcelWriter(file_name) as writer:
        DBout.to_excel(writer, sheet_name='Sheet1')


def save_position_to_sample_list(smpl_list, pos_list, filename):
    """ Update the 'User supplied tags' column in the Excel file with positions from pos_list.

    Parameters:
        smpl_list (list): List of sample indices (0-based).
        pos_list (list): List of positions to be added to the corresponding samples in 'User supplied tags'.
        filename (str): Name of the Excel file to read and update.

    Returns:
        None
    """
    # file_name='300001_sample.xlsx'

    file_dir = './Import/'
    file_name = os.path.join(file_dir, filename)
    if not os.path.isfile(file_name):
        raise FileNotFoundError(f"The file '{file_name}' does not exist.")

    ind_list = [x + 1 for x in smpl_list]
    pos_str = [str(x) for x in pos_list]
    f_out = file_name

    # Read the Excel file
    f = pd.read_excel(file_name)
    tags = pd.DataFrame(f, columns=['User supplied tags']).fillna(0).values

    # Update the tags with the positions from pos_list
    for i, ind in enumerate(ind_list):
        if ind < len(tags):
            if tags[ind][0] != 0:
                tag_str = str(tags[ind][0])
                tags[ind][0] = tag_str + ',pos=' + str(pos_str[i])
            else:
                tags[ind][0] = 'pos=' + str(pos_str[i])

    #Flatten the updated tags
    tags = list(flatten(tags))

    # Create a new DataFrame with the updated tags
    new_f = pd.DataFrame({'User supplied tags': tags})

    # Update the original DataFrame with the new tags
    f.update(new_f)

    with pd.ExcelWriter(f_out) as writer:
        f.to_excel(writer, index=False)

    return None


def xpd_flt_set(flt_p):
    if flt_p[0] == 0:
        fb.flt1.set('Out')
    else:
        fb.flt1.set('In')
    if flt_p[1] == 0:
        fb.flt2.set('Out')
    else:
        fb.flt2.set('In')
    if flt_p[2] == 0:
        fb.flt3.set('Out')
    else:
        fb.flt3.set('In')
    if flt_p[3] == 0:
        fb.flt4.set('Out')
    else:
        fb.flt4.set('In')

    print('filter bank setting:', fb.flt1.get(), fb.flt2.get(), fb.flt3.get(), fb.flt4.get())

    return None


def xpd_flt_read():
    flt_p = [0, 0, 0, 0]
    if fb.flt1.get() == 'Out':
        flt_p[0] = 0
    else:
        flt_p[0] = 1
    if fb.flt2.get() == 'Out':
        flt_p[1] = 0
    else:
        flt_p[1] = 1

    if fb.flt3.get() == 'Out':
        flt_p[2] = 0
    else:
        flt_p[2] = 1
    if fb.flt4.get() == 'Out':
        flt_p[3] = 0
    else:
        flt_p[3] = 1

    return flt_p
