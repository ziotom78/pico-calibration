#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from string import Template

inputdir = '201804_boresight_1pix_2years_nofg'
BASELINE_LENGTH_S = 10.0

with open('2years_template.txt', 'rt') as f:
    template = Template(''.join(f.readlines()))

    for det in ('0A', '0B'):
        for fsky, mask_tag in [(1.00, 'm100'), (0.80, 'm080'), (0.90, 'm090')]:
            for cal_duration_h in (10, 24, 48):
                cal_duration_str = '{0:02d}'.format(cal_duration_h)
                periods_per_cal_constant = int(
                    cal_duration_h * 3600.0 / BASELINE_LENGTH_S)

                fname = 'pico_2years_{cal:02d}h_{mask}_{det}.ini'.format(
                    cal=cal_duration_h, mask=mask_tag, det=det)
                if fsky < 1.0:
                    mask_line = 'mask = /scratch1/scratchdirs/tomasi/masks/dust_mask_{0:03d}_ecliptic.fits.gz'.format(
                        int(fsky * 100.0))
                else:
                    mask_line = ''

                with open(fname, 'wt') as outf:
                    outf.write(
                        template.substitute(
                            inputdir=inputdir,
                            detector=det,
                            fsky=fsky,
                            mask_tag=mask_tag,
                            mask_line=mask_line,
                            cal_duration_str=cal_duration_str,
                            periods_per_cal_constant=periods_per_cal_constant))
                print('File "{0}" written to disk'.format(fname))