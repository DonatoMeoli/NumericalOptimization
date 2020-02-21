import numpy as np
import pytest

from optimization.optimization_function import quad1, quad2, quad5, Rosenbrock
from optimization.unconstrained.rprop import RProp


def test_Rprop_quadratic():
    x, _ = RProp(quad1).minimize()
    np.allclose(x, quad1.x_star())

    x, _ = RProp(quad2).minimize()
    np.allclose(x, quad2.x_star())

    x, _ = RProp(quad5).minimize()
    np.allclose(x, quad5.x_star())


def test_Rprop_Rosenbrock():
    obj = Rosenbrock()
    x, _ = RProp(obj).minimize()
    assert np.allclose(x, obj.x_star(), rtol=1e-4)


if __name__ == "__main__":
    pytest.main()