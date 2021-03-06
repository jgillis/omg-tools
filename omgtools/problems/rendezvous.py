# This file is part of OMG-tools.
#
# OMG-tools -- Optimal Motion Generation-tools
# Copyright (C) 2016 Ruben Van Parys & Tim Mercy, KU Leuven.
# All rights reserved.
#
# OMG-tools is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

from admm import ADMMProblem
from point2point import FreeEndPoint2point
import numpy as np


class RendezVous(ADMMProblem):

    def __init__(self, fleet, environment, options={}):
        problems = []
        for veh in fleet.vehicles:
            free_ind = fleet.configuration[veh].keys()
            problems.append(
                FreeEndPoint2point(veh, environment.copy(), options, {veh: free_ind}))
        ADMMProblem.__init__(self, problems, options)
        problems_dic = {veh: problems[l]
                        for l, veh in enumerate(fleet.vehicles)}
        self.fleet = fleet

        # define parameters
        rel_conT = {veh: self.define_parameter('rcT'+str(l), len(self.fleet.configuration[
                                               veh].keys()), len(self.fleet.get_neighbors(veh))) for l, veh in enumerate(self.vehicles)}

        # end pose constraints
        couples = {veh: [] for veh in self.vehicles}
        for veh in self.vehicles:
            ind_veh = sorted(self.fleet.configuration[veh].keys())
            rcT = rel_conT[veh]
            for l, nghb in enumerate(self.fleet.get_neighbors(veh)):
                ind_nghb = sorted(self.fleet.configuration[nghb].keys())
                if veh not in couples[nghb] and nghb not in couples[veh]:
                    couples[veh].append(nghb)
                    conT_veh = problems_dic[veh].get_variable('conT0')
                    conT_nghb = problems_dic[nghb].get_variable('conT0')
                    rcT_ = rcT[:, l]
                    for k in range(len(ind_veh)):
                        self.define_constraint(
                            conT_veh[ind_veh[k]] - conT_nghb[ind_nghb[k]] - rcT_[k], 0., 0.)

    def set_parameters(self, current_time):
        parameters = {}
        for l, veh in enumerate(self.vehicles):
            rel_conT, rcT_ = self.fleet.get_rel_config(veh), []
            for nghb in self.fleet.get_neighbors(veh):
                rcT_.append(np.c_[rel_conT[nghb]])
            parameters['rcT'+str(l)] = np.hstack(rcT_)
        return parameters

    def stop_criterium(self):
        res = 0.
        for veh in self.vehicles:
            ind_veh = sorted(self.fleet.configuration[veh].keys())
            rel_conT = self.fleet.get_rel_config(veh)
            for nghb in self.fleet.get_neighbors(veh):
                ind_nghb = sorted(self.fleet.configuration[nghb].keys())
                for k in range(len(ind_veh)):
                    rcT = rel_conT[nghb]
                    rcT = rcT if isinstance(rcT, float) else rcT[k]
                    res += np.linalg.norm(veh.trajectories['splines'][ind_veh[k], 0] -
                                          nghb.trajectories['splines'][ind_nghb[k], 0] -
                                          rcT)**2
        if np.sqrt(res) > 5.e-2:
            return False
        return True
