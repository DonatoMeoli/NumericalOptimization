import matplotlib.pyplot as plt
import numpy as np

from optimization import Rosenbrock
from optimization.optimizer import Optimizer


class ProximalBundle(Optimizer):
    # Apply the Proximal Bundle Method for the minimization of the provided
    # function f.
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
    #   start, otherwise it is a subgradient of f() at x (possibly the
    #   gradient, but you should not apply this algorithm to a differentiable
    #   f)
    #
    # The other [optional] input parameters are:
    #
    # - x (either [n x 1] real vector or [], default []): starting point.
    #   If x == [], the default starting point provided by f() is used.
    #
    # - mu (real scalar, optional, default value 1): the fixed weight to be
    #   given to the stabilizing term throughout all the algorithm. It must
    #   be a strictly positive number.
    #
    # - m1 (real scalar, optional, default value 0.01): parameter of the
    #   Armijo-like condition used to declare a Serious Step; has to be in
    #   [0,1).
    #
    # - eps (real scalar, optional, default value 1e-6): the accuracy in the
    #   stopping criterion: the algorithm is stopped when the norm of the
    #   direction (optimal solution of the master problem) is less than or
    #   equal to mu * eps. If a negative value is provided, this is used in a
    #   *relative* stopping criterion: the algorithm is stopped when the norm
    #   of the direction is less than or equal to
    #      mu * (- eps) * || norm of the first gradient ||.
    #
    # - max_f_eval (integer scalar, optional, default value 1000): the maximum
    #   number of function evaluations (hence, iterations, since there is
    #   exactly one function evaluation per iteration).
    #
    # - m_inf (real scalar, optional, default value -inf): if the algorithm
    #   determines a value for f() <= m_inf this is taken as an indication that
    #   the problem is unbounded below and computation is stopped
    #   (a "finite -inf").
    #
    # Output:
    #
    # - x ([n x 1] real column vector): the best solution found so far.
    #
    # - status (string): a string describing the status of the algorithm at
    #   termination
    #
    #   = 'optimal': the algorithm terminated having proven that x is a(n
    #     approximately) optimal solution; this only happens when "cheating",
    #     i.e., explicitly uses v_* = f([]) > -inf, unless in the very
    #     unlikely case that f() spontaneously produces an almost-null
    #     subgradient
    #
    #   = 'unbounded': the algorithm has determined an extremely large negative
    #     value for f() that is taken as an indication that the problem is
    #     unbounded below (a "finite -inf", see m_inf above)
    #
    #   = 'stopped': the algorithm terminated having exhausted the maximum
    #     number of iterations: x is the bast solution found so far, but not
    #     necessarily the optimal one
    #
    #   = 'error': the solver of the master QP problem solver reported
    #     some error, which requires to stop optimization

    def __init__(self, f, x=None, mu=1, m1=0.01, eps=1e-6, max_iter=1000, m_inf=-np.inf, verbose=False, plot=False):
        super().__init__(f, x, eps, max_iter, verbose, plot)
        if not np.isscalar(mu):
            raise ValueError('mu is not a real scalar')
        if mu <= 0:
            raise ValueError('mu must be > 0')
        self.mu = mu
        if not np.isscalar(m1):
            raise ValueError('m1 is not a real scalar')
        if m1 < 0 or m1 > 1:
            raise ValueError('m1 is not in [0,1]')
        self.m1 = m1
        if not np.isscalar(m_inf):
            raise ValueError('m_inf is not a real scalar')
        self.m_inf = m_inf

    def minimize(self):
        f_star = self.f.function([])

        if self.verbose:
            if f_star > -np.inf:
                print('iter\trel gap\t\t|| d ||\t\tstep')
            else:
                print('iter\tf(x)\t\t\t|| d ||\t\tstep')

        # compute first function and subgradient
        fx, g = self.f.function(self.x), self.f.jacobian(self.x)

        G = g.T  # matrix of subgradients
        F = fx - g.T * self.x  # vector of translated function values
        # each (fxi , gi , xi) gives the constraint
        #
        #  v >= fxi + gi' * (x + d - xi) = gi' * (x + d) + (fi - gi' * xi)
        #
        # so we just keep the single constant fi - gi' * xi instead of xi

        ng = np.linalg.norm(g)
        if self.eps < 0:
            ng0 = -ng  # norm of first subgradient
        else:
            ng0 = 1  # un-scaled stopping criterion

        if self.plot and self.n == 2:
            surface_plot, contour_plot, contour_plot, contour_axes = self.f.plot()

        i = 1
        while True:
            # construct the master problem
            d = sdpvar(n, 1)
            v = sdpvar(1, 1)

            M = v * np.ones(np.size(G, 1), 1) >= F + G * (d + self.x)

            if f_star > -np.inf:
                # this is cheating: use information about f_star in the model
                M = M + [v >= f_star]

            c = v + self.mu * np.linalg.norm(d) ** 2 / 2

            # solve the master problem
            ops = sdpsettings('solver', 'QUADPROG', 'verbose', 0)

            diagnostics = optimize(M, c, ops)

            if diagnostics.problem != 0:
                status = 'error'
                break

            d = value(d)
            v = value(v)
            nd = np.linalg.norm(d)

            # output statistics
            if f_star > -np.inf:
                print('%4d\t%1.4e\t%1.4e'.format(i, (fx - f_star) / max(abs(f_star), 1), nd))
            else:
                print('%4d\t%1.8e\t\t%1.4e'.format(i, fx, nd))

            # stopping criteria

            if self.mu * nd <= self.eps * ng0:
                status = 'optimal'
                break

            if i > self.max_iter:
                status = 'stopped'
                break

            # compute function and subgradient

            fd, g = self.f.function(self.x + d)

            if fd <= self.m_inf:
                status = 'unbounded'
                break

            G = [G, OMPCSEMI, g.T]
            F = [F, OMPCSEMI, fd - g.T * (self.x + d)]

            # SS / NS decision

            new_x = self.x + d

            if fd <= fx + self.m1 * (v - fx):
                print('\tSS')
                if self.plot and self.n == 2:
                    p_xy = np.hstack((self.x, new_x))
                    contour_axes.plot(p_xy[0], p_xy[1], color='k')

                self.x = new_x
                fx = fd
            else:
                print('\tNS')
                if self.plot and self.n == 2:
                    p_xy = np.hstack((self.x, new_x))
                    contour_axes.plot(p_xy[0], p_xy[1], color='r')

            i += 1

        if self.verbose:
            print()
        if self.plot and self.n == 2:
            plt.show()
        return self.x, status


if __name__ == "__main__":
    print(ProximalBundle(Rosenbrock(), verbose=True, plot=True).minimize())