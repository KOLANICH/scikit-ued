# -*- coding: utf-8 -*-
from math import radians
from copy import deepcopy, copy
from itertools import permutations
import numpy as np
from .. import Crystal, Atom, Lattice, graphite
from ... import rotation_matrix, transform
import unittest

# TODO: choose three or four crystals from CIFs

class TestBoundedReflections(unittest.TestCase):

	def setUp(self):
		self.crystal = deepcopy(graphite)

	def test_bounded_reflections_negative(self):
		""" Test that negative reflection bounds raise an Exception.
		Otherwise, an infinite number of reflections will be generated """
		with self.assertRaises(ValueError):
			hkl = list(self.crystal.bounded_reflections(-1))
	
	def test_bounded_reflections_zero(self):
		""" Check that bounded_reflections returns (000) for a zero bound """
		h, k, l = self.crystal.bounded_reflections(0)
		[self.assertEqual(len(i), 1) for i in (h, k, l)]
		[self.assertEqual(i[0], 0) for i in (h, k, l)]
	
	def test_bounded_reflections_all_within_bounds(self):
		""" Check that every reflection is within the bound """
		bound = 10
		Gx, Gy, Gz = self.crystal.scattering_vector(*self.crystal.bounded_reflections(nG = bound))
		norm_G = np.sqrt(Gx**2 + Gy**2 + Gz**2)
		self.assertTrue(np.all(norm_G <= bound))
    
class TestScatteringVectorsManipulations(unittest.TestCase):

    def setUp(self):
        self.crystal = deepcopy(graphite)

    def test_miller_indices_back_and_forth(self):
        """ Test that the output of Crystal.miller_indices and 
        Crystal.scattering_vector are compatible """
        h, k, l = self.crystal.bounded_reflections(4*np.pi)
        Gx, Gy, Gz = self.crystal.scattering_vector(h, k, l)
        h2, k2, l2 = self.crystal.miller_indices(Gx, Gy, Gz)

        self.assertTrue(np.allclose(h, h2))
        self.assertTrue(np.allclose(k, k2))
        self.assertTrue(np.allclose(l, l2))

class TestCrystalRotations(unittest.TestCase):

    def setUp(self):
        self.crystal = deepcopy(graphite)
    
    def test_crystal_equality(self):
        """ Tests that Crystal.__eq__ is working properly """
        self.assertEqual(self.crystal, self.crystal)

        cryst2 = deepcopy(self.crystal)
        cryst2.transform(2*np.eye(3)) # This stretches lattice vectors, symmetry operators
        self.assertFalse(self.crystal is cryst2)
        self.assertNotEqual(self.crystal, cryst2)

        cryst2.transform(0.5*np.eye(3))
        self.assertEqual(self.crystal, cryst2)
    
    def test_trivial_rotation(self):
        """ Test rotation by 360 deg around all axes. """
        unrotated = deepcopy(self.crystal)
        r = rotation_matrix(radians(360), [0,0,1])
        self.crystal.transform(r)
        self.assertEqual(self.crystal, unrotated)
    
    def test_identity_transform(self):
        """ Tests the trivial identity transform """
        transf = deepcopy(self.crystal)
        transf.transform(np.eye(3))
        self.assertEqual(self.crystal, transf)
    
    def test_one_axis_rotation(self):
        """ Tests the crystal orientation after rotations. """
        unrotated = deepcopy(self.crystal)

        self.crystal.transform(rotation_matrix(radians(45), [0,1,0]))
        self.assertNotEqual(unrotated, self.crystal)
        self.crystal.transform(rotation_matrix(radians(-45), [0,1,0]))
        self.assertEqual(unrotated, self.crystal)

    def test_wraparound_rotation(self):
        cryst1 = deepcopy(self.crystal)
        cryst2 = deepcopy(self.crystal)

        cryst1.transform(rotation_matrix(radians(22.3), [0,0,1]))
        cryst2.transform(rotation_matrix(radians(22.3 - 360), [0,0,1]))
        self.assertEqual(cryst1, cryst2)

if __name__ == '__main__':
    unittest.main()