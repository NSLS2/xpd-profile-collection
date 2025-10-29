from lmfit import Model, Parameter, Parameters
from lmfit.lineshapes import voigt

def initialize_ecal():
    '''
        Prepare for an energy calibration scan (Ecal)
    '''
    # move the filters in
    # move crystal in
    # open the fast shutter
    print("Initializing ecal, moving setup in")
    print("Moving filters in")
    yield from bps.mov(shctl1, 60)
    yield from bps.mov(ecal_x, 100)
    yield from bps.mov(ecal_y, 0)
    yield from bps.mov(fb.flt1, 1)
    yield from bps.mov(fb.flt2, 1)
    yield from bps.mov(fb.flt3, 1)
    yield from bps.mov(fb.flt4, 1)

def finalize_ecal():
    # move the filters in
    # move crystal in
    # open the fast shutter
    print("Finalizing ecal, moving setup out")
    print("Moving filters out")
    yield from bps.mov(shctl1, 0)
    yield from bps.mov(ecal_x, 30)
    yield from bps.mov(ecal_y, 0)
    yield from bps.mov(fb.flt1, 0)
    yield from bps.mov(fb.flt2, 0)
    yield from bps.mov(fb.flt3, 0)
    yield from bps.mov(fb.flt4, 0)


# dictionary of references
D_SPACINGS = {'LaB6': np.array([4.15772, 2.94676, 2.40116]),
              'Si': 5.43095 / np.array([np.sqrt(3), np.sqrt(8), np.sqrt(11), np.sqrt(27)]),
             }

# Helper functions
def peakfunc(x, amplitude, sigma, x0, slope, intercept):
    # amplitude is *not* amplitude!!! needs to be rescaled by sigma!!!!
    amplitude = amplitude*sigma*np.sqrt(2*np.pi)
    result = voigt(x=x, amplitude=amplitude, center=x0, sigma=sigma)
    result += slope*x + intercept
    return result

def guess(xdata, ydata, sigma=None):
    '''
        sigma is often hard to guess, allow it to be externally guessed
    '''
    g_average = np.average(ydata)

    # choose between a peak or dip
    dip_amp = np.min(ydata) - g_average
    peak_amp = np.max(ydata) - g_average
    if np.abs(dip_amp) > peak_amp:
        print("found a dip")
        g_amp = dip_amp
    else:
        print("found a peak")
        g_amp = peak_amp

    if sigma is None:
        # guess fwhm
        w, = np.where(np.abs(ydata-g_average) < np.abs(g_amp/2.))
        g_fwhm = np.abs(xdata[w[-1]] - xdata[w[0]])
        # guess...
        g_sigma = g_fwhm/2.
    else:
        g_sigma = sigma

    x0 = xdata[np.argmax(np.abs(ydata-g_average))]


    init_guess = {
                  'amplitude': Parameter('amplitude', value=g_amp, vary=True),
                  'sigma': Parameter('sigma', min=0, value=g_sigma, vary=True),
                  'x0' : Parameter('x0', value=x0, vary=True),
                  'intercept': Parameter('intercept', value=g_average,vary=True),
                  'slope': Parameter('slope', value=0, vary=True),
                 }
    params = Parameters(init_guess)
    return params


def ispeak(x, y, sdev=2):
    '''
        Decision making logic for if we have a peak or dip.
        sdev : number of std dev's the peak must be above noise
            sdev 2 seems to be okay...
    '''
    noise = np.std(y)
    avg = np.average(y)
    peak = np.max(np.abs(y - avg))
    return peak > sdev*noise


def guess_and_fit(xdata, ydata, sigma=None):
    '''
        Guess fit and return results.
    '''
    peakmodel = Model(peakfunc, independent_vars=['x'])
    init_guess = guess(xdata, ydata, sigma=sigma)
    return peakmodel.fit(data=ydata, x=xdata, params=init_guess)

def guess_theta_from_reference(wguess, D="Si"):
    '''
        Guess the theta value from the reference.

        Parameters
        ----------
        wguess : float
            the wavelength guess
        D : str
            the reference to use
    '''
    # the sample to use (use from the string supplied)
    D = D_SPACINGS[D]

    cen_guesses = np.degrees(np.arcsin(wguess/ (2 * D)))
    return cen_guesses


def wavelength_from_theta(theta, d):
    '''
        Get the wavelength from theta
        theta : the angle (theta)
            for twotheta divide by two before supplying here
        d : the d spacing
    '''
    return 2*d*np.sin(np.radians(theta))

# New calibration scan plan
def Ecal(wguess, detectors=None, motor=None, coarse_step=.0012, coarse_nsteps=120, D='Si', detector_name='sc_chan1',
              theta_offset=-35.26, nsigma_fine=.1, nsigma_range=5,
              output_file="result.csv", motor_type='th'):
    '''
        This is the new Ecal scan for dips.
            We should treat peaks separately to simplify matters (leaves for
            easier tweaking)


        This algorithm will search for a peak within a certain theta range
            The theta range is determined from the wavelength guess

        Parameters
        ----------
        wguess : the guessed wavelength
        detectors : list, optional
            list of detectors. Defaults to [sc] detector
        motor : motor, optional
            the motor to scan on (th_cal). Defaults to th_cal
        coarse_step : float, optional
            the max_step to scan on. This is the step size we use for
            the coarse initial scan
        coarse_nsteps : int, optional
            the number of steps to take for coarse scan
        D : string, optional
            the reference sample to use for the calculation of the d spacings
            Defaults to "Si"
        detector_name : str, optional
            the name of the detector
        
        theta_offset : float, optional
            the offset of theta zero estimated from the sample
        nsigma_fine : float, optional
            the fraction of sigma per point for the fine scan
            (the sigma used is the fitted sigma)
        nsigma_range: int, optional
            the range to scan for fine scan:
            +/- nsigma_range*fitted_sigma
            where fitted_sigma is the sigma obtained from the fit from
            the coarse scan
        motor_type : str, optional
            the type of motor used, ether "th" (theta) or "tth"(two-theta)
    '''
    if detectors is None:
        detectors = [sc]
    if motor is None:
        motor = th_cal

    # an object for passing messages
    global myresult
    factors = dict(th=1, tth=2)
    factor = factors[motor_type]

    # first guess the theta positions
    # TODO : do for two theta
    cen_guesses = guess_theta_from_reference(wguess, D=D)
    # now find the symmetric peaks
    left_guesses, right_guesses = (theta_offset-cen_guesses,
                                   theta_offset+cen_guesses)

    # just take first peak + symmetric for now
    peak_guesses = right_guesses[0], left_guesses[0]

    print("Trying {} +/- {} = {} and {}".format(theta_offset, cen_guesses[0],
                                                peak_guesses[0],
                                                peak_guesses[1]))


    # set up the live Plotting
    fig = plt.figure(detector_name)
    fig.clf();
    ax = plt.gca();

    #detector_name = detectors[0].name

    # set up a live plotter
    lp = LivePlot(detector_name, x=motor.name, marker='o', ax=ax)

    xdata_total = list()
    ydata_total = list()
    results_list = list()
    cnt = 0
    # TODO : this should be a plan on its own
    for theta_guess in peak_guesses:
        cnt += 1
        # scan the first peak
        # the number of points for each side
        npoints = coarse_nsteps
        start, stop = theta_guess - coarse_step*npoints, theta_guess + coarse_step*npoints
        # reverse to go negative
        start, stop = stop, start
        print("Trying to a guess. Moving {} from {} to {} in {} steps".format(motor.name, start, stop, npoints))
        yield from bpp.subs_wrapper(bp.scan(detectors, motor, start, stop, npoints), lp)
        # TODO : check if a peak was found here
        # (can use ispeak(... , sdev=2)
        # find the position c1 in terms of theta

        xdata = lp.x_data
        ydata = lp.y_data

        peakmodel = Model(peakfunc, independent_vars=['x'])
        init_guess = guess(xdata, ydata, sigma=coarse_step/10.)
        res = peakmodel.fit(data=ydata, x=xdata, params=init_guess)
        fitted_sigma = res.best_values['sigma']

        print("guess: {}".format(init_guess))

        plt.figure('fitting coarse {}'.format(cnt));plt.clf()
        plt.plot(lp.x_data, lp.y_data, linewidth=0, marker='o', color='b', label="data")
        plt.plot(lp.x_data, res.best_fit, color='r', label="fit")
        plt.plot(init_guess['x0'].value, init_guess['amplitude'].value +
                 init_guess['intercept'].value, 'ro')

        # best guess of center position
        new_theta_guess = res.best_values['x0']
        print("Found center at {}, running finer scan".format(new_theta_guess))
        start, stop = new_theta_guess - fitted_sigma*nsigma_range, new_theta_guess + fitted_sigma*nsigma_range
        # force number of steps to yield a step size of approx sigma_fine
        npoints = int(np.abs(stop-start)/fitted_sigma)
        # reverse to go negative
        start, stop = stop, start
        print("Trying to a guess. Moving {} from {} to {} in {} steps".format(motor.name, start, stop, npoints))
        yield from bpp.subs_wrapper(bp.scan(detectors, motor, start, stop, npoints), lp)

        xdata = lp.x_data
        ydata = lp.y_data

        peakmodel = Model(peakfunc, independent_vars=['x'])
        init_guess = guess(xdata, ydata, sigma=coarse_step/10.)
        res = peakmodel.fit(data=ydata, x=xdata, params=init_guess)

        plt.figure('fitting fine {}'.format(cnt));plt.clf()
        plt.plot(lp.x_data, lp.y_data, linewidth=0, marker='o', color='b', label="data")
        plt.plot(lp.x_data, res.best_fit, color='r', label="fit")
        plt.plot(init_guess['x0'].value, init_guess['amplitude'].value +
                 init_guess['intercept'].value, 'ro')

        results_list.append(res)

    # now convert peak to cen 
    # just use first peak for now
    # left right doesnt mean anything by the symmetric peak pairs
    peak_left_cen = results_list[0].best_values['x0']
    peak_right_cen = results_list[1].best_values['x0']

    new_theta_offset = (peak_left_cen+peak_right_cen)*.5
    average_peak_theta = (np.abs(peak_left_cen-new_theta_offset) +
                          np.abs(peak_right_cen-new_theta_offset))*.5
    print("new theta offset : {} deg".format(new_theta_offset))
    print("average peak theta: {} deg".format(average_peak_theta))

    # use first d spacing
    # if th, factor =1 , if tth factor=2 since th = tth/2
    fitted_wavelength = wavelength_from_theta(average_peak_theta/factor,
                                              D_SPACINGS[D][0])
    print("Fitted wavelength is {} angs".format(fitted_wavelength))
    print("Are you happy with results? (y/n)")
    prompt_result = yield from bps.input_plan(">")
    if prompt_result.lower() == "y":
        print("ok, not finalizing. Please run this again")
    else:
        print("Great. Finalizing the Ecal...")
        #yield from finalize_ecal()

    # in case we want access to the results list
    myresult.results_list = results_list
    myresult.wavelength = fitted_wavelength


class MyResult:
    pass

myresult = MyResult()
