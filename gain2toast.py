#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import sys
import numpy as np
from astropy.io import fits

def main(args):
    if len(args) < 4 or len(args) % 2 != 0:
        print("Usage: {0} GAIN_FILE1 DETNAME1 [GAIN_FILE2 DETNAME2...] OUTPUT_FILE"
                .format(os.basename(args[0])))
        sys.exit(1)

    outputfilename = args[-1]
    filedetpairs = args[1:-1]

    hdus = [fits.PrimaryHDU()]
    for curinputfile, curdet in zip(filedetpairs[::2], filedetpairs[1::2]):
        with fits.open(curinputfile) as inpf:
            gains = inpf['GAINS'].data.field('GAIN')
            gainn = inpf['GAINS'].data.field('NSAMPLES')
            ofsn = inpf['OFFSETS'].data.field('NSAMPLES')
            ofsperiod = inpf['PERIODS'].header['LENGTH']

        if ofsperiod == 0.0:
            ofsperiod = 30.0

        ofsstarttime = np.arange(len(ofsn)) * ofsperiod
        gainstarttime = np.empty(len(gains), dtype='float')
        samplesincurgain = 0
        gainidx = 0
        for ofsidx in range(len(ofsn)):
            if samplesincurgain == 0:
                gainstarttime[gainidx] = ofsstarttime[ofsidx]

            samplesincurgain += ofsn[ofsidx]

            if samplesincurgain == gainn[gainidx]:
                samplesincurgain = 0
                gainidx += 1

        cur_hdu = fits.BinTableHDU.from_columns([
            fits.Column(name='TIME', array=gainstarttime, unit='s', format='1D'),
            fits.Column(name='GAIN', array=gains, unit='', format='1D'),
            ])
        cur_hdu.header['EXTNAME'] = curdet

        hdus.append(cur_hdu)

    fits.HDUList(hdus).writeto(outputfilename, overwrite=True)

    print('File {0} written'.format(outputfilename))

if __name__ == '__main__':
    main(sys.argv)
