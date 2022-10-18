import numpy as np
import os
import pathlib
import pandas as pd
from loadHelper import loadHelper
from calendar import monthrange


class georgiaRates:
    def __init__(self, initParams):
        script_path = initParams["output_dir"]
        freq = initParams["freq"]
        month = initParams["month"]
        realDemand = self.__load_hourlyDemandPerMonth(script_path, month, freq)

    def residential(self):
        """TODO"""

    def __load_hourlyDemandPerMonth(self, scriptPath, month, freq):
        # extract demand
        hourlyDemand_file = pathlib.Path(scriptPath).joinpath("inputs", "HourlyDemands100.xlsx")
        skipRows = 1
        monthsForIter = ["01", "02", "03", "04", "05", "06", 
                         "07", "08", "09", "10", "11", "12"]
        for monthIter in monthsForIter:
            daysInMonth = monthrange(2018, int(monthIter))
            hoursInMonth = 24 * daysInMonth[1]  # number of hours in month
            monthlyDemand_path = pathlib.Path(scriptPath).joinpath("inputs", f"month_{monthIter}_demand.pkl")
            if not os.path.isfile(monthlyDemand_path):
                t = pd.read_excel(hourlyDemand_file, sheet_name='Residential', index_col=None, header= None, skiprows=skipRows, nrows=hoursInMonth)
                # create load helper method
                help_obj = loadHelper(initfreq='H', finalFreq=freq)
                # call method for processing series
                dfDemand = help_obj.process_pdFrameMonthly(monthIter, t)
                dfDemand.to_pickle(monthlyDemand_path)
            else:
                skipRows += hoursInMonth
        return dfDemand


#+ =======================================
def main():
    # get file path
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # define initParams
    initParams = dict()
    initParams["output_dir"] = str(script_path)
    initParams["freq"] = "H"  # "15min", "30min" (For EV charging), "H"
    initParams["month"] = "02"  # "01"-jan, "02"-feb,...
    rates_obj = georgiaRates(initParams)

#+ =======================================
if __name__ == "__main__":
    main()
