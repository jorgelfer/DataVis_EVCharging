from Methods.SmartCharging import SmartCharging 
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import pathlib
import csv


class smartCharging_driver:

    def __init__(self, ext, arrivalTime_list, departureTime_list, initEnergy_list, evCapacity_list, initW_list):
        # constructor
        self.arrivalTime_list = arrivalTime_list
        self.departureTime_list = departureTime_list
        self.initEnergy_list = initEnergy_list
        self.evCapacity_list = evCapacity_list
        self.initW_list = initW_list
        self.ext = ext

    def charging_driver(self, output_dir_sc, it, demandProfile, LMP, LMP_index, initW):
        # preprocess
        
        self.it = it
        h = 4
        w = 6
        
        # create smart charging object
        charging_obj = SmartCharging(numberOfHours=24, pointsInTime=LMP.shape[1]) 

        # plot grid signal (one time)
        m = charging_obj.m
        m = self.__order_dates(m, freq="30min")
        plt.clf()
        fig, ax = plt.subplots()
        m.plot()
        ax.set_title('Grid mix')
        plt.ylabel('%')
        plt.xlabel('Time (hrs)')
        fig.tight_layout()
        output_img = pathlib.Path(output_dir_sc).joinpath("PortionRen" + self.ext)
        plt.savefig(output_img)
        plt.close('all')
        
        csv_file = pathlib.Path(output_dir_sc).joinpath("chargingData.csv")
        header = ["key_0", "key_1", "key_2", "key_3", "key_4", "key_5"]
        header = header + m.index.tolist()
        data = ["", "", "", "", "", "m[%]"]
        data = data + np.round(m.values, decimals=3).tolist()

        with open(csv_file, "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerow(data)

        
        for i, ind in enumerate(LMP_index):
            output_dir = pathlib.Path(output_dir_sc).joinpath(f"{ind}")
            if not os.path.isdir(output_dir):
                os.mkdir(output_dir)
            self.output_dir = output_dir
            
            #individual LMP (pi)
            pi_s = LMP.loc[ind,:]
            data = [f"{ind}", "", "", "", "", "dLMP[$/kW]"]
            data = data + np.round(pi_s.values, decimals=3).tolist()
            with open(csv_file, "a", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(data)
            # reorder dates
            pi = self.__reorder_dates(pi_s)
            # transform to array
            pi = np.expand_dims(pi_s.values, axis=1)
            # household demand profile
            PH_s = demandProfile.loc[ind, :] # normal demand
            data = [f"{ind}", "", "", "", "", "PH[kW]"]
            data = data + np.round(PH_s.values, decimals=3).tolist()
            with open(csv_file, "a", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(data)
            # reorder dates
            PH = self.__reorder_dates(PH_s)
            # transform to array
            PH = np.expand_dims(PH.values, axis=1)
                
            # plot Pi
            plt.clf()
            fig, ax = plt.subplots()
            pi_s.plot()
            ax.set_title(f'dLMP at note {ind}')
            plt.ylabel('$/kw')
            plt.xlabel('Time (hrs)')
            fig.tight_layout()
            output_img = pathlib.Path(self.output_dir).joinpath(f"dLMP_node{ind}" + self.ext)
            plt.savefig(output_img)
            plt.close('all')
                
            # user defined parameters (test)
            initW = [np.array([.7, .1, .1, .1]), 
                     np.array([.1, .7, .1, .1]),
                     np.array([.1, .1, .7, .1]),
                     np.array([.1, .1, .1, .7])]
            Times = [("21:00", "08:00"), ("20:00", "07:00"), ("10:00", "21:00"), ("07:00", "18:00")]

            initEnergy = np.round(self.initEnergy_list[i], 1)
            evCapacity = np.round(self.evCapacity_list[i], 1)
            cont = 0

            for cw, w in enumerate(initW):
                for t, time in enumerate(Times):
                    print(f"node:{ind}, w:{cw}, t:{t}")
                    arrTime = time[0]
                    depTime = time[1]
                    # optimal EV charging using the smart charging object
                    PV_star,_,_,_ = charging_obj.QP_charging(pi, PH, w, arrTime, depTime, initEnergy, evCapacity) # user specific values
                    # reorder index from dataSeries:
                    PV_star = self.__order_dates(PV_star, freq="30min")
                    data = [f"{ind}", f"{initEnergy}", f"{evCapacity}", f"W_{cw}", f"T_{t}", "PEV[kW]"]
                    data = data + np.round(PV_star.values, decimals=3).tolist()
                    with open(csv_file, "a", newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(data)
        
                    # new demand plot
                    plt.clf()
                    fig, ax = plt.subplots()
                    
                    HD = PH_s  #  .to_frame()
                    # HD.index, HD.columns = [range(HD.index.size), range(HD.columns.size)]
                    EVCD = HD.add(PV_star)
                    concat3 = pd.concat([HD, EVCD], axis=1)
                    concat3.plot()
                    ax.set_title(f'Demand in node {ind}')
                    plt.legend(['House', 'House+EV'], prop={'size': 15})
                        
                    fig.tight_layout()
                    output_img = pathlib.Path(self.output_dir).joinpath(f"EVcorrected_demand_w_{cont}"+ self.ext)
                    plt.savefig(output_img)
                    plt.close('all')
                    cont += 1
    
    def __reorder_dates(self, pdSeries):
        """Transforms data into the format that kartik wants it"""
        pdSeries1 = pdSeries[:pdSeries.index.get_loc('08:00')]
        pdSeries2 = pdSeries[pdSeries.index.get_loc('08:00'):]
        pdSeries = pd.concat((pdSeries2, pdSeries1))
        return pdSeries
    
    def __order_dates(self, array, freq="30min"):
        """Transforms data back to normal day"""
        # initialize time pdSeries
        pdSeries = pd.Series(np.zeros(len(array)))
        pdSeries.index = pd.date_range("00:00", "23:59", freq=freq).strftime('%H:%M')
        # reorder init dataSeries to match Kartik's order
        pdSeries = self.__reorder_dates(pdSeries)
        # assign obtained values
        pdframe = pdSeries.to_frame()
        pdframe[0] = array
        pdSeries = pdframe.squeeze()
        # order back to normal 
        pdSeries1 = pdSeries[:pdSeries.index.get_loc('00:00')]
        pdSeries2 = pdSeries[pdSeries.index.get_loc('00:00'):]
        pdSeries = pd.concat((pdSeries2, pdSeries1))
        return pdSeries

