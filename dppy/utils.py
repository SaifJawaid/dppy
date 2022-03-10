import numpy as np
from numpy.linalg import det, matrix_rank
from scipy.special import betaln


def check_random_state(seed: object) -> np.random.RandomState:
    """Turn seed into a np.random.RandomState instance
    Parameters
    ----------
    seed : None | int | instance of RandomState
        If seed is None, return the RandomState singleton used by np.random.
        If seed is an int, return a new RandomState instance seeded with seed.
        If seed is already a RandomState instance, return it.
        Otherwise raise ValueError.

    Returns
    -------
    np.random.RandomState

    .. seealso::

        `Scikit learn source code <https://github.com/scikit-learn/scikit-learn/blob/7813f7efb/sklearn/utils/validation.py#L763>`_
    """
    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, (int, np.integer)):
        return np.random.RandomState(seed)
    if isinstance(seed, np.random.RandomState):
        return seed
    raise ValueError(
        "%r cannot be used to seed a numpy.random.RandomState" " instance" % seed
    )


def log_binom(r, k):
    if r == k:
        return 0.0
    return -(np.log(r + 1) + betaln(r - k + 1, k + 1))


def det_ST(array, S, T=None):
    """Compute :math:`\\det M_{S, T} = \\det [M_{ij}]_{i\\inS, j\\in T}`

    :param array:
        Matrix
    :type M:
        array_like

    :param S:
        collection of indices
    :type M:
        1D list, array_like

    :param T:
        collection of indices
    :type M:
        1D list, array_like, default None

    :return:
        - if `T is None` return :math:`\\det M_{S, S}`
        - else return :math:`\\det M_{S, T}`. If S=T=[], numpy convention = 1.0
    :rtype:
        float
    """

    if T is None:  # det M_SS = det M_S
        return det(array[np.ix_(S, S)])

    else:  # det M_ST, numpy deals with det M_[][] = 1.0
        return det(array[np.ix_(S, T)])


def check_square(matrix):
    if matrix is None:
        return None
    if matrix.shape != (matrix.shape[0],) * 2:
        raise ValueError("matrix is not 2D square")


def check_hermitian(matrix, indices=None):
    """Cheap test to check hermitianity M^* = M"""
    check_square(matrix)
    if matrix is None:
        return None
    idx = range(min(10, matrix.shape[0])) if indices is None else indices
    M = matrix[np.ix_(idx, idx)]
    if not np.allclose(M.conj().T, M):
        raise ValueError("matrix is not hermitian: M.conj().T != M")


def check_projection(matrix, indices=None):
    """Cheap test to check reproducing property: M^2 = M"""
    check_square(matrix)
    if matrix is None:
        return None
    M = matrix
    idx = range(min(10, matrix.shape[0])) if indices is None else indices
    if not np.allclose(M[idx, :].dot(M[:, idx]), M[np.ix_(idx, idx)]):
        raise ValueError("matrix is not a projection: M^2 != M")


def check_orthonormal_columns(matrix, indices=None):
    """Cheap test for checking orthonormality of columns of array: M.T M = I"""
    if matrix is None:
        return None
    idx = range(min(10, matrix.shape[1])) if indices is None else indices
    U = matrix[:, idx]
    if not np.allclose(U.T.dot(U), np.eye(len(idx))):
        raise ValueError("array  M.T M != I")


def check_equal_to_O_or_1(array, tol=1e-8):
    """Check if entries are **all** in :math:`\\{0, 1\\}`, for a given tolerance"""
    if array is None:
        return None

    eq_0_or_1 = np.abs(array) <= tol
    np.logical_xor(eq_0_or_1, np.abs(1 - array) <= tol, out=eq_0_or_1)
    if not np.all(eq_0_or_1):
        raise ValueError("array with entries not all in {0,1}")


def check_in_01(array, tol=1e-8):
    """Check if entries are **all** in :math:`[0, 1]`, for a given tolerance"""
    if array is None:
        return

    in_01 = -tol <= array
    np.logical_and(in_01, array <= 1.0 + tol, out=in_01)
    if not np.all(in_01):
        raise ValueError("array with entries not all in [0,1]")


def check_geq_0(array, tol=1e-8):
    r"""Check if entries are **all** :math:`\geq0`, for a given tolerance"""
    if array is None:
        return

    if not np.all(array >= -tol):
        raise ValueError("array entries not all >= 0")


def check_full_row_rank(matrix):
    # Check rank(M) = #rows
    if matrix is None:
        return None

    d, N = matrix.shape
    err_print = "array (size = dxN) is not full row rank"

    if d > N:
        raise ValueError(err_print + "d(={}) > N(={})".format(d, N))
    else:
        rank = matrix_rank(matrix)
        if rank == d:
            return matrix
        else:
            raise ValueError(err_print + "d(={}) != rank(={})".format(d, rank))


def stable_filter(eigenvec, eigenval):
    """Given eigendecomposition of a PSD matrix, compute a reduced (thin) version containing only stable eigenvalues."""
    n = eigenvec.shape[0]

    if eigenvec.shape != (n, n) or eigenval.shape != (n,):
        raise ValueError(
            "array sizes of {} eigenvectors and {} eigenvalues do not match".format(
                eigenvec.shape, eigenval.shape
            )
        )

    # threshold formula taken from pinv2's implementation of numpy/scipy
    thresh = np.abs(eigenval).max() * max(eigenval.shape) * np.finfo(eigenval.dtype).eps
    stable_eig = np.logical_not(np.isclose(eigenval, 0.0, atol=thresh))

    if np.any(eigenval <= -thresh):
        raise ValueError(
            "Some eigenvalues of a PSD matrix are negative, this should never happen. "
            "Minimum eig: {}".format(np.min(eigenval))
        )

    m = sum(stable_eig)
    eigenvec_thin = eigenvec[:, stable_eig]
    eigenval_thin = eigenval[stable_eig]
    if eigenvec_thin.shape != (n, m) or eigenval_thin.shape != (m,):
        raise ValueError(
            "array sizes of {} eigenvectors and {} eigenvalues do not match".format(
                eigenvec.shape, eigenval.shape
            )
        )

    return eigenvec_thin, eigenval_thin


def stable_invert_root(eigenvec, eigenval):
    """Given eigendecomposition of a PSD matrix, compute a representation of the pseudo-inverse square root
    of the matrix using numerically stable operations. In particular, eigenvalues which are near-zero
    and the associated eigenvectors are dropped from the pseudo-inverse.
    """
    eigenvec_thin, eigenval_thin = stable_filter(eigenvec, eigenval)

    eigenval_thin_inv_root = (1 / np.sqrt(eigenval_thin)).reshape(-1, 1)

    return eigenvec_thin, eigenval_thin_inv_root


def get_progress_bar(total=-1, disable=False, **kwargs):
    """Helper function to get a tqdm progress bar (or a simple fallback otherwise)"""

    class ProgBar(object):
        def __init__(self, total=-1, disable=False, **kwargs):
            self.disable = disable
            self.t = 0
            self.total = total
            self.debug_string = ""

        def __enter__(self):
            return self

        def __exit__(self, *args, **kwargs):
            pass

        def set_postfix(self, **kwargs):
            self.debug_string = ""
            for arg in kwargs:
                self.debug_string += "{}={} ".format(arg, kwargs[arg])

        def update(self):
            if not self.disable:
                self.t += 1
                print_str = "{}".format(self.t)

                if self.total > 0:
                    print_str += "/{}".format(self.total)

                print_str += ": {}".format(self.debug_string)

                if len(print_str) < 80:
                    print_str = print_str + " " * (80 - len(print_str))

                print(print_str, end="\r", flush=True)

            if self.t == self.total:
                print("")

    try:
        from tqdm import tqdm

        progress_bar = tqdm(total=total, disable=disable)
    except ImportError:
        progress_bar = ProgBar(total=total, disable=disable)

    return progress_bar


def eval_kernel_diagonal(eval_L, X):
    """Helper function to evaluate a likelihood function on a set of points (i.e. compute the diagonal of the L matrix)"""
    diag_eval = getattr(eval_L, "diag", None)
    if callable(diag_eval):
        return diag_eval(X)

    # inspired by sklearn.gaussian_process.kernels.PairwiseKernel
    return np.apply_along_axis(eval_L, axis=1, arr=X).ravel()


def kernel_linear(x, y=None):
    x = np.atleast_2d(x)
    y = x if y is None else np.atleast_2d(y)
    return x.dot(y.T)


def kernel_polynomial(x, y=None, p=2):
    kernel_xy = kernel_linear(x, y)
    np.power(kernel_xy, p, out=kernel_xy)
    return kernel_xy


def kernel_minimum(x, y=None):
    check_in_01(x)
    if y is None:
        y = x
    else:
        check_in_01(y)
    return np.minimum.outer(x.ravel(), y.ravel())


def elementary_symmetric_polynomials(k, x):
    """Evaluate the `elementary symmetric polynomials <https://en.wikipedia.org/wiki/Elementary_symmetric_polynomial>`_ :math:`[e_i(x_1, \\dots, x_m)]_{i=0, m=1}^{k, n}`.

    :param x:
        Points at which the elementary symmetric polynomials will be evaluated
    :type x:
        array_like

    :param k:
        Maximum degree of the elementary symmetric polynomials to be evaluated
    :type k:
        int

    :return:
        Matrix of size :math:`(k+1, n)` containing the evaluation of the elementary symmetric polynomials :math:`[e_i(x_1, \\dots, x_m)]_{i=0, m=1}^{k, n}`
    :rtype:
        array_like

    .. seealso::

        - :cite:`KuTa12` Algorithm 7
        - `Wikipedia <https://en.wikipedia.org/wiki/Elementary_symmetric_polynomial>`_
    """

    # Initialize output array
    n = x.size
    E = np.zeros((k + 1, n + 1), dtype=float)
    E[0, :] = 1.0

    # Recursive evaluation
    for i in range(1, k + 1):
        for m in range(0, n):
            E[i, m + 1] = E[i, m] + x[m] * E[i - 1, m]

    return E
