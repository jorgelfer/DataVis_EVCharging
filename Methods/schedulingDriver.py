"""
by Jorge
"""

# required for processing
import numpy as np
import pandas as pd
import pathlib
#required for plotting
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 12})
from Methods.SLP_dispatch_simp import SLP_dispatch
from Methods.LP_dispatch import LP_dispatch
from Methods.plotting import plottingDispatch
from Methods.loadHelper import loadHelper


# Methods
def create_battery(PTDF, pointsInTime, sbus, batSize):
    """function to define battery parameters"""
    batt = dict()
    numBatteries = 3
    batt['numBatteries'] = numBatteries
    BatIncidence = np.zeros((len(PTDF.columns), numBatteries))
    BatIncidence[PTDF.columns == sbus + '.1', 0] = 1
    BatIncidence[PTDF.columns == sbus + '.2', 1] = 1
    BatIncidence[PTDF.columns == sbus + '.3', 2] = 1
    batt['BatIncidence'] = BatIncidence
    nodes = np.where(np.any(BatIncidence, 1))[0]
    BatSizes = batSize * np.ones((1, numBatteries))
    batt['BatSizes'] = BatSizes
    BatChargingLimits = (24 / pointsInTime) * 100 * np.ones((1, numBatteries))
    batt['BatChargingLimits'] = BatChargingLimits
    BatEfficiencies = 0.97 * np.ones((1, numBatteries))
    batt['BatEfficiencies'] = BatEfficiencies
    np.random.seed(2022)  # Set random seed so results are repeatable
    BatInitEnergy = BatSizes * np.random.uniform(0.5, 0.8, size=(1, numBatteries))
    batt['BatInitEnergy'] = BatInitEnergy
    Pbatcost = 0.01
    batt['Pbatcost'] = Pbatcost
    ccharbat = Pbatcost * np.ones((1, 2 * numBatteries * pointsInTime))
    batt['ccharbat'] = ccharbat
    ccapacity = Pbatcost * np.ones((1, numBatteries * (pointsInTime + 1)))
    batt['ccapacity'] = ccapacity
    batt['BatPenalty'] = np.ones((1, numBatteries))
    return batt, nodes

def create_reg(dxdr):
    """function to define regulator parameters"""
    reg = dict()
    numRegs = len(dxdr.columns)
    reg['numRegs'] = numRegs
    reg['tapInit'] = np.zeros((1, numRegs))
    reg['tapChange'] = 3 * np.ones((1, numRegs))
    reg['regMaxTap'] = 16 * np.ones((1, numRegs))
    return reg


def load_PTDF(script_path, case):
    '''function to load PTDF'''
    PTDF_file = pathlib.Path(script_path).joinpath("inputs", case, "PTDF.pkl")
    PTDF = pd.read_pickle(PTDF_file)
    # adjust lossless PTDF
    PTDF = PTDF / 10  # divide by perturbation injection value
    return PTDF


def load_generationCosts(script_path, n, pointsInTime, freq):
    '''function to load generations costs and perform interpolation'''
    GenPrice_file = pathlib.Path(script_path).joinpath("inputs", "HourlyMarginalPrice.xlsx")
    tcost = pd.read_excel(GenPrice_file)
    gCost = 10000 * np.ones((n, pointsInTime))
    # create load helper method
    help_obj = loadHelper(initfreq='H', finalFreq=freq, price=True)
    cost_wednesday = pd.Series(tcost.values[225, 1:-1])  # 2018-08-14
    # call method for processing series
    cost_wednesday = help_obj.process_pdSeries(cost_wednesday)
    cost_wednesday = np.squeeze(cost_wednesday.values)
    gCost[0, :] = cost_wednesday
    gCost[1, :] = cost_wednesday
    gCost[2, :] = cost_wednesday
    # Define generation limits
    Gmax = np.zeros((n, 1))
    Gmax[0, 0] = 2000  # asume the slack conventional phase is here
    Gmax[1, 0] = 2000  # asume the slack conventional phase is here
    Gmax[2, 0] = 2000  # asume the slack conventional phase is here
    return gCost, cost_wednesday, Gmax


def create_PVsystems(freq, Gmax, PTDF, gCost, cost_wednesday, pv1bus, pv2bus, pvSize):
    '''function to Define the utility scale PVs'''
    nodesPV1 = [pv1bus + '.1', pv1bus + '.2', pv1bus + '.3']
    nodesPV2 = [pv2bus + '.1', pv2bus + '.2', pv2bus + '.3']
    # define the PV location
    PV1 = np.stack([PTDF.columns == nodesPV1[0], PTDF.columns == nodesPV1[1],
                    PTDF.columns == nodesPV1[2]], axis=1)
    PV2 = np.stack([PTDF.columns == nodesPV2[0], PTDF.columns == nodesPV2[1],
                    PTDF.columns == nodesPV2[2]], axis=1)
    PVnodes = np.any(np.concatenate([PV1, PV2], axis=1), axis=1)
    # define the maximum output
    Gmax[np.where(np.any(PV1, axis=1))[0]] = pvSize  # Utility scale Solar PV
    Gmax[np.where(np.any(PV2, axis=1))[0]] = pvSize  # Utility scale Solar PV

    if pv1bus == pv2bus:
        Gmax[np.where(np.any(PV1, axis=1))[0]] = 300
    # define the cost
    gCost[PVnodes] = 0.1 * cost_wednesday  # *np.mean(cost_wednesday)
    # create load helper method
    help_obj = loadHelper(initfreq='H', finalFreq=freq)
    # Estimate a PV Profile
    np.random.seed(2022)
    a = np.sin(np.linspace(-4, 19, 24) * np.pi / 15) - 0.5 + np.random.rand(24) * 0.2
    a[a < 0] = 0
    a = a / max(a)
    # call method for processing series
    PVProfile = help_obj.process_pdSeries(pd.Series(a))
    PVProfile[PVProfile < 0.01] = 0
    PVProfile = np.squeeze(PVProfile.values)
    return Gmax, gCost, PVnodes, PVProfile


def compute_penaltyFactors(PTDF, source):
    '''function to Compute penalty factors'''
    # compute dPgref
    dPgref = np.min(PTDF[:3])
    # dPl/dPgi = 1 - (- dPgref/dPgi) -> eq. L9_25
    # ITLi = dPL/dPGi
    ITL = 1 + dPgref  # Considering a PTDF with transfer from bus i to the slack. If PTDF is calculated in the converse, then it will be 1 - dPgref
    Pf = 1 / (1 - ITL)
    # substation correction
    Pf[source + '.1'] = 1
    Pf[source + '.2'] = 1
    Pf[source + '.3'] = 1
    return Pf


def load_voltageSensitivity(script_path, case):
    '''funtion to load voltage sensitivity'''
    # voltage sensitivity
    dfVS_file = pathlib.Path(script_path).joinpath("inputs", case, "VoltageSensitivity.pkl")
    dfVS = pd.read_pickle(dfVS_file)
    # adjust voltage sensi matrix
    dfVS = dfVS / 10  # divide by perturbation injection value
    return dfVS


def load_RegSensitivities(script_path, dssCase):
    '''funtion to load voltage sensitivity'''
    # voltage sensitivity
    dVdR = pd.read_pickle(pathlib.Path(script_path).joinpath("inputs", dssCase,
                          "VoltageToRegSensitivity.pkl"))
    dPjkdR = pd.read_pickle(pathlib.Path(script_path).joinpath("inputs", dssCase,
                            "FlowsToRegSensitivity.pkl"))
    return dVdR, dPjkdR


def load_lineLimits(script_path, case, PTDF, pointsInTime, DR, Pij, Pjk_lim):
    '''function to load line Limits'''
    compare = Pij > Pjk_lim
    violatingLines = compare.any(axis=1)
    # Line Info
    Linfo_file = pathlib.Path(script_path).joinpath("inputs", case, "LineInfo.pkl")
    Linfo = pd.read_pickle(Linfo_file)
    return violatingLines, Linfo


def compute_violatingVolts(v_0, v_base, vmin, vmax):
    # extract violating Lines
    v_lb = (vmin * 1000) * v_base
    v_ub = (vmax * 1000) * v_base
    compare = (v_0 > v_ub) | (v_0 < v_lb)
    violatingVolts = compare.any(axis=1)
    return violatingVolts


def schedulingDriver(iterName, outDSS, initDSS, initParams, outES):
    # get init params
    batSize = int(initParams["batSize"])
    pvSize = int(initParams["pvSize"])
    case = initParams["case"]
    script_path = initParams["script_path"]
    freq = initParams["freq"]
    # extract init DSS results
    loadNames = initDSS['loadNames']
    demandProfile = initDSS['dfDemand']
    # extract output DSS results
    Pjk_lim = outDSS['limPjks']
    Pg_0 = outDSS['initPower']
    v_0 = outDSS['initVolts']
    Pjk_0 = outDSS['initPjks']
    v_base = outDSS['nodeBaseVolts']
    # process
    demandProfilei = demandProfile.any(axis=1)
    lnodes = np.where(demandProfilei)[0]
    pointsInTime = v_0.shape[1]
    # ####################
    # define flags
    flags = dict()
    flags["PF"] = True
    flags["DR"] = True

    if initParams["reg"] == 'True':
        flags["reg"] = True
    else:
        flags["reg"] = False

    if batSize == 0:
        flags["storage"] = False
    else:
        flags["storage"] = True

    if pvSize == 0:
        flags["PV"] = False
    else:
        flags["PV"] = True
    # ######################

    # resource location
    if case == '123bus':
        source = '150'
        sbus = '83'
        pv1bus = '66'
        pv2bus = '80'
    elif case == "13bus":
        source = 'sourcebus'
        sbus = '675'
        pv1bus = '692'
        pv2bus = '680'

    # reshape base voltage:
    v_basei = v_base.to_frame()
    v_base = np.kron(v_basei, np.ones((1, pointsInTime)))
    v_base = pd.DataFrame(v_base, index=v_basei.index, columns=v_0.columns)
    # violatingVolts = compute_violatingVolts(v_0, v_base, vmin, vmax)
    # load PTDF results
    PTDF = load_PTDF(script_path, case)
    n = len(PTDF.columns)
    m = len(PTDF)
    # Storage
    batt, Snodes = create_battery(PTDF, pointsInTime, sbus, batSize)
    # Penalty factors
    if flags["PF"]:
        pf = compute_penaltyFactors(PTDF, source)
    # round the PTDF (required for optimization)
    PTDF = PTDF.round()
    # Line costs
    pijCost = 0.1 * np.ones((m, pointsInTime))
    clin = np.reshape(pijCost.T, (1, pijCost.size), order="F")
    # Load generation costs
    gCost, cost_wednesday, Gmax = load_generationCosts(script_path, n, pointsInTime, freq)
    # Line limits and info
    _, Linfo = load_lineLimits(script_path, case, PTDF, pointsInTime, flags["DR"], Pjk_0, Pjk_lim)
    # Demand Response (cost of shedding load)
    np.random.seed(2022)  # Set random seed so results are repeatable
    DRcost = np.random.randint(100, 300, size=(1, n))
    cdr = np.kron(DRcost, np.ones((1, pointsInTime)))
    # PV system
    if flags["PV"]:
        Gmax, gCost, PVnodes, PVProfile = create_PVsystems(freq, Gmax, PTDF, gCost, cost_wednesday,
                                                           pv1bus, pv2bus, pvSize)
        # Normal gen
        max_profile = np.kron(Gmax, np.ones((1, pointsInTime)))
        # PV nodes
        max_profile[PVnodes, :] = max_profile[PVnodes, :] * PVProfile
    else:
        PVnodes = None
        # Normal gen
        max_profile = np.kron(Gmax, np.ones((1, pointsInTime)))
    # Overall Generation limits:
    Gmax = np.reshape(max_profile.T, (1, np.size(max_profile)), order='F')
    # Overall Generation costs:
    cgn = np.reshape(gCost.T, (1, gCost.size), order="F")
    # regulator costs
    val = 10
    unitCost = val * np.array([[1, .3, .3, .3, .3, .3, .3]])
    cctap = np.kron(unitCost, np.ones((1, pointsInTime)))
    val = 10
    unitCost = val * np.array([[1, .3, .3, .3, .3, .3, .3]])
    ccap = np.kron(unitCost, np.ones((1, pointsInTime + 1)))
    # create dict to store costs
    costs = dict()
    costs["cgn"] = cgn
    costs["cdr"] = cdr
    costs["clin"] = clin
    costs["cctap"] = cctap
    costs["ccap"] = ccap
    # load voltage base at each node
    dvdp = load_voltageSensitivity(script_path, case)
    # load regulator sensitivities
    dvdr, dpjkdr = load_RegSensitivities(script_path, case)
    # create a dict to store sensitivities
    sen = dict()
    sen["pf"] = pf
    sen["PTDF"] = PTDF
    sen["dvdp"] = dvdp
    sen["dvdr"] = dvdr
    sen["dpjkdr"] = dpjkdr

    # only want to control voltage at nodes with load
    modDSS = dict()
    modDSS['limPjks'] = Pjk_lim
    modDSS['initPower'] = Pg_0 
    modDSS["initVolts"] = v_0[demandProfilei.values]
    modDSS['initPjks'] = Pjk_0 
    modDSS["v_base"] = v_base[demandProfilei.values]  # store the temporally expanded vBase

    sen["dvdp"] = dvdp[demandProfilei.values]
    sen["dvdr"] = dvdr[demandProfilei.values]

    # init limits
    vmin = float(initParams["vmin"])
    vmax = float(initParams["vmax"])
    
    if outES is not None:
        # decrease the voltage limits a little bit
        if outDSS["violatingVolts"].any():
            indx = outDSS["violatingVolts"].values  #.index[outDSS["violatingVolts"]["bool"]].tolist()
            vmin = 1.001 * outES["vmin"]
            vmax = 0.999 * outES["vmax"]
            outES["vmin"] = vmin
            outES["vmax"] = vmax

        # decrease line limits a little bit
        if outDSS["violatingLines"].any():
            indx = outDSS["violatingLines"].values  #.index[outDSS["violatingLines"]["bool"]].tolist()
            Pjk_lim[indx] = 0.999 * outES["limPjks"][indx]
            outES["limPjks"] = Pjk_lim

    # call the dispatch method
    if initParams["dispatchType"] == 'SLP':
        # create an instance of the dispatch class
        dispatch_obj = SLP_dispatch(Gmax, batt, costs, flags, sen, modDSS, initParams, outES)
        x, m, LMP = dispatch_obj.PTDF_SLP_OPF(initDSS)
    else:
        dispatch_obj = LP_dispatch(Gmax, batt, costs, flags, sen, modDSS, initParams)
        x, m, LMP, Ain = dispatch_obj.PTDF_LP_OPF()
    # Create plot object
    plot_obj = plottingDispatch(iterName, pointsInTime, initParams, PTDF=PTDF)
    # extract dispatch results
    Pg, Pdr, Pij, Pchar, Pdis, E, Tn, Tp = plot_obj.extractResults(x, flags, batt)

    # ###############
    # DR costs
    # ###############
    Pdr_1d = np.reshape(Pdr, np.size(Pdr), order="F")
    costPdr = cdr @ Pdr_1d.T

    # extract LMP results
    LMP = plot_obj.extractLMP(LMP, flags, batt)
    #
    # OUTPUT
    #
    outES = dict()
    outES["vmin"] = vmin
    outES["vmax"] = vmax
    outES["limPjks"] = Pjk_lim
    outES['costWednesday'] = cost_wednesday
    outES['J'] = m.objVal
    outES['DRcost'] = costPdr
    outES['LMP'] = pd.DataFrame(LMP[lnodes, :], np.asarray(PTDF.columns[lnodes]), v_0.columns)

    if flags["reg"]:
        outES['R'] = pd.DataFrame(Tp - Tn, index=dvdr.columns, columns=v_0.columns)
    else:
        outES['R'] = None

    if flags["DR"]:
        lnames = [loadNames.loc[n] for n in PTDF.columns[lnodes]]
        outES['DR'] = pd.DataFrame(Pdr[lnodes, :], index=np.asarray(lnames), columns=v_0.columns)
        outES['DR_node'] = pd.DataFrame(Pdr[lnodes, :], index=PTDF.columns[lnodes], columns=v_0.columns)
    else:
        outES['DR'] = None

    if flags["PV"]:
        outES['Gen'] = pd.DataFrame(Pg[PVnodes, :], np.asarray(PTDF.columns[PVnodes]), v_0.columns)
        outES['maxOutput'] = outES['Gen'].max(axis=1)
    else:
        outES['Gen'] = None
    # check storage
    if flags["storage"]:
        outES['Pchar'] = pd.DataFrame(Pchar, np.asarray(PTDF.columns[Snodes]), v_0.columns)
        outES['Pdis'] = pd.DataFrame(Pdis, np.asarray(PTDF.columns[Snodes]), v_0.columns)
    else:
        outES['Pchar'] = None
        outES['Pdis'] = None
    # plot output
    if initParams["plot"] == "True":
        # plot demand response
        if flags["DR"]:
            plot_obj.plot_DemandResponse(outES["DR"])
        # plot Dispatch
        dfPg = pd.DataFrame(Pg, PTDF.columns, v_0.columns)
        plot_obj.plot_Dispatch(dfPg.iloc[3:])
        # plot taps
        if flags["reg"]:
            plot_obj.plot_reg(outES['R'])
        # plot Storage
        if flags["storage"]:
            plot_obj.plot_storage(E, batt, gCost[0, :])

    return outES
