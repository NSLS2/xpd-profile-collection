import itertools
import bluesky.plan_stubs as bps


p1 = [
    (52.0, 340, 450, 0),
    (30.261290301043037, 340, 1800, 1),
    (21.55862058950062, 340, 3600, 0),
    (34.90538217067181, 340, 3600, 1),
    (53.129448763065085, 400, 450, 0),
    (58.22228250584029, 400, 450, 0),
    (68.0, 400, 450, 0),
    (18.254961976699835, 400, 450, 1),
    (21.38408748042952, 400, 450, 1),
    (29.224267821396577, 400, 1800, 0),
    (47.03789369783586, 400, 1800, 1),
    (23.670099461400827, 400, 3600, 0),
    (27.226756188799893, 400, 3600, 0),
    (37.66943776422152, 400, 3600, 0),
    (75.66772298711686, 400, 3600, 0),
    (60.560307846728435, 400, 3600, 1),
    (53.333335443399534, 460, 450, 0),
    (69.88942987567354, 460, 900, 0),
    (25.584623161859657, 460, 900, 1),
    (68.12786631318222, 460, 900, 1),
    (60.22211498893399, 460, 1800, 0),
    (64.33324514861206, 460, 1800, 0),
    (38.00338218519404, 460, 1800, 1),
    (53.55812508192558, 460, 1800, 1),
    (54.38220016905454, 460, 1800, 1),
    (62.44657141973025, 460, 1800, 1),
    (71.44570726115217, 460, 1800, 1),
]
p2 = [
    (30.3330444540047, 340, 450, 0),
    (37.86313998007816, 340, 450, 0),
    (21.000944424554643, 340, 1800, 0),
    (26.334238071691267, 340, 1800, 0),
    (59.0, 340, 1800, 0),
    (20.957393918772528, 400, 450, 0),
    (29.666859304198187, 400, 450, 0),
    (33.77798763543133, 400, 450, 0),
    (23.277686739822617, 400, 450, 1),
    (37.41046864218521, 400, 450, 1),
    (67.47193872294505, 400, 450, 1),
    (68.0, 400, 450, 1),
    (79.66537195987766, 400, 1800, 0),
    (36.41102957015972, 400, 3600, 0),
    (25.009354003572785, 400, 3600, 1),
    (51.67181496230776, 400, 3600, 1),
    (63.48076903832869, 400, 3600, 1),
    (77.22381732216856, 400, 3600, 1),
    (68.33652122796366, 460, 450, 1),
    (17.44790372676635, 460, 900, 0),
    (42.667811134614496, 460, 900, 0),
    (45.33444811727734, 460, 900, 0),
    (61.396603131287165, 460, 900, 0),
    (66.35036565231812, 460, 900, 1),
    (68.69125798919492, 460, 900, 1),
    (15.991730700696655, 460, 1800, 0),
    (22.77775023506028, 460, 1800, 0),
]


def batch_scan(
    dets,
    sample_points,
    *,
    ti_range=5.0,
    points=10,
    rocking_range=0.5,
    rocking_num=3,
    real_motors,
    exposure=20,
    take_data=None,
    transform_pair
):
    if take_data is None:
        take_data = stepping_ct

    # unpack the real motors
    x_motor, y_motor = real_motors
    # make the soft pseudo axis
    ctrl = Control(name="ctrl")
    pseudo_axes = tuple(getattr(ctrl, k) for k in ctrl.component_names)
    _md = {
        "batch_id": str(uuid.uuid4()),
        "batch_scan": {
            "rocking_range": rocking_range,
            "take_data": take_data.__name__,
            "rocking_num": rocking_num,
            "points": points,
            "ti_range": ti_range,
        },
        'sample_points': sample_points
    }

    for p in sample_points:
        ti, *strip = p
        for j, ti_m in enumerate(np.linspace(ti-(ti_range/2), ti+(ti_range/2), points)):
            try:
                real_target = transform_pair.forward(ti_m, *strip)
                print(f"real target: {real_target}")
            except ValueError as ve:
                print("ValueError!")
                continue

            # move to the new position
            t0 = time.time()
            yield from bps.mov(*itertools.chain(*zip(real_motors, real_target)))
            t1 = time.time()
            print(f"move to target took {t1-t0:0.2f}s")

            # read back where the motors really are
            real_x = yield from _read_the_first_key(x_motor)
            real_y = yield from _read_the_first_key(y_motor)
            print(f"real x and y: {real_x}, {real_y}")
            if real_x is None:
                real_x, real_y = real_target
            # compute the new (actual) pseudo positions
            pseudo_target = transform_pair.inverse(real_x, real_y)
            print(f"pseudo target: {pseudo_target}")
            # and set our local synthetic object to them
            yield from bps.mv(*itertools.chain(*zip(pseudo_axes, pseudo_target)))

            uid = yield from take_data(
                dets + list(real_motors) + [ctrl],
                exposure,
                y_motor,
                real_y - rocking_range,
                real_y + rocking_range,
                md={
                    **_md,
                    "center_point": p,
                    "inner_count": j,
                },
                num=rocking_num
            )
