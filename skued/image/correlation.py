# -*- coding: utf-8 -*-
"""
Image correlation and related functions
=======================================
"""
from functools import partial

import numpy as np
from scipy.fftpack import next_fast_len, fftn, ifftn
from scipy.signal import fftconvolve

from ..array_utils import mirror
from ..utils import deprecated

FFTOPS = {}
try:
    from pyfftw.interfaces.numpy_fft import rfft2, irfft2
    FFTOPS['threads'] = 2
except ImportError:
    from numpy.fft import rfft2, irfft2


EPS = np.finfo(np.float).eps

def xcorr(arr1, arr2, mode = 'full', axes = None):
    """ 
    Cross-correlation between two N-dimensional arrays.
    Support for cross-correlation along specific axes as well.

    Parameters
    ----------
    arr1 : `~numpy.ndarray`
        First array. 
    arr2 : `~numpy.ndarray`
        Second array. It should have the same number of dimensions
        as ``arr1``.
    mode : {'full', 'same'}, optional
        'full':
            By default, mode is 'full'.  This returns the convolution
            at each point of overlap, with an output shape of (N+M-1,M+N-1). At
            the end-points of the convolution, the signals do not overlap
            completely, and boundary effects may be seen.
        'same':
            Mode 'same' returns output of length ``max(M, N)``. Boundary
            effects are still visible.
    axes : None or tuple of ints, optional
        Axes over which to compute the cross-correlation. If None,
        cross-correlation is computed over all axes.

    Returns
    -------
    out : `~numpy.ndarray`
        Cross-correlation. If ``arr1`` or ``arr2`` is complex, then
        ``out`` will be complex as well; otherwise, ``out`` will be
        of float type.

    Notes
    -----
    If ``pyfftw`` is installed, its routines will be preferred.
    
    Raises
    ------
    ValueError : mode argument is invalid
    ValueError : if either ``arr1`` or ``arr2`` is complex.

    See Also
    --------
    mnxc2 : masked normalized cross-correlation between images.
    """
    if mode not in {'full', 'same'}:
        raise ValueError('Unexpected cross-correlation mode {}'.format(mode))
    
    if axes is None:
        axes = tuple(range(arr1.ndim))

    arr1, arr2 = np.asarray(arr1), np.asarray(arr2)

    # Determine final size along transformation axes
    # To speed up FFT, shape of Fourier transform might be slightly larger
    # then slice back before returning
    s1 = tuple(arr1.shape[ax] for ax in axes)
    s2 = tuple(arr2.shape[ax] for ax in axes)
    final_shape = tuple( ax1 + ax2 - 1 for ax1, ax2 in zip(s1, s2))
    fast_shape = tuple(map(next_fast_len, final_shape))
    final_slice = tuple([slice(0, int(sz)) for sz in final_shape])

    F1 = fftn(arr1, shape = fast_shape, axes = axes)
    F2 = fftn(np.conj(mirror(arr2, axes = axes)), shape = fast_shape, axes = axes)
    xc = ifftn(F1 * F2)[final_slice]

    if mode == 'same':
        return _centered(xc, arr1.shape, axes = axes)
    else:
        return xc

@deprecated('Use mnxc instead.')
def mnxc2(arr1, arr2, m1 = None, m2 = None, mode = 'full', axes = (0, 1), out = None, overlap_ratio = 3/10):
    """
    [DEPRECATED] Masked normalized cross-correlation (MNXC) between two images or stacks of images.

    Parameters
    ----------
    arr1 : `~numpy.ndarray`, shape (M,N)
        Reference, or 'fixed-image' in the language of _[PADF]. This array can also
        be a stack of images; in this case, the cross-correlation
        is computed along the two axes passed to ``axes``.
    arr2 : `~numpy.ndarray`, shape (M,N)
        Moving image. This array can also be a stack of images; 
        in this case, the cross-correlation is computed along the 
        two axes passed to ``axes``.
    m1 : `~numpy.ndarray`, shape (M,N) or None, optional
        Mask of `arr1`. The mask should evaluate to `True`
        (or 1) on invalid pixels. If None (default), no mask
        is used.
    m2 : `~numpy.ndarray`, shape (M,N) or None, optional
        Mask of `arr2`. The mask should evaluate to `True`
        (or 1) on invalid pixels. If None (default), `m2` is 
        taken to be the same as `m1`.	
    mode : {'full', 'same'}, optional
        'full':
            By default, mode is 'full'.  This returns the convolution
            at each point of overlap, with an output shape of (N+M-1,M+N-1). At
            the end-points of the convolution, the signals do not overlap
            completely, and boundary effects may be seen.
        'same':
            Mode 'same' returns output of length ``max(M, N)``. Boundary
            effects are still visible.
    axes : 2-tuple of ints, optional
        Axes along which to compute the cross-correlation.
    out : `~numpy.ndarray` or None, optional
        If not None, the results will be stored in `out`. If None, a new array
        is returned.
    overlap_ratio : float, optional
        Maximum allowed overlap ratio between masks. The correlation at pixels with overlap ratio higher
        than this threshold will be zeroed.

        .. versionadded:: 1.0.2
        
    Returns
    -------
    out : `~numpy.ndarray`
        Masked, normalized cross-correlation. If images are real-valued, then `out` will be
        real-valued as well. For complex input, `out` will be complex as well.
    
    See Also
    --------
    xcorr : cross-correlation between two N-dimensional arrays.
        
    References
    ----------
    .. [PADF] Dirk Padfield. Masked Object Registration in the Fourier Domain. 
        IEEE Transactions on Image Processing, vol.21(5), pp. 2706-2718 (2012). 
    """
    if len(axes) != 2:
        raise ValueError('`axes` parameter must be 2-tuple, not `{}`'.format(axes))

    m1 = np.zeros_like(arr1, dtype = np.bool) if (m1 is None) else np.array(m1, dtype = np.bool)
    m2 = np.zeros_like(arr2, dtype = np.bool) if (m2 is None) else np.array(m2, dtype = np.bool)

    return np.real(mnxc(arr1, arr2, np.logical_not(m1), np.logical_not(m2), mode = mode, axes = axes, overlap_ratio = overlap_ratio))

def mnxc(arr1, arr2, m1, m2, mode='full', axes=(-2, -1), overlap_ratio=3 / 10):
    """
    N-dimensional masked normalized cross-correlation (MNXC) between arrays.

    .. versionadded:: 1.0.2

    Parameters
    ----------
    arr1 : ndarray
        First array.
    arr2 : ndarray
        Seconds array. The dimensions of `arr2` along axes that are not
        transformed should be equal to that of `arr1`.
    m1 : ndarray
        Mask of `arr1`. The mask should evaluate to `True`
        (or 1) on valid pixels. `m1` should have the same shape as `arr1`.
    m2 : ndarray
        Mask of `arr2`. The mask should evaluate to `True`
        (or 1) on valid pixels. `m2` should have the same shape as `arr2`.
    mode : {'full', 'same'}, optional
        'full':
            This returns the convolution at each point of overlap. At
            the end-points of the convolution, the signals do not overlap
            completely, and boundary effects may be seen.
        'same':
            The output is the same size as `arr1`, centered with respect
            to the `‘full’` output. Boundary effects are less prominent.
    axes : tuple of ints, optional
        Axes along which to compute the cross-correlation.
    overlap_ratio : float, optional
        Maximum allowed overlap ratio between masks. The correlation at pixels
        with overlap ratio higher than this threshold will be zeroed.

    Returns
    -------
    out : ndarray
        Masked normalized cross-correlation.

    Raises
    ------
    ValueError : if correlation `mode` is not valid, or array dimensions along
        non-transformation axes are not equal.

    References
    ----------
    .. [1] Dirk Padfield. Masked Object Registration in the Fourier Domain.
        IEEE Transactions on Image Processing, vol.21(5), pp. 2706-2718 (2012).
    """
    if mode not in {'full', 'same'}:
        raise ValueError("Correlation mode {} is not valid.".format(mode))

    fixed_image = np.array(arr1, dtype=np.float)
    fixed_mask = np.array(m1, dtype=np.bool)
    moving_image = np.array(arr2, dtype=np.float)
    moving_mask = np.array(m2, dtype=np.bool)
    eps = np.finfo(np.float).eps

    # Array dimensions along non-transformation axes should be equal.
    all_axes = set(range(fixed_image.ndim))
    for axis in (all_axes - set(axes)):
        if fixed_image.shape[axis] != moving_image.shape[axis]:
            raise ValueError(
                'Array shapes along non-transformation axes should be \
                    equal, but dimensions along axis {a} not'.format(a=axis))

    # Determine final size along transformation axes
    # Note that it might be faster to conmpute Fourier transform in a slightly
    # larger shape (`fast_shape`) Then, after all fourier transforms are done,
    # we slice back to`final_shape` using `final_slice`.
    final_shape = list(arr1.shape)
    for axis in axes:
        final_shape[axis] = fixed_image.shape[axis] + \
            moving_image.shape[axis] - 1
    final_shape = tuple(final_shape)
    final_slice = tuple([slice(0, int(sz)) for sz in final_shape])

    # Extent transform axes to the next fast length (i.e. multiple of 3, 5, or 7)
    fast_shape = tuple([next_fast_len(final_shape[ax]) for ax in axes])

    # We use numpy's fft because it allows to leave transform axes unchanged
    # which is not possible with SciPy's fftn/ifftn
    # E.g. arr shape (2,3,7), transform along axes (0, 1) with shape (4,4)
    # results in arr_fft shape (4,4, 7)
    fft = partial(np.fft.fftn, s=fast_shape, axes=axes)
    ifft = partial(np.fft.ifftn, s=fast_shape, axes=axes)

    fixed_image[np.logical_not(fixed_mask)] = 0.0
    moving_image[np.logical_not(moving_mask)] = 0.0

    # N-dimensional analog to rotation by 180deg is flip over all relevant axes
    # See [1] for discussion.
    rotated_moving_image = _flip(moving_image, axes=axes)
    rotated_moving_mask = _flip(moving_mask, axes=axes)

    fixed_fft = fft(fixed_image)
    rotated_moving_fft = fft(rotated_moving_image)
    fixed_mask_fft = fft(fixed_mask)
    rotated_moving_mask_fft = fft(rotated_moving_mask)

    # Calculate overlap of masks at every point in the convolution
    # Locations with high overlap should not be taken into account.
    number_overlap_masked_px = np.real(
        ifft(rotated_moving_mask_fft * fixed_mask_fft))
    number_overlap_masked_px[:] = np.round(number_overlap_masked_px)
    number_overlap_masked_px[:] = np.fmax(number_overlap_masked_px, eps)
    masked_correlated_fixed_fft = ifft(rotated_moving_mask_fft * fixed_fft)
    masked_correlated_rotated_moving_fft = ifft(
        fixed_mask_fft * rotated_moving_fft)

    numerator = ifft(rotated_moving_fft * fixed_fft)
    numerator -= masked_correlated_fixed_fft * \
        masked_correlated_rotated_moving_fft / number_overlap_masked_px

    fixed_squared_fft = fft(np.square(fixed_image))
    fixed_denom = ifft(rotated_moving_mask_fft * fixed_squared_fft)
    fixed_denom -= np.square(masked_correlated_fixed_fft) / \
        number_overlap_masked_px
    fixed_denom[:] = np.fmax(fixed_denom, 0.0)

    rotated_moving_squared_fft = fft(np.square(rotated_moving_image))
    moving_denom = ifft(fixed_mask_fft * rotated_moving_squared_fft)
    moving_denom -= np.square(masked_correlated_rotated_moving_fft) / \
        number_overlap_masked_px
    moving_denom[:] = np.fmax(moving_denom, 0.0)

    denom = np.sqrt(fixed_denom * moving_denom)

    # Slice back to expected convolution shape
    numerator = numerator[final_slice]
    denom = denom[final_slice]
    number_overlap_masked_px = number_overlap_masked_px[final_slice]

    if mode == 'same':
        _centering = partial(_centered,
                             newshape=fixed_image.shape, axes=axes)
        denom = _centering(denom)
        numerator = _centering(numerator)
        number_overlap_masked_px = _centering(number_overlap_masked_px)

    # Pixels where `denom` is very small will introduce large
    # numbers after division To get around this problem,
    # we zero-out problematic pixels.
    tol = 1e3 * eps * np.max(np.abs(denom), axis=axes, keepdims=True)
    nonzero_indices = denom > tol

    out = np.zeros_like(denom)
    out[nonzero_indices] = numerator[nonzero_indices] / denom[nonzero_indices]
    np.clip(out, a_min=-1, a_max=1, out=out)

    # Apply overlap ratio threshold
    number_px_threshold = overlap_ratio * np.max(number_overlap_masked_px,
                                                 axis=axes, keepdims=True)
    out[number_overlap_masked_px < number_px_threshold] = 0.0

    return out

def _centered(arr, newshape, axes):
    """ Return the center `newshape` portion of `arr`, leaving axes not
    in `axes` untouched. """
    newshape = np.asarray(newshape)
    currshape = np.array(arr.shape)

    slices = [slice(None, None)] * arr.ndim

    for ax in axes:
        startind = (currshape[ax] - newshape[ax]) // 2
        endind = startind + newshape[ax]
        slices[ax] = slice(startind, endind)

    return arr[tuple(slices)]

def _flip(arr, axes=None):
    """ Reverse array over many axes. Generalization of arr[::-1] for many
    dimensions. If `axes` is `None`, flip along all axes. """
    if axes is None:
        axes = tuple(range(arr.ndim))
    
    # Note that np.flip requires numpy>1.12
    for axis in axes:
        arr = np.flip(arr, axis)

    return arr