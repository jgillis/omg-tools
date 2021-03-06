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
from point2point import Point2point
import numpy as np


class FormationPoint2point(ADMMProblem):

    def __init__(self, fleet, environment, options={}):
        problems = [Point2point(vehicle, environment.copy(), options)
                    for vehicle in fleet.vehicles]
        ADMMProblem.__init__(self, problems, options)
        self.fleet = fleet

        # define parameters
        rel_splines = {veh: self.define_parameter('rs'+str(l), len(self.fleet.configuration[
                                                  veh].keys()), len(self.fleet.get_neighbors(veh))) for l, veh in enumerate(self.vehicles)}

        # formation constraints
        couples = {veh: [] for veh in self.vehicles}
        for veh in self.vehicles:
            ind_veh = sorted(self.fleet.configuration[veh].keys())
            rs = rel_splines[veh]
            for l, nghb in enumerate(self.fleet.get_neighbors(veh)):
                ind_nghb = sorted(self.fleet.configuration[nghb].keys())
                if veh not in couples[nghb] and nghb not in couples[veh]:
                    couples[veh].append(nghb)
                    spl_veh = veh.get_variable('splines0')
                    spl_nghb = nghb.get_variable('splines0')
                    rel_spl = rs[:, l]
                    for k in range(len(ind_veh)):
                        self.define_constraint(
                            spl_veh[ind_veh[k]] - spl_nghb[ind_nghb[k]] - rel_spl[k], 0., 0.)

        # terminal constraints (stability issue)
        for veh in self.vehicles:
            splines = veh.get_variable('splines0')
            for spline in splines:
                for d in range(1, veh.degree+1):
                    # constraints imposed on distributedproblem instance will be
                    # invoked on the z-variables (because it is interpreted as
                    # 'interconnection constraint')
                    self.define_constraint(spline.derivative(d)(1.), 0., 0.)
                    # this one will be invoked on the x-trajectory
                    veh.define_constraint(spline.derivative(d)(1.), 0., 0.)

    def set_parameters(self, current_time):
        parameters = {}
        for l, veh in enumerate(self.vehicles):
            rel_spl, rs_ = self.fleet.get_rel_config(veh), []
            for nghb in self.fleet.get_neighbors(veh):
                rs_.append(np.c_[rel_spl[nghb]])
            parameters['rs'+str(l)] = np.hstack(rs_)
        return parameters

    def get_interaction_error(self):
        error = 0.
        for veh in self.vehicles:
            ind_veh = sorted(self.fleet.configuration[veh].keys())
            n_samp = veh.signals['time'].shape[1]
            end_time = veh.signals['time'][:, -1]
            Ts = veh.options['sample_time']
            rs = self.fleet.get_rel_config(veh)
            spl_veh = veh.signals['splines']
            nghbs = self.fleet.get_neighbors(veh)
            for nghb in nghbs:
                ind_nghb = sorted(self.fleet.configuration[nghb].keys())
                spl_nghb = nghb.signals['splines']
                Dspl = spl_veh[ind_veh] - spl_nghb[ind_nghb]
                err_rel = np.zeros(n_samp)
                for k in range(n_samp):
                    Dspl_nrm = np.linalg.norm(Dspl[:, k])
                    rs_nrm = np.linalg.norm(rs[nghb])
                    err_rel[k] = ((Dspl_nrm - rs_nrm)/rs_nrm)**2
                err_rel_int = 0.
                for k in range(n_samp-1):
                    err_rel_int += 0.5*(err_rel[k+1] + err_rel[k])*Ts
                error += np.sqrt(err_rel_int/end_time)/len(nghbs)
        error /= self.fleet.N
        return error

    def final(self):
        ADMMProblem.final(self)
        err = self.get_interaction_error()
        print '%-18s %6g %%' % ('Formation error:', err*100.)
