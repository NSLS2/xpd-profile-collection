We need to generate `integration` files and tiff files (`dark_sub`)

What we have now via Kafka:

```bash
2024-05-28/20:20:49 mrakitin@xf28id2-ws3:XPD (RHEL8.9) /nsls2/data/xpd-new/proposals/commissioning/pass-315985/ldrd/unnamed_sample $ tree
.
├── fq
│   └── unnamed_sample_20240528-202016_2f28e7_0001.fq
├── mask
├── meta
│   └── unnamed_sample_20240528-202016_2f28e7.yaml
├── pdf
│   └── unnamed_sample_20240528-202016_2f28e7_0001.gr
└── sq
    └── unnamed_sample_20240528-202016_2f28e7_0001.sq
```


Good example (from ZMQ):

```bash
2024-05-28/20:24:59 mrakitin@xf28id2-ws3:XPD (RHEL8.9) /nsls2/data/xpd-new/proposals/commissioning/pass-315985/tmp/unnamed_sample $ tree .
.
├── dark_sub
│   ├── unnamed_sample_20240517-184225_2f003e_primary-dk_sub_image-00000.tiff
│   └── unnamed_sample_20240528-191335_29af22_primary-dk_sub_image-00000.tiff
├── fq
│   ├── unnamed_sample_20240528-183014_ca6f1a_0001.fq
│   ├── unnamed_sample_20240528-185345_79aec5_0001.fq
│   ├── unnamed_sample_20240528-185612_15c0fd_0001.fq
│   ├── unnamed_sample_20240528-190023_c55fbd_0001.fq
│   ├── unnamed_sample_20240528-191335_29af22_0001.fq
│   └── unnamed_sample_20240528-201210_786aad_0001.fq
├── integration
│   ├── unnamed_sample_20240528-191335_29af22_primary-1_mean_q.chi
│   └── unnamed_sample_20240528-191335_29af22_primary-1_mean_tth.chi
├── mask
│   ├── unnamed_sample_20240517-184225_2f003e_primary-mask-1.npy
│   └── unnamed_sample_20240528-191335_29af22_primary-mask-1.npy
├── meta
│   ├── unnamed_sample_20240517-184225_2f003e.yaml
│   ├── unnamed_sample_20240528-191335_29af22.yaml
│   └── unnamed_sample_20240528-201210_786aad.yaml
├── pdf
│   ├── unnamed_sample_20240528-183014_ca6f1a_0001.gr
│   ├── unnamed_sample_20240528-185345_79aec5_0001.gr
│   ├── unnamed_sample_20240528-185612_15c0fd_0001.gr
│   ├── unnamed_sample_20240528-190023_c55fbd_0001.gr
│   ├── unnamed_sample_20240528-191335_29af22_0001.gr
│   └── unnamed_sample_20240528-201210_786aad_0001.gr
├── scalar_data
│   ├── unnamed_sample_20240517-184225_2f003e_primary.csv
│   └── unnamed_sample_20240528-191335_29af22_primary.csv
└── sq
    ├── unnamed_sample_20240528-183014_ca6f1a_0001.sq
    ├── unnamed_sample_20240528-185345_79aec5_0001.sq
    ├── unnamed_sample_20240528-185612_15c0fd_0001.sq
    ├── unnamed_sample_20240528-190023_c55fbd_0001.sq
    ├── unnamed_sample_20240528-191335_29af22_0001.sq
    └── unnamed_sample_20240528-201210_786aad_0001.sq

8 directories, 29 files
```