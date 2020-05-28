from abc import ABC

import numpy as np
from scipy.linalg import ldl

from ... import Optimizer
from ... import Quadratic
from ...utils import ldl_solve


class BoxConstrainedQuadraticOptimizer(Optimizer, ABC):

    def __init__(self, f, ub, eps=1e-6, max_iter=1000, callback=None, callback_args=(), verbose=False):
        if not isinstance(f, Quadratic):
            raise TypeError(f'{f} is not an allowed quadratic function')
        super().__init__(f, ub / 2,  # starts from the middle of the box
                         eps, max_iter, callback, callback_args, verbose)
        if any(u < 0 for u in ub):
            raise ValueError('the lower bound must be > 0')
        self.ub = ub


class LagrangianBoxConstrainedQuadratic(Quadratic):

    def __init__(self, quad, ub):
        """
        Construct the lagrangian relaxation of a box-constrained quadratic function defined as:

                        1/2 x^T Q x + q^T x : 0 <= x <= ub

        :param quad: box-constrained quadratic function to be relaxed
        """
        if not isinstance(quad, Quadratic):
            raise TypeError(f'{quad} is not an allowed quadratic function')
        super().__init__(quad.Q, quad.q)
        self.ndim *= 2
        # Compute the LDL^T Cholesky symmetric indefinite factorization
        # of Q because it is symmetric but could be not positive definite.
        # This will be used at each iteration to solve the Lagrangian relaxation.
        self.L, self.D, self.P = ldl(self.Q)
        if any(u < 0 for u in ub):
            raise ValueError('the lower bound must be > 0')
        self.ub = np.asarray(ub, dtype=np.float)
        self.primal = quad
        self.primal_solution = np.inf
        self.primal_value = np.inf

    def x_star(self):
        raise np.full(fill_value=np.nan, shape=self.ndim)

    def f_star(self):
        return np.inf

    def function(self, lmbda):
        """
        Compute the value of the lagrangian relaxation defined as:

             L(x, lambda) = 1/2 x^T Q x + q^T x - lambda_+^T (ub - x) - lambda_-^T x
            L(x, lambda) = 1/2 x^T Q x + (q^T + lambda_+^T - lambda_-^T) x - lambda_+^T ub

        where lambda_+^T are the second n components of lambda and lambda_-^T are the last n components;
        both controls the box-constraints and are constrained to be >= 0.

        The optimal solution of the Lagrangian relaxation is the unique solution of the linear system:

                Q x = q^T + lambda_+^T - lambda_-^T

        Since we have saved the LDL^T Cholesky factorization of Q,
        i.e., Q = L D L^T, we obtain this by solving:

             L D L^T x = q^T + lambda_+^T - lambda_-^T

        :param lmbda:
        :return: the function value
        """
        lmbda_p, lmbda_n = np.split(lmbda, 2)
        ql = self.q.T + lmbda_p - lmbda_n
        x = ldl_solve((self.L, self.D, self.P), -ql)
        return (0.5 * x.T.dot(self.Q) + ql.T).dot(x) - lmbda_p.T.dot(self.ub)

    def jacobian(self, lmbda):
        """
        Compute the jacobian of the lagrangian relaxation as follow: with x the optimal
        solution of the minimization problem, the gradient at lambda is:

                                [x - ub, -x]

        However, we rather want to maximize the lagrangian relaxation, hence we have to
        change the sign of both function values and gradient entries:

                                 [ub - x, x]
        :param lmbda:
        :return:
        """
        lmbda_p, lmbda_n = np.split(lmbda, 2)
        ql = self.q.T + lmbda_p - lmbda_n
        x = ldl_solve((self.L, self.D, self.P), -ql)
        g = np.hstack((self.ub - x, x))

        # compute an heuristic solution out of the solution x of
        # the Lagrangian relaxation by projecting x on the box
        x[x < 0] = 0
        idx = x > self.ub
        x[idx] = self.ub[idx]

        v = self.primal.function(x)
        if v < self.primal_value:
            self.primal_solution = x
            self.primal_value = -v

        return g