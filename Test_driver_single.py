# -*- coding: utf-8 -*-
"""
Created on Mon Mar  7 17:07:32 2022

@author: Jorge

"""
#########################################################################
from SLP_LP_scheduling import scheduling
from Methods.smartCharging_driver import smartCharging_driver
import os
import pathlib
import time
import shutil
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 20})

# get file path
script_path = os.path.dirname(os.path.abspath(__file__))

# init parameters
initParams = dict()
initParams["plot"] = "True"  # plotting flag
initParams["vmin"] = "0.95"  # voltage limits
initParams["vmax"] = "1.05"
initParams["freq"] = "30min"  # "15min", "30min" (For EV charging), "H"
initParams["dispatchType"] = "SLP"  # "LP"
initParams["script_path"] = str(script_path)  # "LP"
initParams["case"] = "123bus"  # 13bus
initParams["dssFile"] = "IEEE123Master.dss"  # 'IEEE13Nodeckt.dss'


# EV parameters
metric = np.inf# 1,2,np.inf
ext = '.pdf'
h = 6 
w = 4 

# output directory
# time stamp
t = time.localtime()
timestamp = time.strftime('%b-%d-%Y_%H%M', t)
# create directory to store results
today = time.strftime('%b-%d-%Y', t)
directory = "Results_Vis_" + today
output_dir12 = pathlib.Path(script_path).joinpath("outputs", directory)

if not os.path.isdir(output_dir12):
    os.mkdir(output_dir12)
# else:
#     shutil.rmtree(output_dir12)
#     os.mkdir(output_dir12)

# other parameters
initParams["reg"] = "False"
initParams["loadMult"] = 10
initParams["batSize"] = 0
initParams["pvSize"] = 0
outDir = f"reg_{initParams['reg']}_bat_{initParams['batSize']}_pv_{initParams['pvSize']}_lm_{initParams['loadMult']}"
# define output dir
output_dir1 = pathlib.Path(output_dir12).joinpath(outDir)
if not os.path.isdir(output_dir1):
    os.mkdir(output_dir1)
initParams["output_dir"] = str(output_dir1)

####################################
# compute scheduling
####################################
initDispatchLMP_path = pathlib.Path(output_dir1).joinpath("initDispatchLMP.pkl")
initDispatchDemand_path = pathlib.Path(output_dir1).joinpath("initDispatchDemand.pkl")
if not os.path.isfile(initDispatchLMP_path):
    outES, initDSS, k = scheduling(initParams)

    LMP = outES['LMP']
    LMP.to_pickle(initDispatchLMP_path)
    demandProfile = initDSS["dfDemand"]
    demandProfile.to_pickle(initDispatchDemand_path)
else:
    LMP = pd.read_pickle(initDispatchLMP_path)
    demandProfile = pd.read_pickle(initDispatchDemand_path)

####################################
# Define Smart Charging parameters
####################################
# Set random seed so results are repeatable
np.random.seed(2022)
# define init energy
LMP_size = np.size(LMP, 0)
initEnergy_list = [np.random.uniform(40, 50) for i in range(LMP_size)]
# define ev capacity
evCapacity_list = [np.random.uniform(80.5, 110) for i in range(LMP_size)]
# define arrival time
arrivalTime_list = [f"{np.random.randint(15, 23)}:{np.random.randint(0,2)*3}0" for i in range(LMP_size)]
# define departure time
departureTime_list = [f"{np.random.randint(6, 12)}:{np.random.randint(0,2)*3}0" for i in range(LMP_size)]
initW = np.array([[.7, .1, .1, .1], [.1, .7, .1, .1], [.1, .1, .7, .1], [.1, .1, .1, .7]])
initW_list = [initW[np.random.choice(len(initW),
                                     size=1)] for i in range(LMP_size)]
# LMP index random
# LMP_index = np.random.choice(LMP_size, LMP_size, replace=False)
LMP_index = LMP.sample(frac=1, random_state=np.random.RandomState(2022)).index 

# create smart charging driver object
char_obj = smartCharging_driver(ext, arrivalTime_list, departureTime_list, initEnergy_list, evCapacity_list, initW_list)

# define folder to store smartcharging results
output_dir = pathlib.Path(output_dir1).joinpath("SmartCharging")
if not os.path.isdir(output_dir):
    os.mkdir(output_dir)
# compute EV corrected demand
newDemand = char_obj.charging_driver(output_dir, 0, demandProfile, LMP, LMP_index, initW)
