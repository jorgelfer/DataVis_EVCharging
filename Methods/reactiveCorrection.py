import numpy as np
import py_dss_interface
import os
import pathlib
import pandas as pd
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 20})


ext = ".pdf"

class reactiveCorrection:

    def __init__(self, dss, output_dir, iterName):
        self.dss = dss
        self.output_dir = output_dir
        self.iterName = iterName

    def compute_correction(self, vo, baseVoltage, phiNames, pjk, qjk):

        # get line Yprim
        Sjk_max, Yjk, Gjk, Bjk, vj_dic, vk_dic, lineNames = self.__getLineYprim(baseVoltage, vo)
        
        # prelocation
        Pjk_lim = np.zeros((len(lineNames), len(vo.columns)))

        # evolution
        pjkcc = list() 
        qjkcc = list() 
        sjkcc = list() 
        
        for l, line in enumerate(lineNames):
            for t, time in enumerate(vo.columns): 
                vj = np.expand_dims(vj_dic[line].loc[:,time].values,1)
                vk = np.expand_dims(vk_dic[line].loc[:,time].values,1)
                
                # compute constants
                Pjk_C = vj.T @ Gjk[line] @ np.conjugate(vj)
                Pjk_C = np.real(Pjk_C[0][0]) / 1000 # to work in kW
                Qjk_C = -vj.T @ Bjk[line] @ np.conjugate(vj)
                Qjk_C = np.real(Qjk_C[0][0]) / 1000 # to work in kVAr   
                Sjk_C = vj.T @ Yjk[line] @ np.conjugate(vk)
                Sjk_C = abs(Sjk_C[0][0]) / 1000 # to work in kVA
                MC = -(Pjk_C**2) - (Qjk_C**2) + (Sjk_C**2) 
                
                # compute quadratic constants
                a = (Pjk_C**2 + Qjk_C**2)
                b = - (Sjk_max[line]**2 - MC) * Pjk_C
                c = 1/4 *(Sjk_max[line]**2 - MC)**2 - (Sjk_max[line]**2)*(Qjk_C**2)
                
                # quadratic formula computation
                dis = (b**2) - (4*a*c)
                Pjk_lim[l,t] = (-b + np.sqrt(dis))/(2*a)

        Pjk_lim = pd.DataFrame(Pjk_lim, index=lineNames, columns=vo.columns)

        #define the phase based limit
        Pjk_phiLim, Sjk_phiLim = self.__definePhaseLim(baseVoltage, Pjk_lim, Sjk_max)
        Pjk_phiLim = pd.DataFrame(np.vstack([Pjk_phiLim[l] for l in phiNames]), index=phiNames, columns=Pjk_lim.columns)
        Sjk_phiLim = pd.DataFrame(np.vstack([Sjk_phiLim[l] for l in phiNames]), index=phiNames, columns=Pjk_lim.columns)

        return Pjk_phiLim, Sjk_phiLim

    # Helper methods
    def __definePhaseLim(self, baseVoltage, Pjk_lim, Sjk_max):

        #phase-based name
        phiName = list()
        Pjk_phiLim = dict()
        Sjk_phiLim = dict()
        elements = self.dss.circuit_all_element_names()

        for i, elem in enumerate(elements):
            self.dss.circuit_set_active_element(elem)
            if "Line" in elem and "sw" not in elem:
                # get node-based line names
                buses = self.dss.cktelement_read_bus_names()
                
                # get nodes and discard the reference
                nodes = self.dss.cktelement_node_order()
                # reorder the number of nodes
                nodes = np.asarray(nodes).reshape((int(len(nodes)/2),-1),order="F")                
                    
                for t1n, t2n in zip(nodes[:,0],nodes[:,1]):
                    # define the phase-based name
                    phiName.append("L"+ buses[0].split(".")[0] + f".{t1n}" + "-" + buses[1].split(".")[0] + f".{t2n}")
                    # compute the phase-based normal rated power from the active PD element
                    Pjk_phiLim[phiName[-1]] = Pjk_lim.loc[elem,:].values / nodes.shape[0]
                    lim = Sjk_max[elem] / nodes.shape[0]
                    Sjk_phiLim[phiName[-1]] = lim * np.ones(len(Pjk_lim.columns)) 

            elif "sw" in elem:
                # get node-based line names
                buses = self.dss.cktelement_read_bus_names()
                
                # get nodes and discard the reference
                nodes = self.dss.cktelement_node_order()
                # reorder the number of nodes
                nodes = np.asarray(nodes).reshape((int(len(nodes)/2),-1),order="F")                
                    
                for t1n, t2n in zip(nodes[:,0],nodes[:,1]):
                    # define the phase-based name
                    phiName.append("L"+ buses[0].split(".")[0] + f".{t1n}" + "-" + buses[1].split(".")[0] + f".{t2n}")
                    # compute the normal rated power from the active PD element
                    lim = 1.5*self.dss.cktelement_read_norm_amps() * baseVoltage[buses[0].split(".")[0]+ f".{t1n}"]
                    Pjk_phiLim[phiName[-1]] = lim * np.ones(len(Pjk_lim.columns)) 
                    Sjk_phiLim[phiName[-1]] = lim * np.ones(len(Pjk_lim.columns)) 

            elif "Transformer" in elem:
                # get buses
                buses = self.dss.cktelement_read_bus_names()
            
                # get this element node and discard the reference
                nodes = [i for i in self.dss.cktelement_node_order() if i != 0]
                # reorder the number of nodes
                nodes = np.asarray(nodes).reshape((int(len(nodes)/2),-1),order="F")
                
                for t1n, t2n in zip(nodes[:,0],nodes[:,1]):
                    # define phase based name
                    phiName.append("T"+ buses[0].split(".")[0] + f".{t1n}" + "-" + buses[1].split(".")[0] + f".{t2n}") 
                    # compute the normal rated power from the active PD element
                    lim = self.dss.cktelement_read_norm_amps() * baseVoltage[buses[0].split(".")[0]+ f".{t1n}"]
                    Pjk_phiLim[phiName[-1]] = lim * np.ones(len(Pjk_lim.columns)) 
                    Sjk_phiLim[phiName[-1]] = lim * np.ones(len(Pjk_lim.columns)) 

        return Pjk_phiLim, Sjk_phiLim


    def __getLineYprim(self, baseVoltage, vo):

        # prelocate 
        elements = self.dss.circuit_all_element_names()
        Sjk_max = dict()
        Yjk = dict()
        Gjk = dict()
        Bjk = dict()
        
        Vj = dict()
        Vk = dict()
        lineNames = list()
    
        for i, elem in enumerate(elements):
            self.dss.circuit_set_active_element(elem)
            if "Line" in elem and "sw" not in elem:
                
                # store line element name
                lineNames.append(elem)
                
                # get node-based line names
                buses = self.dss.cktelement_read_bus_names()
                
                # get number of nodes including reference
                n = len(self.dss.cktelement_node_order())
                
                # extract and organize yprim
                yprim_tmp = self.dss.cktelement_y_prim()
                yprim_tmp = np.asarray(yprim_tmp).reshape((2*n,n), order="F")
                yprim_tmp =yprim_tmp.T
                yprim_tmp_B =yprim_tmp[:int(n/2),:n]
                yprim_tmp = -yprim_tmp[:int(n/2),n:]
                Gprim = yprim_tmp[:, 0::2]
                Gjk[elem] = Gprim
                Bprim = yprim_tmp_B[:, 1::2]
                Bjk[elem] = Bprim
                Yprim = yprim_tmp[:, 0::2] + 1j* yprim_tmp[:, 1::2]
                Yjk[elem] = Yprim
                
                # get nodes and discard the reference
                nodes = self.dss.cktelement_node_order()
                
                # reorder the number of nodes
                nodes = np.asarray(nodes).reshape((int(len(nodes)/2),-1),order="F")                
                    
                # voltages
                vbus1 = list()
                vbus2 = list()
                
                # MVA limit
                Sjk = 0
                
                for t1n, t2n in zip(nodes[:,0],nodes[:,1]):
                    # line nodes nodes
                    node_bus1 = buses[0].split(".")[0] + f'.{t1n}'
                    node_bus2 = buses[1].split(".")[0] + f'.{t2n}'
                    
                    # voltage
                    vbus1.append(vo.loc[node_bus1,:])
                    vbus2.append(vo.loc[node_bus2,:])
                    
                    # MVA limit
                
                    if Yprim.shape[0] < 2:
                        ampacity = 230 
                    else:
                        ampacity = 530

                    Sjk += ampacity * baseVoltage[node_bus1] # base voltage in KV 

                # store line buses initial voltages
                Vj[elem] = pd.concat(vbus1, axis=1).T
                Vk[elem] = pd.concat(vbus2, axis=1).T
                # MVA limit
                Sjk_max[elem] = Sjk

        return Sjk_max, Yjk, Gjk, Bjk, Vj, Vk, lineNames


#+===========================================================================
def main():

    script_path = os.path.dirname(os.path.abspath(__file__))
    dss_file = pathlib.Path(script_path).joinpath("..", "EV_data", "123bus", "IEEE123Master.dss")
    
    dss = py_dss_interface.DSSDLL()
    dss.text(f"Compile [{dss_file}]")

    # compute yprimitive
    Qobj = reactiveCorrection(dss) 
    lines, ymat = Qobj.getLineYprim()

#+===========================================================================
if __name__ == "__main__":
    main()

