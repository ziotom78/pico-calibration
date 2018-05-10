#!/bin/sh
#SBATCH -q debug
#SBATCH -t 29:59

index.py ini/index_2years_0A.ini
index.py ini/index_2years_0B.ini
