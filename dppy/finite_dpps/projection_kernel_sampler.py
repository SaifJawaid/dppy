import numpy as np
from dppy.utils import check_random_state, inner1d


def projection_kernel_sampler(dpp, random_state=None, **params):
    assert dpp.projection

    size = params.get("size")
    if dpp.kernel_type == "likelihood":
        if not size:
            raise ValueError(
                "size !> 0. projection_kernel_sampler only applies to k-DPP(L) with orthogonal projection L kernel."
            )
        dpp.compute_L()
        kernel = dpp.L
    else:  # dpp.kernel_type == "correlation":
        dpp.compute_K()
        kernel = dpp.K

    mode = params.get("mode")
    if dpp.hermitian:
        sampler = select_orthogonal_projection_kernel_sampler(mode)
    else:
        sampler = select_generic_projection_kernel_sampler(mode)

    return sampler(kernel, size=size, random_state=random_state)


def select_generic_projection_kernel_sampler(mode):
    """Select a sampler for projection DPP define via its correlation kernel K satisfying :math:`K^2 = K`.

    - :func:`projection_kernel_sampler_Schur <projection_kernel_sampler_Schur>`
    """
    samplers = {
        "Schur": projection_kernel_sampler_Schur,
    }
    default = samplers["Schur"]
    return samplers.get(mode, default)


def select_orthogonal_projection_kernel_sampler(mode):
    """Select a sampler for projection DPP define via its correlation kernel

    - :func:`orthogonal_projection_kernel_sampler_GS <orthogonal_projection_kernel_sampler_GS>`
    - :func:`projection_kernel_sampler_Schur <projection_kernel_sampler_Schur>`
    - :func:`orthogonal_projection_kernel_sampler_Chol <orthogonal_projection_kernel_sampler_Chol>`
    """
    samplers = {
        "GS": orthogonal_projection_kernel_sampler_GS,
        "Chol": orthogonal_projection_kernel_sampler_Chol,
        "Schur": projection_kernel_sampler_Schur,
    }
    default = samplers["GS"]
    return samplers.get(mode, default)


def orthogonal_projection_kernel_sampler_Chol(K, size=None, random_state=None):
    """Generate an exact sample from :math:`\\operatorname{DPP}(K)`, or :math:`\\operatorname{k-DPP}(K)` with :math:`k=` ``size`` (if ``size`` is provided), where :math:`K` is an orthogonal projection `kernel`.

    The chain rule is applied by performing Cholesky updates following :cite:`Pou19` Algorithm 3.

    :param K:
        Orthogonal projection kernel.
    :type K:
        array_like

    :param size:
        Size of the output sample (if ``size`` is provided), otherwise :math:`k=\\operatorname{trace}(K)=\\operatorname{rank}(K)`.
    :type size:
        int

    :return:
        An exact sample from the corresponding :math:`\\operatorname{DPP}(K)` or :math:`\\operatorname{k-DPP}(K)`.
    :rtype:
        list

    .. caution::

        The current implementation is an attempt of @guilgautier to reproduce the original C implementation of `catamari <https://gitlab.com/hodge_star/catamari>`_

    .. seealso::

        - :cite:`Pou19` Algorithm 3 and :ref:`catamari code <https://gitlab.com/hodge_star/catamari/blob/38718a1ea34872fb6567e019ece91fbeb5af5be1/include/catamari/dense_dpp/elementary_hermitian_dpp-impl.hpp#L37>`_ for the Hermitian swap routine.
        - :func:`orthogonal_projection_kernel_sampler_GS <orthogonal_projection_kernel_sampler_GS>`
        - :func:`projection_kernel_sampler_Schur <projection_kernel_sampler_Schur>`
    """

    rng = check_random_state(random_state)

    rank = np.rint(np.trace(K)).astype(int)
    if size is None:  # full projection DPP else k-DPP with k = size
        size = rank
    assert size <= rank

    A = K.copy()
    d = np.copy(A.diagonal().real)

    N = len(A)
    ground_set = np.arange(N)

    for j in range(size):

        # Sample from pivot index and permute
        t = rng.choice(range(j, N), p=np.abs(d[j:]) / (rank - j))

        # Hermitian swap of indices j and t of A
        # bottom swap
        j_t = [j, t]
        t_j = j_t[::-1]
        T1 = slice(t + 1, N)
        A[T1, j_t] = A[T1, t_j]
        # inner swap
        J1 = slice(j + 1, t)
        tmp = A[J1, j].copy()
        np.conj(A[t, J1], out=A[J1, j])
        np.conj(tmp, out=A[t, J1])
        # corner swap
        A[t, j] = A[t, j].conj()
        # diagonal swap
        A[j_t, j_t] = A[t_j, t_j].real
        # left swap
        A[j_t, :j] = A[t_j, :j]

        # Swap positions j and t
        ground_set[j_t] = ground_set[t_j]
        d[j_t] = d[t_j]

        A[j, j] = np.sqrt(d[j])

        if j == size - 1:
            break

        # Form new column and update diagonal
        J2 = slice(j + 1, N)
        A[J2, j] -= A[J2, :j].dot(A[j, :j].conj())
        A[J2, j] /= A[j, j]
        if np.iscomplexobj(A):
            d[J2] -= A[J2, j].real ** 2 + A[J2, j].imag ** 2
        else:
            d[J2] -= A[J2, j] ** 2

    sample = ground_set[:size].tolist()
    # log_likelihood = np.sum(np.log(np.diagonal(A[:size, :size]).real))
    return sample  # , log_likelihood


def orthogonal_projection_kernel_sampler_GS(K, size=None, random_state=None):
    """Generate an exact sample from :math:`\\operatorname{DPP}(K)`, or :math:`\\operatorname{k-DPP}(K)` with :math:`k=` ``size`` (if ``size`` is provided), where :math:`K` is an orthogonal projection `kernel`.

    Chain rule is applied by performing sequential Gram-Schmidt orthogonalization or equivalently Cholesky decomposition updates of :math:`K`.

    :param K:
        Orthogonal projection kernel.
    :type K:
        array_like

    :param size:
        Size of the output sample (if ``size`` is provided), otherwise :math:`k=\\operatorname{trace}(K)=\\operatorname{rank}(K)`.
    :type size:
        int

    :return:
        An exact sample from the corresponding :math:`\\operatorname{DPP}(K)` or :math:`\\operatorname{k-DPP}(K)`.
    :rtype:
        list

    .. seealso::

        - :cite:`TrBaAm18` Algorithm 3, :cite:`Gil14` Algorithm 2
        - :func:`projection_kernel_sampler_Schur <projection_kernel_sampler_Schur>`
        - :func:`orthogonal_projection_kernel_sampler_Chol <orthogonal_projection_kernel_sampler_Chol>`
    """

    rng = check_random_state(random_state)

    N = len(K)  # ground set size
    rank = np.rint(np.trace(K)).astype(int)  # rank(K) = Tr(K)
    if size is None:  # full projection DPP else k-DPP with k = size
        size = rank
    assert size <= rank

    ground_set = np.arange(len(K))
    rem = np.full_like(ground_set, fill_value=True, dtype=bool)
    sample = np.zeros(size, dtype=int)

    norm_2 = np.copy(K.diagonal().real)
    c = np.zeros_like(K, shape=(N, size))

    for it in range(size):
        j = rng.choice(ground_set[rem], p=np.abs(norm_2[rem]) / (rank - it))
        sample[it] = j
        rem[j] = False
        if it == size - 1:
            break

        c[rem, it] = K[rem, j] - c[rem, :it].dot(c[j, :it])
        c[rem, it] /= np.sqrt(norm_2[j])

        norm_2[rem] -= c[rem, it] ** 2

    # log_likelihood = np.sum(np.log(norm_2[sample]))
    return sample.tolist()  # , log_likelihood


def projection_kernel_sampler_Schur(K, size=None, random_state=None):
    """Generate an exact sample from :math:`\\operatorname{DPP}(K)`, or :math:`\\operatorname{k-DPP}(K)` with :math:`k=` ``size`` (if ``size`` is provided), where :math:`K` is a projection kernel (not necessarily orthogonal).

    The chain rule is applied by computing Schur complements explicitely, using Woodbury's formula.

    :param K:
        Projection kernel.
    :type K:
        array_like
    :param size:
        Size of the output sample (if ``size`` is provided), otherwise :math:`k=\\operatorname{trace}(K)=\\operatorname{rank}(K)`.
    :type size:
        int

    :return:
        An exact sample from the corresponding :math:`\\operatorname{DPP}(K)` or :math:`\\operatorname{k-DPP}(K)`.

    :return:
        If ``size`` is not provided (None),
            A sample from :math:`\\operatorname{DPP}(K)`.
        If ``size`` is provided,
            A sample from :math:`\\operatorname{k-DPP}(K)`.
    :rtype:
        array_like

    .. seealso::
        - :func:`orthogonal_projection_kernel_sampler_GS <orthogonal_projection_kernel_sampler_GS>`
        - :func:`orthogonal_projection_kernel_sampler_Chol <orthogonal_projection_kernel_sampler_Chol>`
    """

    rng = check_random_state(random_state)

    rank = np.rint(np.trace(K)).astype(int)  # rank(K) = Tr(K)
    if size is None:  # full projection DPP else k-DPP with k = size
        size = rank
    assert size <= rank

    ground_set = np.arange(len(K))
    rem = np.full_like(ground_set, fill_value=True, dtype=bool)
    sample = np.zeros(size, dtype=int)

    schur = np.copy(K.diagonal().real)
    K1 = np.zeros_like(K, shape=(size, size))  # K^-1

    for it in range(size):
        j = rng.choice(ground_set[rem], p=np.abs(schur[rem]) / (rank - it))
        sample[it] = j
        rem[j] = False

        # Update Schur complements K_ii - K_iY (K_Y)^-1 K_Yi
        # 1. Use Woodbury identity to compute K[Y+j,Y+j]^-1 from K[Y,Y]^-1
        if it == 0:
            K1[0, 0] = 1.0 / K[j, j]

        elif it == 1:
            i = sample[0]
            K1[:2, :2] = np.array([[K[j, j], -K[j, i]], [-K[j, i], K[i, i]]])
            K1[:2, :2] /= K[i, i] * K[j, j] - K[j, i] ** 2

        elif it < size - 1:
            # Compute K[Y+j,Y+j]^-1 from K[Y,Y]^-1, using Woodbury
            Y = slice(0, it)
            tmp1 = K1[Y, Y].dot(K[sample[Y], j])  # K1_Y K_Yj
            # K_jj - K_jY K1_Y K_Yj
            schur_j = K[j, j] - K[j, sample[Y]].dot(tmp1)
            tmp2 = K[j, sample[Y]].dot(K1[Y, Y]) / schur_j  # K_jY K1_YY / schur

            # K1[Y,Y] + K1[Y,Y] K[Y,j] K[j,Y] K1[Y,Y] / schur
            K1[Y, Y] += np.outer(tmp1, tmp2)
            K1[Y, it] = -tmp1 / schur_j  # - K1[Y,Y] K[Y,j] / schur
            K1[it, Y] = -tmp2  # - K[j,Y] K1[Y,Y] / schur
            K1[it, it] = 1.0 / schur_j

        else:  # it == size-1
            break  # no need to update for nothing

        # 2. Update Schur complements
        # K_ii - K_iY (K_Y)^-1 K_Yi for Y <- Y+j
        Y = slice(0, it + 1)
        K_iY = K[np.ix_(rem, sample[Y])]
        K_Yi = K[np.ix_(sample[Y], rem)]
        schur[rem] = K[rem, rem] - inner1d(K_iY.dot(K1[Y, Y]), K_Yi.T, axis=1)

    # log_likelihood = np.sum(np.log(schur[sample]))
    return sample.tolist()  # , log_likelihood