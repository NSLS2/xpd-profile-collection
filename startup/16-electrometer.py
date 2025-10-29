from nslsii.ad33 import QuadEMV33


class XPDQuadEM(QuadEMV33):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs.update([(self.acquire_mode, "Single")])  # single mode
        self.configuration_attrs = [
            "integration_time",
            "averaging_time",
            "em_range",
            "num_averaged",
            "values_per_read",
        ]

    def set_primary(self, n, value=None):
        name_list = []
        if "All" in n:
            for k in self.read_attrs:
                getattr(self, k).kind = "normal"
            return

        for channel in n:
            cur = getattr(self, f"current{channel}")
            cur.kind |= Kind.normal
            cur.mean_value = Kind.hinted


qem1 = XPDQuadEM("XF:28IDC-BI{IM:02}EM180:", name="qem1")
for det in [qem1]:
    det.read_attrs = ['current2', 'current2.mean_value','current3', 'current3.mean_value']
