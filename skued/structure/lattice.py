# -*- coding: utf-8 -*-
from functools import partial
from itertools import repeat
from math import cos, isclose, radians, sin, sqrt, tan

import numpy as np
from numpy.linalg import norm

from npstreams import cyclic

from .. import change_basis_mesh, transform
from .base import Base

e1, e2, e3 = np.eye(3) # Euclidian basis

# TODO: Introduce conventions on ordering a, b, c and angles
#       based on http://atztogo.github.io/spglib/definition.html
def lattice_vectors_from_parameters(a, b, c, alpha, beta, gamma):
    """ 
    Returns the lattice vectors from three lengths and angles.
    
    Parameters
    ----------
    a, b, c : float
        Lengths of lattice vectors [Angstroms]
    alpha, beta, gamma : float
        Angles of lattice vectors [degrees]. 
    
    Returns
    -------
    a1, a2 a3 : `~numpy.ndarray`, shape (3,)
        Lattice vectors
    """
    alpha, beta, gamma = map(radians, (alpha, beta, gamma))

    a1 = a*e1
    a2 = b * (cos(gamma)*e1 + sin(gamma)*e2)

    # Determine a3 = c1 *e1 + c2 * e2 + c3 * e3
    c1 = cos(beta)
    c2 = cos(alpha)/sin(gamma) - cos(beta)/tan(gamma)
    try:
        c3 = sqrt(1 - c1**2 - c2**2)    #
    except ValueError:
        raise ValueError('Invalid lattice parameters')

    return a1, a2, c*(c1*e1 + c2*e2 + c3*e3)    

class Lattice(Base):
    """
    Container class for lattice information and manipulations.

    Instances can also be create from the standard 'three lengths and angles'
    parameters via ``Lattice.from_parameters``:

    Parameters
    ----------
    lattice_vectors: iterable of `~numpy.ndarray`, shape (3,), optional
        Lattice vectors. Default is a cartesian lattice.
    """
    def __init__(self, lattice_vectors, **kwargs):
        a1, a2, a3 = lattice_vectors
        self.a1 = np.asarray(a1, dtype = np.float) 
        self.a2 = np.asarray(a2, dtype = np.float) 
        self.a3 = np.asarray(a3, dtype = np.float)
        super().__init__(**kwargs)
    
    def __repr__(self):
        return '< Lattice object. a1 : {} \n, a2 : {} \n, a3 : {}>'.format(self.a1, self.a2, self.a3)

    def __hash__(self):
        return hash(self.lattice_parameters) | super().__hash__()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return np.allclose(self.lattice_vectors, other.lattice_vectors) and super().__eq__(other)
        return NotImplemented

    @classmethod
    def from_parameters(cls, a, b, c, alpha, beta, gamma):
        """ 
        Create a lattice instance from three lengths and angles.

        Parameters
        ----------
        a, b, c : floats
            Lattice vectors lengths [Angs]
        alpha, beta, gamma : floats
            Angles between lattice vectors [deg]
        """
        return cls(lattice_vectors = lattice_vectors_from_parameters(a, b, c, alpha, beta, gamma))
    
    @property
    def lattice_parameters(self):
        """ Lattice parameters as three lengths [:math:`\AA`] and three angles [degrees]. """
        a, b, c = norm(self.a1), norm(self.a2), norm(self.a3)
        alpha = np.arccos(np.vdot(self.a2, self.a3)/(b*c))
        beta = np.arccos(np.vdot(self.a1, self.a3)/(a*c))
        gamma = np.arccos(np.vdot(self.a1, self.a2)/(a*b))
        return a, b, c, np.rad2deg(alpha), np.rad2deg(beta), np.rad2deg(gamma)

    @property
    def lattice_system(self):
        """ Crystal family, one of {'triclinic', 'monoclinic', 'orthorhombic', 
        'tetragonal', 'cubic', 'hexagonal', 'rhombohedral', 'cubic'} """
        return lattice_system(self, atol = 5e-2)
    
    @property
    def volume(self):
        """ Lattice cell volume Angtroms cubed """
        return np.dot(self.a1, np.cross(self.a2, self.a3))
    
    @property
    def lattice_vectors(self):
        """ Iterable of lattice vectors """
        return self.a1, self.a2, self.a3
    
    @lattice_vectors.setter
    def lattice_vectors(self, vectors):
        self.a1, self.a2, self.a3 = vectors
    
    @property
    def reciprocal(self):
        """ Reciprocal lattice """
        return Lattice(lattice_vectors = self.reciprocal_vectors)

    @property
    def reciprocal_vectors(self):
        """
        Reciprocal lattice vectors, defined as:

        .. math::

            b_i = 2 \pi \\frac{a_j \\times a_k}{v}
        
        For :math:`v` the unit cell volume.
        """
        cell_volume = self.volume
        b1 = 2*np.pi*np.cross(self.a2, self.a3)/cell_volume
        b2 = 2*np.pi*np.cross(self.a3, self.a1)/cell_volume
        b3 = 2*np.pi*np.cross(self.a1, self.a2)/cell_volume
        return b1, b2, b3

    @property
    def periodicity(self):
        """ Crystal periodicity in x, y and z direction from the lattice constants.
        This is effectively a bounding cube for the unit cell, which is itself a unit cell. """
        e1, e2, e3 = np.eye(3)
        per_x = sum( (abs(np.vdot(e1,a)) for a in self.lattice_vectors) )
        per_y = sum( (abs(np.vdot(e2,a)) for a in self.lattice_vectors) )
        per_z = sum( (abs(np.vdot(e3,a)) for a in self.lattice_vectors) )
        return per_x, per_y, per_z

    def scattering_vector(self, h, k, l):
        """
        Scattering vector from Miller indices.

        Parameters
        ----------
        h, k, l : array_like
            Miller indices. 

        Returns
        -------
        Gx, Gy, Gz : `~numpy.ndarray`
            Components of the scattering vectors, of the same shape 
            as ``h``, ``k``, and ``l``.
        """
        h, k, l = np.atleast_1d(h, k, l)
        return change_basis_mesh(h, k, l, basis1 = self.reciprocal_vectors, basis2 = np.eye(3))

    def miller_indices(self, Gx, Gy, Gz):
        """
        Miller indices from scattering vector components.

        Parameters
        ----------
        Gx, Gy, Gz : `~numpy.ndarray`
            Scattering vector components, in :math:`A^{-1}`.
        
        Returns
        -------
        h, k, l : `~numpy.ndarray`
            Miller indices.
        """
        Gx, Gy, Gz = np.atleast_1d(Gx, Gy, Gz)
        return change_basis_mesh(Gx, Gy, Gz, basis1 = np.eye(3), basis2 = self.reciprocal_vectors)
    
    @staticmethod
    def frac_mesh(*xi, indexing = 'xy'):
        """
        Coordinate arrays for fractional coordinates.

        Parameters
        ----------
        x1, x2, x3 : `~numpy.ndarray`, shape (N,)
            1d coordinate vectors. If only ``x1`` is provided, it is assumed
            that ``x1 = x2 = x3``. Otherwise, three coordinate vectors are expected.
        indexing : str, {'ij', 'xy'}
            Cartesian (‘xy’, default) or matrix (‘ij’) indexing of output.
        
        Returns
        -------
        out1, out2, out3 : `~numpy.ndarray`
            Fractional coordinate arrays.
        
        Raises
        ------
        ValueError : if number of input vectors is neither 1 nor 3.
        
        See Also
        --------
        numpy.meshgrid : Coordinate arrays from coordinate vectors
        Lattice.mesh : Real-space coordinate arrays from fractional coordinate vectors
        """
        if len(xi) == 1:
            xi = tuple(repeat(xi[0], times = 3))
        elif len(xi) != 3:
            raise ValueError('1 or 3 coordinate arrays are required, but received {}'.format(len(xi)))
        
        return np.meshgrid(*xi, indexing = indexing)

    def mesh(self, *xi, indexing = 'xy'):   
        """
        Real-space coordinate arrays from fractional coordinate vectors.

        Parameters
        ----------
        x1, x2, x3 : `~numpy.ndarray`, shape (N,)
            1d coordinate vectors in fractional coordinates. 
            If only ``x1`` is provided, it is assumed that ``x1 = x2 = x3``. 
            Otherwise, three coordinate vectors are expected.
        indexing : str, {'ij', 'xy'}
            Cartesian (‘xy’, default) or matrix (‘ij’) indexing of output.
        
        Returns
        -------
        out1, out2, out3 : `~numpy.ndarray`
            Real-space oordinate arrays.
        
        Raises
        ------
        ValueError : if number of input vectors is neither 1 nor 3.
        
        See Also
        --------
        numpy.meshgrid : Coordinate arrays from coordinate vectors
        Lattice.frac_mesh : Coordinate arrays for fractional coordinates
        """ 
        return change_basis_mesh(*self.frac_mesh(*xi, indexing = indexing),
                                 basis1 = np.array(self.lattice_vectors),
                                 basis2 = np.eye(3) )

    def transform(self, *matrices):
        """
        Transforms the real space coordinates according to a matrix.
        
        Parameters
        ----------
        matrices : ndarrays, shape {(3,3), (4,4)}
            Transformation matrices.
        """
        # Transform lattice vectors 
        for matrix in matrices:
            self.a1 = transform(matrix, self.a1)
            self.a2 = transform(matrix, self.a2)
            self.a3 = transform(matrix, self.a3)

# TODO: also determine body-centered, primitive, face-centered, etc.
#       https://en.wikipedia.org/wiki/Bravais_lattice#Bravais_lattices_in_3_dimensions
def lattice_system(lattice, atol = 1e-2):
    """
    Determine the lattice system. All cyclic permutations are checked,
    so that no convention on ordering of lattice parameters is assumed.

    Parameters
    ----------
    lattice : Lattice
        Lattice instance or subclass.
    atol : float, optional
        Absolute tolerance (in Angstroms)
    
    Returns
    -------
    system : str, {'triclinic', 'monoclinic', 'orthorhombic', 
                   'tetragonal', 'cubic', 'hexagonal', 'rhombohedral', 'cubic'}
        Lattice system. This is equivalent to crystal families, except that the hexagonal lattice
        family is split in hexagonal and rhombohedral.
    """
    angleclose = partial(isclose, abs_tol = 1)
    lengthclose = partial(isclose, abs_tol = atol)

    a, b, c, alpha, beta, gamma = lattice.lattice_parameters
    lengths, angles = (a, b, c), (alpha, beta, gamma)

    lengths_equal = all(lengthclose(length, a) for length in lengths)
    angles_equal = all(angleclose(angle, alpha) for angle in angles)

    # Checking for monoclinic lattice system is generalized 
    # to the case where (a, b, c) can be cycled
    # i.e. a != c and beta != 90
    #   or b != c and alpha != 90
    #   or a != b and gamma != 90
    for clengths, cangles in zip(cyclic(lengths), cyclic(angles)):
        (l1, l2, l3), (a1, a2, a3) = clengths, cangles
        if ((not lengthclose(l1, l3)) and angleclose(a1, 90) and angleclose(a3, 90) 
                and (not angleclose(a2, 90))):
            return 'monoclinic'
    
    if (lengths_equal and angles_equal):
        if angleclose(alpha, 90):
            return 'cubic'
        else:
            return 'rhombohedral'
    
    # Special note : technically, a hexagonal lattice system
    # could have all three lengths equal
    elif lengths_equal and (not angles_equal):
        if (any(isclose(angle, 120) for angle in angles) and 
             (sum(isclose(i, 90) for i in angles) == 2)):
            return 'hexagonal'
    
    # At this point, two lengths are equal at most
    elif _two_equal(lengths, atol = atol):
        if angles_equal and angleclose(alpha, 90):
            return 'tetragonal'

        elif (any(isclose(angle, 120) for angle in angles) and 
             (sum(isclose(i, 90) for i in angles) == 2)):
            return 'hexagonal'

    # At this point, all lengths are unequal
    elif angles_equal and angleclose(alpha, 90):
        return 'orthorombic'

    else:
        return 'triclinic'

def _two_equal(iterable, atol):
    """ Returns True if and only if two items are equal """
    iterable = tuple(iterable)
    for i in iterable:
        if sum(isclose(i, l, abs_tol = atol) for l in iterable) == 2:
            return True
    return False
