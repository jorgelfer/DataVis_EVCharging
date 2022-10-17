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
ext = '.png'
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
else:
    shutil.rmtree(output_dir12)
    os.mkdir(output_dir12)

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
initEnergy_list = [np.random.uniform(18, 40) for i in range(LMP_size)]
# define ev capacity
evCapacity_list = [np.random.uniform(80.5, 118) for i in range(LMP_size)]
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
####################################
# compute the decentralized smart charging
####################################
evh = [-1]
evh_size = len(evh)
# number of EV loop
for ev in range(evh_size):
    # initialize store variables as lists
    OpCost_list = list()
    mOpCost_list = list()
    LMP_list = list()
    demand_list = list()

    # initial append
    LMP_list.append(LMP)
    demand_list.append(demandProfile)

    # create a folder to store LMP per EV
    output_dirEV = pathlib.Path(output_dir).joinpath(f"EV_{ev}")
    if not os.path.isdir(output_dirEV):
        os.mkdir(output_dirEV)
        
    # per node LMP comparison
    dLMP_list = list()

    # prelocate demand difference variable
    diffDemand = np.zeros(demandProfile.shape)

    # define number of max iterations
    maxIter = 30
    sum_dLMP = 100
    sum_dLMP_list = list()
    tol = 70
    it = 0
    # iterations loop
    while sum_dLMP > tol and it < maxIter:
        # novelty criterion
        if it == 0:
            mean_LMP = LMP_list[-1]
        else:
            aux2 = [(dLMP / sum(dLMP_list)) for dLMP in  dLMP_list]
            aux1 = [np.expand_dims((dLMP / sum(dLMP_list)), axis=1) * LMPi.values  for dLMP, LMPi in zip(dLMP_list, LMP_list[1:])]
            mean_LMP = pd.DataFrame(sum(aux1), index=LMP.index, columns=LMP.columns)

        # compute EV corrected demand
        plot = True
        newDemand = char_obj.charging_driver(output_dirEV, it, demandProfile, mean_LMP, LMP_index[:evh[ev]], plot)
        demand_list.append(newDemand)
        
        # compute scheduling with new demand
        outES_EV, initDSS_EV, k_EV = scheduling(initParams, newDemand)
        OperationCost_EVC = outES_EV['J']
        LMP_EVC = outES_EV['LMP']
        # store corrected values
        OpCost_list.append(OperationCost_EVC)
        LMP_list.append(LMP_EVC)

        # store node-base LMP difference
        dLMP_list.append(np.linalg.norm(LMP_list[it + 1].values - LMP_list[it].values, ord=metric, axis=1))
        sum_dLMP = np.linalg.norm(LMP_list[it + 1].values - LMP_list[it].values, ord=metric)
        sum_dLMP_list.append(sum_dLMP)

        # keep track
        print(f"EV:{ev}_it:{it}_diff={sum_dLMP}_cost:{np.round(OpCost_list[-1], 2)}")

        # Store demand difference
        # diffDemand = newDemand - prevDemand
        diffDemand = demand_list[it + 1].values - demand_list[it].values

        if plot:
            diffDemand_pd = pd.DataFrame(diffDemand)
            fig, ax = plt.subplots(figsize=(h, w))
            sns.heatmap(diffDemand, annot=False)
            fig.tight_layout()

            output_dirDemand = pathlib.Path(output_dirEV).joinpath("Demand")
            if not os.path.isdir(output_dirDemand):
                os.mkdir(output_dirDemand)

            output_img = pathlib.Path(output_dirDemand).joinpath(f"Demand_diff_it_{it}" + ext)
            plt.savefig(output_img)
            plt.close('all')

            output_pkl = pathlib.Path(output_dirDemand).joinpath(f"Demand_diff_it_{it}.pkl")
            diffDemand_pd.to_pickle(output_pkl)
        
        if it != 0:
            if mOpCost_list[it] > 1.1 * mOpCost_list[it - 1]:
                break
        it += 1
