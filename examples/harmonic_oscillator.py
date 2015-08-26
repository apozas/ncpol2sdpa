# -*- coding: utf-8 -*-
"""
Exporting a Hamiltonian ground state problem to SDPA. The Hamiltonian
is of a simple harmonic oscillator. Bosonic systems reach the optimum
solution at relaxation level 1:

Navascués, M. García-Sáez, A. Acín, A. and Pironio, S. A paradox in bosonic
energy computations via semidefinite programming relaxations. New Journal of
Physics, 2013, 15, 023026.

Created on Fri May 10 09:45:11 2013

@author: Peter Wittek
"""
import time
from sympy.physics.quantum.dagger import Dagger
from ncpol2sdpa import generate_variables, SdpRelaxation,\
                       write_to_sdpa, bosonic_constraints

# Level of relaxation
level = 1

# Number of variables
N = 3

# Parameters for the Hamiltonian
hbar, omega = 1, 1

# Define ladder operators
a = generate_variables(N, name='a')
substitutions = bosonic_constraints(a)

hamiltonian = sum(hbar * omega * (Dagger(a[i]) * a[i]) for i in range(N))

time0 = time.time()
# Obtain SDP relaxation
print("Obtaining SDP relaxation...")
sdpRelaxation = SdpRelaxation(a, verbose=1)
sdpRelaxation.get_relaxation(level, objective=hamiltonian,
                             substitutions=substitutions)
# Export relaxation to SDPA format
write_to_sdpa(sdpRelaxation, 'harmonic_oscillator.dat-s')

print('%0.2f s' % ((time.time() - time0)))
