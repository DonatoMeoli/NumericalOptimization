import matplotlib.pyplot as plt
import numpy as np

from optimization import Rosenbrock
from optimization.optimizer import LineSearchOptimizer
from optimization.unconstrained.line_search import backtracking_line_search


class AcceleratedGradient(LineSearchOptimizer):
    # Apply a Accelerated Gradient approach for the minimization of the
    # provided function f.
    #
    # Input:
    #
    # - x is either a [n x 1] real (column) vector denoting the input of
    #   f(), or [] (empty).
    #
    # Output:
    #
    # - v (real, scalar): if x == [] this is the best known lower bound on
    #   the unconstrained global optimum of f(); it can be -inf if either f()
    #   is not bounded below, or no such information is available. If x ~= []
    #   then v = f(x).
    #
    # - g (real, [n x 1] real vector): this also depends on x. if x == []
    #   this is the standard starting point from which the algorithm should
    #   start, otherwise it is the gradient of f() at x (or a subgradient if
    #   f() is not differentiable at x, which it should not be if you are
    #   applying the gradient method to it).
    #
    # The other [optional] input parameters are:
    #
    # - x (either [n x 1] real vector or [], default []): starting point.
    #   If x == [], the default starting point provided by f() is used.
    #
    # - a_start (real scalar, optional, default value 1): abs(a_start) is taken
    #   as the starting value of alpha in the line search. This is especially
    #   important in  Accelerated Gradient because it can be considered the estimate of
    #   1 / L, which is crucial in the analysis of the algorithm, especially if no
    #   line search is performed (see m1 below). If a line search is used and
    #   a_start > 0, the provided value is used anew at each iteration, while if
    #   a_start < 0 then the starting value at iteration i is the optimal value
    #   at iteration i - 1 as the convergence theory requires. This is of
    #   course immaterial if no line search is done.
    #
    # - m1 (real scalar, optional, default value 0): parameter of the Armijo
    #   condition (sufficient decrease) in the backtracking line search. Has
    #   to be in [0,1), with the special value 0 meaning "no line search",
    #   i.e., fixed step size.
    #
    # - mon (integer scalar, optional, default value 0): if ~= 0 imposes the
    #   use of the monotone version of the method, which costs a further
    #   function evaluation per each iteration
    #
    # - wf (integer scalar, optional, default value 0): which fast gradient
    #   formula to use; there are four available (0, 1, 2, 3)
    #
    # - eps (real scalar, optional, default value 1e-6): the accuracy in the
    #   stopping criterion: the algorithm is stopped when the norm of the
    #   gradient is less than or equal to eps. If a negative value is provided,
    #   this is used in a *relative* stopping criterion: the algorithm is
    #   stopped when the norm of the gradient is less than or equal to
    #   (- eps) * || norm of the first gradient ||.
    #
    # - max_f_eval (integer scalar, optional, default value 1000): the maximum
    #   number of function evaluations (hence, iterations will be not more than
    #   max_f_eval because at each iteration at least a function evaluation is
    #   performed, possibly more due to the line search).
    #
    # - m2 (real scalar, optional, default value 0.9): typically the second
    #   parameter of the Armijo-Wolfe-type line search (strong curvature
    #   condition). It should to be in (0,1); if not, it is taken to mean that
    #   the simpler Backtracking line search should be used instead
    #
    # - tau (real scalar, optional, default value 0.9): scaling parameter for
    #   the Backtracking line search, each time the step is multiplied by tau
    #   (hence it is decreased).
    #
    # - m_inf (real scalar, optional, default value -inf): if the algorithm
    #   determines a value for f() <= m_inf this is taken as an indication that
    #   the problem is unbounded below and computation is stopped
    #   (a "finite -inf").
    #
    # - min_a (real scalar, optional, default value 1e-16): if the algorithm
    #   determines a step size value <= min_a, this is taken as an indication
    #   that something has gone wrong (the gradient is not a direction of
    #   descent, so maybe the function is not differentiable) and the line
    #   search is stopped (but the algorithm as a whole is not, as it is a
    #   non-monotone algorithm).
    #
    # Output:
    #
    # - x ([n x 1] real column vector): the best solution found so far.
    #
    # - status (string): a string describing the status of the algorithm at
    #   termination
    #
    #   = 'optimal': the algorithm terminated having proven that x is a(n
    #     approximately) optimal solution, i.e., the norm of the gradient at x
    #     is less than the required threshold
    #
    #   = 'unbounded': the algorithm has determined an extremely large negative
    #     value for f() that is taken as an indication that the problem is
    #     unbounded below (a "finite -inf", see m_inf above)
    #
    #   = 'stopped': the algorithm terminated having exhausted the maximum
    #     number of iterations: x is the bast solution found so far, but not
    #     necessarily the optimal one
    #
    #   = 'error': the algorithm found a numerical error that prevents it from
    #     continuing optimization (see min_a above)

    def __init__(self, f, x=None, a_start=1, m1=0, mon=1e-6, wf=0, eps=1e-6, max_f_eval=1000,
                 tau=0.9, m_inf=-np.inf, min_a=1e-16, verbose=False, plot=False):
        super().__init__(f, x, eps, max_f_eval, a_start=a_start, tau=tau, m_inf=m_inf,
                         min_a=min_a, verbose=verbose, plot=plot)
        if not np.isscalar(m1):
            raise ValueError('m1 is not a real scalar')
        if m1 < 0 or m1 >= 1:
            raise ValueError('m1 is not in [0,1)')
        self.m1 = m1
        if not np.isscalar(mon):
            raise ValueError('mon is not a real scalar')
        self.mon = mon
        if not np.isscalar(wf):
            raise ValueError('wf is not a real scalar')
        if wf < 0 or wf > 3:
            raise ValueError('unknown fast gradient formula {:d}'.format(wf))
        self.wf = wf

    def minimize(self):
        f_star = self.f.function([])

        last_x = np.zeros((self.n, 1))  # last point visited in the line search
        last_g = np.zeros((self.n, 1))  # gradient of last_x
        f_eval = 1  # f() evaluations count ("common" with LSs)

        if self.verbose:
            if f_star > -np.inf:
                print('f_eval\trel gap', end='')
            else:
                print('f_eval\tf(x)', end='')
            print('\t\t|| g(x) ||\tgamma\tls fev\ta*')

        i = 1
        gamma = 1
        if self.wf == 3:
            d = np.zeros((self.n, 1))

        y = self.x
        past_y = self.x
        if self.mon:
            past_x = self.x
            past_xv = np.inf

        if self.plot and self.n == 2:
            surface_plot, contour_plot, contour_plot, contour_axes = self.f.plot()

        while True:
            # compute f(y)
            v, g = self.f.function(y), self.f.jacobian(y)
            ng = np.linalg.norm(g)
            if f_eval == 1 and self.eps < 0:
                ng0 = -ng  # norm of first subgradient
            else:
                ng0 = 1  # un-scaled stopping criterion

            f_eval += 1

            if self.mon:  # in the monotone version
                if v < past_xv:  # if y is better than x
                    self.x = y  # then x = y
                    past_xv = v

            # output statistics
            if self.verbose:
                if f_star > -np.inf:
                    print('{:4d}\t{:1.4e}\t{:1.4e}\t{:1.4f}'.format(
                        f_eval, (v - f_star) / max(abs(f_star), 1), ng, gamma), end='')
                else:
                    print('{:4d}\t{:1.8e}\t\t{:1.4e}\t{:1.4f}'.format(f_eval, v, ng, gamma), end='')

            # stopping criteria
            if ng <= self.eps * ng0:
                status = 'optimal'
                break

            if f_eval > self.max_f_eval:
                status = 'stopped'
                break

            d = -g

            # compute step size
            if self.m1 > 0:
                a, v, last_x, last_g, _, f_eval = \
                    backtracking_line_search(self.f, d, self.x, last_x, last_g, None, f_eval, self.max_f_eval,
                                             self.min_a, v, -ng, abs(self.a_start), self.m1, self.tau, self.verbose)

                if self.a_start < 0:
                    self.a_start = -a
            else:  # fixed step size
                a = abs(self.a_start)
                last_x = y - a * g

                if self.mon:  # in the monotone version
                    xv = self.f.function(last_x)

            # output statistics
            if self.verbose:
                print('\t{:1.2e}'.format(a))

            if a <= self.min_a:
                status = 'error'
                break

            if v <= self.m_inf:
                status = 'unbounded'
                break

            # possibly plot the trajectory
            if self.plot and self.n == 2:
                p_xy = np.hstack((self.x, last_x))
                contour_axes.plot(p_xy[0], p_xy[1], color='k')

            if self.mon:  # in the monotone version
                if xv > past_xv:  # if the new x is worse than the last x
                    last_x = past_x  # then new x = last x
                else:
                    past_x = last_x
                    past_xv = xv

            # perform appropriate black magic
            if self.wf == 0:
                past_gamma = gamma
                gamma = (np.sqrt(4 * gamma ** 2 + gamma ** 4) - gamma ** 2) / 2
                beta = gamma * (1 / past_gamma - 1)
            elif self.wf == 1:
                past_gamma = gamma
                gamma = (1 + np.sqrt(1 + 4 * past_gamma)) / 2
                beta = (past_gamma - 1) / gamma
            elif self.wf == 2:
                beta = i / (i + 3)

            if self.wf < 3:
                y = last_x + beta * (last_x - self.x)
            else:
                d = (2 / (i + 2)) * g + (i / (i + 2)) * d
                z = -((i + 1) * (i + 2) * a / 4) * d
                y = (2 / (i + 3)) * z + ((i + 1) / (i + 3)) * last_x

            self.x = last_x

            if self.n == 2 and self.plot:
                p_xy = np.hstack((y, past_y))
                contour_axes.plot(p_xy[0], p_xy[1], color='r')
                past_y = y

            i += 1

        if self.verbose:
            print()
        if self.plot and self.n == 2:
            plt.show()
        return self.x, status


if __name__ == "__main__":
    print(AcceleratedGradient(Rosenbrock(), verbose=True, plot=True).minimize())