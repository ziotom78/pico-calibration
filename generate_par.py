#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
from string import Template
from itertools import product
from collections import namedtuple
import json
import healpy

CUR_PATH = os.path.abspath(os.path.dirname(__file__))

class AtTemplate(Template):
    delimiter = '@'


INDEX_FILE_TEMPLATE = AtTemplate("""#!/bin/sh
#SBATCH -q debug
#SBATCH -N 1
#SBATCH -t 9:00
#SBATCH --account=mp107

mydir=$(mktemp -d "./$(basename $0).XXXXXXXXXXXX")
myfile=$mydir/index.par

cat > $myfile <<EOF
[input_files]
path = @{outdir}/out_000
mask = tod_fake_@{detector}_science_?????.fits
hdu = 1
column = TIME

[periods]
length = @{baseline_length_s}

[output_file]
file_name = @{index_file}
EOF

index.py $myfile && rm -rf $mydir
""")

CALIBRATE_FILE_TEMPLATE = AtTemplate("""#!/bin/sh
#SBATCH -q debug
#SBATCH -N @{nodes}
#SBATCH -t 0:29:59
#SBATCH --account=mp107

mydir=$(mktemp -d "./$(basename $0).XXXXXXXXXXXX")
myfile=$mydir/index.par

cat > $myfile <<EOF
[input_files]
index_file = @{index_file}
signal_hdu = 1
signal_column = TOTALTOD
pointing_hdu = 1
pointing_columns = THETA, PHI
angle_column = PSI

[dacapo]
t_cmb_k = 2.72548
solsysdir_ecl_colat_rad = 1.7656051330336222
solsysdir_ecl_long_rad = 2.9958842149922833
solsysspeed_m_s = 370082.2332
frequency_hz = 140e9
nside = 256
mask = @{galactic_mask}
periods_per_cal_constant = @{periods_per_cal_constant}
cg_stop_value = 1e-8
cg_max_iterations = 100
dacapo_stop_value = 1e-8
dacapo_max_iterations = 100
pcond = jacobi

[output]
file_name = @{gain_file}
save_map = yes
save_convergence_information = yes
comment = "@{baseline_length_s} s baseline for 1/f, @{cal_duration_min} min for calibration, fsky=1.00"
EOF

srun -n $((@{nodes} * 16)) calibrate.py $myfile && rm -rf mydir
""")


OVERALL_FILE_TEMPLATE = AtTemplate("""#!/bin/sh
#SBATCH -q regular
#SBATCH -N 80
#SBATCH -t 5:00:00
#SBATCH --account=mp107

""")


def formattime(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds - (h * 3600 + m * 60)
    return '{0}:{1:02d}:{2:02d}'.format(h, m, s)


NoiseParameters = namedtuple('NoiseParameters', [
    'white_noise',
    'fknee_mHz',
])

ScanningParameters = namedtuple('ScanningParameters', [
    'spin_angle_deg',
    'prec_angle_deg',
    'spin_rate_rpm',
    'prec_rate_rpm',
])

WHITE_NOISE = 33.8e-6
NOISE_PARAMS = [
    NoiseParameters(white_noise=1e-15, fknee_mHz=0),
    NoiseParameters(white_noise=WHITE_NOISE, fknee_mHz=10),
]

SCANNING_PARAMS = [
    ScanningParameters(spin_angle_deg=69, prec_angle_deg=26, spin_rate_rpm=1, prec_rate_rpm=1.0 / (10.0 * 60.0)), # PICO
]

MASKS = [
    '',
    '/global/u2/t/tomasi/work/masks/dust_mask_090_ecliptic.fits.gz',
    '/global/u2/t/tomasi/work/masks/dust_mask_095_ecliptic.fits.gz',
]

OUTPUT_PATH = './slurm'  # Where to write the SLURM files
DETECTOR_VALUES = ['0A', '0B']
SAMPLE_RATE_HZ = 100.0

with open('job1_uncalibrated.template', 'rt') as f:
    job1_template = AtTemplate(''.join(f.readlines()))

with open('job2_calibrated.template', 'rt') as f:
    job2_template = AtTemplate(''.join(f.readlines()))

try:
    os.mkdir(OUTPUT_PATH)
except:
    pass

casenum = 0
cases = {}
for noise, scanning in product(NOISE_PARAMS, SCANNING_PARAMS):

    subjobs = []

    if noise.fknee_mHz > 0:
        baseline_length_s = 1.0 / (noise.fknee_mHz * 1e-3) / 2.0
    else:
        baseline_length_s = 60.0  # Arbitrary value, as there is no 1/f

    prec_period_min = 1.0 / scanning.prec_rate_rpm
    estimated_seconds = 10 * 60

    estimated_nodes = 40
    d = {
        'code_path': CUR_PATH,
        'prec_angle_deg': scanning.prec_angle_deg,
        'spin_angle_deg': scanning.spin_angle_deg,
        'psd_NET': noise.white_noise,
        'psd_NET_mK': 1e6 * noise.white_noise,
        'fknee_Hz': 1e-3 * noise.fknee_mHz,
        'fknee_mHz': noise.fknee_mHz,
        'spin_period_min': 1.0 / scanning.spin_rate_rpm,
        'prec_period_min': prec_period_min,
        'prec_period_min_int': int(prec_period_min),
        'baseline_length_s': baseline_length_s,
        'sample_rate': SAMPLE_RATE_HZ,
        'nodes': estimated_nodes,
        'walltime': formattime(estimated_seconds),
        'case': casenum,
    }

    basename = ('{case:03d}_spin{spin_angle_deg:02d}deg_wn{psd_NET_mK:.1f}_fk{fknee_mHz:03d}').format(**d)
    d['outdir'] = os.path.join(
        '/scratch1/scratchdirs/tomasi/pico/out', basename)

    uncalibrated_job = os.path.join(OUTPUT_PATH, basename + '_1_uncalibrated.slurm')
    with open(uncalibrated_job, 'wt') as outf:
        outf.write(job1_template.substitute(d))
    subjobs.append(uncalibrated_job)

    cases[casenum] = dict(d)

    if prec_period_min > 60 * 24 * 10:
        # If the precession period is larger than 10 days, let's use a more reasonable baseline for calibration
        cal_duration_base = 60
    else:
        cal_duration_base = prec_period_min

    for mask_file_name in MASKS:
        if mask_file_name != '':
            cur_mask = healpy.read_map(mask_file_name, verbose=False)
            # Round the percentage so that it is a multiple of 5
            mask_percentage = round((len(cur_mask[cur_mask > 0]) * 20) / len(cur_mask)) * 5
        else:
            mask_percentage = 100

        d['galactic_mask'] = mask_file_name
        d['mask_percentage'] = mask_percentage

        for cal_duration_min in (cal_duration_base, 4 * cal_duration_base):
            cal_duration_str = '{0:02d}'.format(int(cal_duration_min))
            gain2toast_input = []
            for det in DETECTOR_VALUES:
                d['detector'] = det
                d['index_file'] = os.path.join(
                    d['outdir'], '{case:03d}_{detector}_index.fits'.format(**d))
                ind_fname = os.path.join(
                    OUTPUT_PATH, '{0:03d}_index_{1}_{2:03d}s.slurm'.format(casenum, det, int(baseline_length_s)))
                with open(ind_fname, 'wt') as outf:
                    outf.write(INDEX_FILE_TEMPLATE.substitute(d))

                if not ind_fname in subjobs:
                    subjobs.append(ind_fname)

                periods_per_cal_constant = int(
                    cal_duration_min * 60.0 / baseline_length_s)

                if cal_duration_min > cal_duration_base:
                    d['nodes'] = 13
                else:
                    d['nodes'] = 50
                d['cal_duration_min'] = cal_duration_min
                d['cal_duration_min_int'] = int(cal_duration_min)
                d['periods_per_cal_constant'] = periods_per_cal_constant
                d['gain_file'] = os.path.join(
                    d['outdir'], '{case:03d}_gains_{detector}_mask{mask_percentage:03d}_{cal_duration_min_int:03d}min.fits'.format(**d))

                cal_fname = os.path.join(
                    OUTPUT_PATH, '{0:03d}_calibrate_{1}_mask{2:03d}_{3:03d}min.slurm'.format(casenum, det, mask_percentage, d['cal_duration_min_int']))
                with open(cal_fname, 'wt') as outf:
                    outf.write(CALIBRATE_FILE_TEMPLATE.substitute(d))
                subjobs.append(cal_fname)

                gain2toast_input += [d['gain_file'], 'fake_' + det]

            d['nodes'] = estimated_nodes
            d['gain2toast_input'] = ' '.join(gain2toast_input)
            d['gain2toast_output'] = os.path.join(d['outdir'],
                    '{case:03d}_gains_mask{mask_percentage:03d}_{cal_duration_min_int:03d}min.fits'.format(**d))
            d['outdir_cal'] = os.path.join(
                    '/scratch1/scratchdirs/tomasi/pico/out/calibrated_{0}min/mask{1:03d}'.format(cal_duration_str, mask_percentage),
                    basename)

            calibrated_job_name = os.path.join(OUTPUT_PATH, basename + '_2_calibrated_mask{0:03d}_{1}min.slurm'.format(mask_percentage, cal_duration_str))
            with open(calibrated_job_name, 'wt') as outf:
                outf.write(job2_template.substitute(d))

            subjobs.append(calibrated_job_name)

    overall_job_name = '{casenum:03d}_overall_job.slurm'.format(casenum=casenum)
    with open(os.path.join(OUTPUT_PATH, overall_job_name), 'wt') as outf:
        outf.write(OVERALL_FILE_TEMPLATE.substitute(d))
        for cur_subjob in subjobs:
            outf.write('''echo "[$(date --iso-8601=seconds)] Running job {0}"
/bin/bash "{0}"
echo "[$(date --iso-8601=seconds)] Job {0} has completed"

'''.format(os.path.abspath(cur_subjob)))

    print(
        'Parameter files for case "{0}" written to disk'.format(basename))

    casenum += 1

with open("cases.json", "wt") as outf:
    json.dump(cases, outf, indent=4)
