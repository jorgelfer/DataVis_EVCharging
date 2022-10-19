import numpy as np
import os
import pathlib
import pandas as pd
from loadHelper import loadHelper
from calendar import monthrange


class georgiaRates:
    def __init__(self, initParams):
        """Define initial paramentes for every rate"""
        # initparams
        self.scriptPath = initParams["output_dir"]
        self.freq = initParams["freq"]
        # peak hours
        self.peakHoursInit = "14:00"
        self.peakHoursFinal = "19:00"
        # peak Days
        self.peakDayInit = "Monday"
        self.peakDayFinal = "Friday"
        # Months
        self.peakMonthInit = "06"
        self.peakMonthFinal = "09"

    def SmartUsage(self):
        """Smart Usage tarif"""
        onPeak = 0.096052 # cents per kwh
        offPeak = 0.010268 # cents per kwh
        demandCharge = 8.21 # dolars for the max kw hourly consumption in a month 

    def PlugInEV(self):
        """PlugInEV tarif"""
        onPeak = 0.203217 # cents per kWh
        offPeak = 0.069728 # cents per kWh
        superOffPeak = 0.014993 # cents per kWh
        demandCharge = 8.21 # dolars for the max kw hourly consumption in a month

    def ResidentialService(self, month):
        """Residential Service tariff"""
        # load residential demand
        dfDemand = self.__load_hourlyDemandPerMonth(month)
        totalDemand = dfDemand.sum(axis=0)
        if (int(month) > 10) or (int(month) < 6):
            # winter d
            EV_demandProfile = np.ones(dfDemand.shape)
            EV_demandProfile = pd.DataFrame(dfDemand, index=dfDemand.index, columns=dfDemand.columns)
            fix0 = 0.058366 # cents per kWh
            fix1 = 0.050062 # cents per kwh
            fix2 = 0.049143 # cents per kwh
        else:
            # summer 
            fix0 = 0.058366 # centes per kWh
            fix1 = 0.096943 # cents per kwh
            fix2 = 0.0100336 # cents per kwh

    def __load_hourlyDemandPerMonth(self, month):
        # extract demand
        monthlyDemand_path = pathlib.Path(self.scriptPath).joinpath("inputs", "monthlyDemandsPKL", f"month_{month}_demand.pkl")
        if not os.path.isfile(monthlyDemand_path):
            self.__load_hourlyDemandAllMonths()
            dfDemand = pd.read_pickle(monthlyDemand_path)
        else:
            dfDemand = pd.read_pickle(monthlyDemand_path)
        return dfDemand.iloc[:, 1:]

    def __load_hourlyDemandAllMonths(self):
        # extract demand
        hourlyDemand_file = pathlib.Path(self.scriptPath).joinpath("inputs", "HourlyDemands100.xlsx")
        skipRows = 1
        monthsForIter = ["01", "02", "03", "04", "05", "06", 
                         "07", "08", "09", "10", "11", "12"]
        for monthIter in monthsForIter:
            daysInMonth = monthrange(2018, int(monthIter))
            hoursInMonth = 24 * daysInMonth[1]  # number of hours in month
            monthlyDemand_path = pathlib.Path(self.scriptPath).joinpath("inputs", "monthlyDemandsPKL", f"month_{monthIter}_demand.pkl")
            if not os.path.isfile(monthlyDemand_path):
                t = pd.read_excel(hourlyDemand_file, sheet_name='Residential', index_col=None, header= None, skiprows=skipRows, nrows=hoursInMonth)
                # create load helper method
                help_obj = loadHelper(initfreq='H', finalFreq=self.freq)
                # call method for processing series
                dfDemand = help_obj.process_pdFrameMonthly(monthIter, t)
                dfDemand.to_pickle(monthlyDemand_path)
            else:
                skipRows += hoursInMonth


#+ =======================================
def main():
    # get file path
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # define initParams
    initParams = dict()
    initParams["output_dir"] = str(script_path)
    initParams["freq"] = "H"  # "15min", "30min" (For EV charging), "H"
    rates_obj = georgiaRates(initParams)
    month = "01"  # "01"-jan, "02"-feb,...
    rate = rates_obj.ResidentialService(month)

#+ =======================================
if __name__ == "__main__":
    main()
