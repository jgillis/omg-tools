from optilayer import OptiFather, OptiChild
from fleet import get_fleet_vehicles
from plots import Plots
import time

class Simulator:

    def __init__(self, problem, options={}):
        self.set_default_options()
        self.set_options(options)
        self.problem = problem
        self.environment = problem.environment
        self.plot = Plots(problem.fleet, problem.environment)

    def set_default_options(self):
        self.options = {'update_time': 0.1}

    def set_options(self, options):
        self.options.update(options)

    def run(self):
        current_time = 0.
        self.problem.initialize()
        stop = False
        while not stop:
            stop = self.update(current_time)
            current_time += self.options['update_time']
        self.problem.final()

    def update(self, current_time):
        # solve problem
        self.problem.solve(current_time)
        # update vehicle(s) and environment
        self.problem.update_vehicles(current_time, self.options['update_time'])
        self.environment.update(current_time, self.options['update_time'])
        self.plot.update()
        # check termination criteria
        stop = self.problem.stop_criterium()
        return stop


class Problem(OptiChild):

    def __init__(self, fleet, environment, options={}, label='problem'):
        OptiChild.__init__(self, label)
        self.fleet, self.vehicles = get_fleet_vehicles(fleet)
        self.environment = environment
        self.environment.add_vehicle(self.vehicles)
        self.set_default_options()
        self.set_options(options)
        self.iteration = 0
        self.current_time = 0.0
        self.update_times = []

    # ========================================================================
    # Problem options
    # ========================================================================

    def set_default_options(self):
        self.options = {'verbose': 2, 'update_time': 0.1}
        self.options['solver'] = {'tol': 1e-3, 'linear_solver': 'ma57',
                                  'warm_start_init_point': 'yes',
                                  'print_level': 0, 'print_time': 0}
        self.options['codegen'] = {
            'jit': False, 'jit_options': {'flags': ['-O0']}}

    def set_options(self, options):
        if 'solver' in options:
            self.options['solver'].update(options['solver'])
        if 'codegen' in options:
            self.options['codegen'].update(options['codegen'])
        for key in options:
            if key not in ['solver', 'codegen']:
                self.options[key] = options[key]

    # ========================================================================
    # Create and solve problem
    # ========================================================================

    def init(self):
        children = [vehicle for vehicle in self.vehicles]
        children.extend([self.environment, self])
        self.father = OptiFather(children)
        self.problem, compile_time = self.father.construct_problem(self.options)
        self.father.init_transformations(self.init_primal_transform,
                                         self.init_dual_transform)

    def solve(self, current_time):
        self.current_time = current_time
        self.init_step(current_time)
        # set initial guess, parameters, lb & ub
        var = self.father.get_variables()
        par = self.father.set_parameters(current_time)
        lb, ub = self.father.update_bounds(current_time)
        # solve!
        t0 = time.time()
        self.problem({'x0': var, 'p': par, 'lbg': lb, 'ubg': ub})
        t1 = time.time()
        t_upd = t1-t0
        self.father.set_variables(self.problem.getOutput('x'))
        stats = self.problem.getStats()
        if stats.get("return_status") != "Solve_Succeeded":
            print stats.get("return_status")
        # print
        if self.options['verbose'] >= 1:
            self.iteration += 1
            if ((self.iteration-1) % 20 == 0):
                print "----|------------|------------"
                print "%3s | %10s | %10s " % ("It", "t upd", "time")
                print "----|------------|------------"
            print "%3d | %.4e | %.4e " % (self.iteration, t_upd, current_time)
        self.update_times.append(t_upd)

    # ========================================================================
    # Methods encouraged to override (very basic implementation)
    # ========================================================================

    def init_step(self, current_time):
        pass

    def init_variables(self):
        return {}

    def set_parameters(self, time):
        return {}

    def final(self):
        pass

    def initialize(self):
        pass

    def init_primal_transform(self, basis):
        return None

    def init_dual_transform(self, basis):
        return None

    # ========================================================================
    # Methods required to override (no general implementation possible)
    # ========================================================================

    def update_vehicles(self, current_time, update_time):
        raise NotImplementedError('Please implement this method!')

    def stop_criterium(self):
        raise NotImplementedError('Please implement this method!')