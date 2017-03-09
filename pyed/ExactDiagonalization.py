# ----------------------------------------------------------------------

""" General routines for exact diagonalization and calculation of
single particle response functions in frequency and imaginary time
using the Lehmann spectral representation.

Author: Hugo U. R. Strand (2015), hugo.strand@gmail.com """

# ----------------------------------------------------------------------

import time
import itertools
import numpy as np
from scipy.linalg import expm

#import scipy.sparse as sparse

from scipy.sparse.linalg import eigs as eigs_sparse
from scipy.sparse.linalg import eigsh as eigsh_sparse

# ----------------------------------------------------------------------
class TetrahedronHelper(object):

    def __init__(self, N):
        self.N = N

# ----------------------------------------------------------------------
def tetra_index(N, tetra_index=0):

    """ Get indices for one of the six tetrahedra. """
    
    tetra_list = [
        (lambda x,y,z : x > y and y > z, [0, 1, 2], +1),
        (lambda x,y,z : y > x and x > z, [1, 0, 2], -1),
        #
        (lambda x,y,z : y > z and z > x, [1, 2, 0], +1),
        (lambda x,y,z : z > y and y > x, [2, 1, 0], -1),
        #
        (lambda x,y,z : x > z and z > y, [0, 2, 1], -1),
        (lambda x,y,z : z > x and x > y, [2, 0, 1], +1),
        #
        #(lambda x,y,z : x >= y and y >= z, [0, 1, 2], +1),
        #(lambda x,y,z : y >= x and x >= z, [1, 0, 2], -1),
        #
        #(lambda x,y,z : y >= z and z >= x, [1, 2, 0], +1),
        #(lambda x,y,z : z >= y and y >= x, [2, 1, 0], -1),
        #
        #(lambda x,y,z : x >= z and z >= y, [0, 2, 1], -1),
        #(lambda x,y,z : z >= x and x >= y, [2, 0, 1], +1),
        ]

    func, perm, sign = tetra_list[tetra_index]
    
    index = []
    for n1, n2, n3 in itertools.product(range(N), repeat=3):
        if func(n1, n2, n3): index.append((n1, n2, n3))

    return np.array(index).T, perm, sign

# ----------------------------------------------------------------------
class ExactDiagonalization(object):

    # ------------------------------------------------------------------
    def __init__(self, H, beta, nstates=None, hermitian=True,
                 v0=None, tol=0):

        self.v0 = v0
        self.tol = tol
        
        self.nstates = nstates
        self.hermitian = hermitian
        
        self.H = H
        self.beta = beta

        self._diagonalize_hamiltonian()
        self._calculate_partition_function()
        
    # ------------------------------------------------------------------
    def _diagonalize_hamiltonian(self):
       
        if self.nstates is None:
            if self.hermitian:
                self.E, self.U = np.linalg.eigh(self.H.todense())
            else:
                self.E, self.U = np.linalg.eig(self.H.todense())
        else:
            if self.hermitian:
                t = time.time()
                self.E, self.U = eigsh_sparse(
                    self.H, k=self.nstates, which='SA',
                    v0=self.v0, tol=self.tol, ncv=self.nstates*8+1)
                print 'ED:', time.time() - t, ' s'
            else:
                self.E, self.U = eigs_sparse(
                    self.H, k=self.nstates, which='SR',
                    v0=self.v0, tol=self.tol)
            
        self.U = np.mat(self.U)
        self.E0 = np.min(self.E)
        self.E = self.E - self.E0

    # ------------------------------------------------------------------
    def _calculate_partition_function(self):

        exp_bE = np.exp(-self.beta * self.E)
        self.Z = np.sum(exp_bE)

    # ------------------------------------------------------------------
    def _calculate_density_matrix(self):

        exp_bE = np.exp(-self.beta * self.E) / self.Z
        self.rho = np.einsum('ij,j,jk->ik', self.U, exp_bE, self.U.H)

    # ------------------------------------------------------------------
    def _operators_to_eigenbasis(self, op_vec):

        dop_vec = []
        for op in op_vec:
            dop = np.mat(self.U).H * op.todense() * np.mat(self.U)
            dop_vec.append(dop)

        return dop_vec
        
    # ------------------------------------------------------------------
    def get_expectation_value_sparse(self, operator):

        exp_val = 0.0
        for idx in xrange(self.E.size):
            vec = self.U[:, idx]
            dot_prod = np.dot(vec.H, operator * vec)[0,0] # <n|O|n>
            exp_val += np.exp(-self.beta * self.E[idx]) * dot_prod

        exp_val /= self.Z

        return exp_val
    
    # ------------------------------------------------------------------
    def get_expectation_value_dense(self, operator):

        if not hasattr(self, 'rho'): self._calculate_density_matrix()            
        return np.sum(np.diag(operator * self.rho))

    # ------------------------------------------------------------------
    def get_expectation_value(self, operator):

        if self.nstates is None:
            return self.get_expectation_value_dense(operator)
        else:
            return self.get_expectation_value_sparse(operator)
    
    # ------------------------------------------------------------------
    def get_free_energy(self):

        r""" Free energy using ground state energy shift

        Z = \sum_n e^{-\beta E_n}
        \Omega = -1/\beta \ln Z

        Z = e^{-\beta E_0} x \sum_n e^{-\beta (E_n - E_0)} = e^{-beta E_0} Z'
        \Omega = -1/\beta ( \ln Z' - \beta E_0 ) """
        
        Omega = -1./self.beta * (np.log(self.Z) - self.beta * self.E0)
        return Omega
    
    # ------------------------------------------------------------------
    def get_partition_function():
        return self.Z

    # ------------------------------------------------------------------
    def get_density_matrix():
        return self.rho

    # ------------------------------------------------------------------
    def get_eigen_values():
        return self.E

    # ------------------------------------------------------------------
    def get_eigen_vectors():
        return self.U

    # ------------------------------------------------------------------
    def get_ground_state_energy():
        return self.E0
    
    # ------------------------------------------------------------------
    def get_g2_dissconnected_tau(self, tau, g):

        g = np.squeeze(g) # fix for now throwing orb idx
        g = g.real
        
        N = len(tau)
        G4 = np.zeros((N, N, N), dtype=np.complex)

        def gint(t):
            sign = 1.0
            if (t < 0).any():
                assert( (t <= 0).all() )
                #t = self.beta - t
                t = self.beta + t
                sign = -1.0

            return sign * np.interp(t, tau, g)
        
        for tidx in xrange(6):
            idx, perm, perm_sign = tetra_index(N, tetra_index=tidx)
            i1, i2, i3 = idx
            t1, t2, t3 = tau[i1], tau[i2], tau[i3]

            G4[list(idx)] = gint(t1-t2)*gint(t3) - gint(t1)*gint(t3-t2)

        return G4
    
    # ------------------------------------------------------------------
    def get_g2_tau(self, tau, ops):

        # ------
        # test acces
        N = len(tau)
        tmp = np.zeros((N, N, N), dtype=np.complex)
        for tidx in xrange(6):
            idx, perm, perm_sign = tetra_index(N, tetra_index=tidx)
            i1, i2, i3 = idx
            tmp[list(idx)] += 1.0

        assert( not (tmp > 1.0).any() )
        # ------
        
        N = len(tau)
        G4 = np.zeros((N, N, N), dtype=np.complex)
        ops = np.array(ops)

        for tidx in xrange(6):
            idx, perm, perm_sign = tetra_index(N, tetra_index=tidx)
            print 'Tetra idx:', tidx, perm

            i1, i2, i3 = idx
            t1, t2, t3 = tau[i1], tau[i2], tau[i3]
            
            # permute times and operators

            taus = np.vstack([t1, t2, t3])
            taus_perm = taus[perm] # permute the times
            
            ops_perm = ops[perm + [3]] # do not permute the last operator
            
            G4[list(idx)] = self.get_high_order_tau_greens_function(
                taus_perm, ops_perm) * perm_sign

        return G4

    # ------------------------------------------------------------------
    def get_high_order_tau_greens_function(self, taus, ops):

        r"""
        G(t) = - < b(t) b^+(o) > 
             = - 1/Z Tr[ e^{-\beta H} e^{t H} b e^{-t H} b^+]
             = -1/Z \sum_n e^{-\beta E_n} \sum_m e^{-t(E_m-E_n)} <n|b|m><m|b^+|n>

        with 
        U_p(t) = \sum_n |n> e^{(t-\beta)E_n} <n|
        U_m(t) = \sum_m |m> e^{-t E_m} <m|

        this takes the form

        G(t) = -1/Z Tr[ U_p(t) b U_m(t) b^+ ]

        """

        assert( taus.shape[0] == 3 )
        assert( len(ops) == 4 )

        Nop = 4
        G = np.zeros((taus.shape[-1]), dtype=np.complex)


        E = self.E[None, :]

        t1, t2, t3 = taus
        t1, t2, t3 = t1[:, None], t2[:, None], t3[:, None]

        assert( (t1 <= self.beta).all() )
        assert( (t1 >= t2).all() )
        assert( (t2 >= t3).all() )
        assert( (t3 >= 0).all() )

        print ((t1 >= t2)*(t2 >= t3)).all()
        
        et_a = np.exp((-self.beta + t1)*E)
        et_b = np.exp((t2-t1)*E)
        et_c = np.exp((t3-t2)*E)
        et_d = np.exp((-t3)*E)

        dops = self._operators_to_eigenbasis(ops)
        op1, op2, op3, op4 = dops
        
        G = np.einsum(
            'ta,tb,tc,td,ab,bc,cd,da->t',
            et_a, et_b, et_c, et_d, op1, op2, op3, op4)

        G /= self.Z        
        return G

    # ------------------------------------------------------------------
    def get_tau_greens_function(self, tau, op_vec):

        r"""
        G(t) = - < b(t) b^+(o) > 
             = - 1/Z Tr[ e^{-\beta H} e^{t H} b e^{-t H} b^+]
             = -1/Z \sum_n e^{-\beta E_n} \sum_m e^{-t(E_m-E_n)} <n|b|m><m|b^+|n>

        with 
        U_p(t) = \sum_n |n> e^{(t-\beta)E_n} <n|
        U_m(t) = \sum_m |m> e^{-t E_m} <m|

        this takes the form

        G(t) = -1/Z Tr[ U_p(t) b U_m(t) b^+ ]

        """

        Nop = len(op_vec)
        G = np.zeros((Nop, Nop, len(tau)), dtype=np.complex)

        dop_vec = self._operators_to_eigenbasis(op_vec)
        
        et_p = np.exp((-self.beta + tau[:,None])*self.E[None,:])
        et_m = np.exp(-tau[:,None]*self.E[None,:])
        
        for i1, i2 in itertools.product(range(Nop), repeat=2):
            op1, op2 = dop_vec[i1], dop_vec[i2]
            G[i1, i2] = -np.einsum(
                'tn,tm,nm,mn->t', et_p, et_m, op1, np.mat(op2).H)

        G /= self.Z        
        return G

    # ------------------------------------------------------------------
    def get_tau_greens_function_numba_depr(self, tau, op_vec):

        r"""
        G(t) = - < b(t) b^+(o) > 
             = - 1/Z Tr[ e^{-\beta H} e^{t H} b e^{-t H} b^+]
             = -1/Z \sum_n e^{-\beta E_n} \sum_m e^{-t(E_m-E_n)} <n|b|m><m|b^+|n>

        with 
        U_p(t) = \sum_n |n> e^{(t-\beta)E_n} <n|
        U_m(t) = \sum_m |m> e^{-t E_m} <m|

        this takes the form

        G(t) = -1/Z Tr[ U_p(t) b U_m(t) b^+ ]

        """

        from ExactDiagonalizationNumba import \
            numba_get_tau_greens_function_depr
        
        Nop = len(op_vec)
        G = np.zeros((Nop, Nop, len(tau)), dtype=np.float)

        for i1, i2 in itertools.product(range(Nop), repeat=2):
            b = op_vec[i1].todense()
            bd = op_vec[i2].getH().todense()                  
            G[i1, i2, :] = numba_get_tau_greens_function_depr(
                tau, b, bd, self.beta, self.E, self.U)
        
        G /= -self.Z        
        return G

    # ------------------------------------------------------------------
    def get_tau_greens_function_numba(self, tau, op_vec):

        r"""
        G(t) = - < b(t) b^+(o) > 
             = - 1/Z Tr[ e^{-\beta H} e^{t H} b e^{-t H} b^+]
             = -1/Z \sum_n e^{-\beta E_n} \sum_m e^{-t(E_m-E_n)} <n|b|m><m|b^+|n>

        with 
        U_p(t) = \sum_n |n> e^{(t-\beta)E_n} <n|
        U_m(t) = \sum_m |m> e^{-t E_m} <m|

        this takes the form

        G(t) = -1/Z Tr[ U_p(t) b U_m(t) b^+ ]

        """

        from ExactDiagonalizationNumba import \
            numba_get_tau_greens_function
        
        Nop = len(op_vec)
        G = np.zeros((Nop, Nop, len(tau)), dtype=np.float)
        dop_vec = self._operators_to_eigenbasis(op_vec)
        
        for i1, i2 in itertools.product(range(Nop), repeat=2):
            op1, op2 = dop_vec[i1], dop_vec[i2]            
            G[i1, i2, :] = numba_get_tau_greens_function(
                tau, op1, op2, self.beta, self.E, self.U)
        
        G /= -self.Z        
        return G

    # ------------------------------------------------------------------
    def get_frequency_greens_function(self, z, op_vec, xi,
                                      verbose=False,
                                      only_n_ne_m_contribs=False,
                                      full_output=False):

        r""" For i\omega_n - (E_m - E_n) != 0 we have:

        G(i\omega_n) = 
            Z^{-1} \sum_{nm} <n|b|m><m|b^+|n>/(z - (E_m-E_n)) 
            * (e^{-beta E_n} - \xi e^{-\beta E_m})
            = Z^{-1} \sum{nm} b_{nm} (b^+)_{mn}/(z - dE_{nm}) * M_{nm}

        While for i\omega_0 - (E_n - E_n) == 0 we get the additional contrib

        G(i\omega_0) += -Z^{-1} \sum_{n} <n|b|n><n|b^+|n> \beta e^{-\beta E_n}
        """
        
        # -- Setup components of the Lehman expression
        dE = - self.E[:, None] + self.E[None, :]
        exp_bE = np.exp(-self.beta * self.E)
        M = exp_bE[:, None] - xi * exp_bE[None, :]

        inv_freq = z[:, None, None] - dE[None, :, :]
        nonzero_idx = np.nonzero(inv_freq) # -- Only eval for non-zero values
        freq = np.zeros_like(inv_freq)
        freq[nonzero_idx] = inv_freq[nonzero_idx]**(-1)

        # -- Trasform operators to eigen basis
        dop_vec = []
        for op in op_vec:
            dop = np.mat(self.U).H * op.todense() * np.mat(self.U)
            dop_vec.append(dop)

        # -- Compute Lehman sum for all operator combinations
        Nop = len(dop_vec)
        G = np.zeros((Nop, Nop, len(z)), dtype=np.complex)
        G0 = np.zeros((Nop, Nop), dtype=np.complex)
        for i1, i2 in itertools.product(range(Nop), repeat=2):
            op1, op2 = dop_vec[i1], dop_vec[i2]
            G[i1, i2] = np.einsum('nm,mn,nm,znm->z',
                                  op1, np.mat(op2).H, M, freq)
            # -- Zero frequency and zero energy difference contribution
            G0[i1, i2] = np.einsum('n,nn,nn->',
                                   -self.beta * exp_bE, op1, np.mat(op2).H)

        # -- Additional zero freq contrib
        if not only_n_ne_m_contribs:
            G[:, :, (z == 0.0)] += G0[:, :, None]
        else:
            #print '--> WARNING: Removing zero freq. contrib in ED'
            pass

        # -- Normalization by partition function
        G /= self.Z

        # -- Change axes from [2, 2, z] to [z, 2, 2]
        G = np.rollaxis(G, -1)

        if full_output:
            return G, G0
        else:
            return G
    
    # ------------------------------------------------------------------
    def get_frequency_greens_function_numba_depr(self, z, op_vec, xi,
                                      verbose=False,
                                      only_n_ne_m_contribs=False):

        r""" For i\omega_n - (E_m - E_n) != 0 we have:

        G(i\omega_n) = 
            Z^{-1} \sum_{nm} <n|b|m><m|b^+|n>/(z - (E_m-E_n)) 
            * (e^{-beta E_n} - \xi e^{-\beta E_m})
            = Z^{-1} \sum{nm} b_{nm} (b^+)_{mn}/(z - dE_{nm}) * M_{nm}

        While for i\omega_0 - (E_n - E_n) == 0 we get the additional contrib

        G(i\omega_0) += -Z^{-1} \sum_{n} <n|b|n><n|b^+|n> \beta e^{-\beta E_n}
        """
        
        from ExactDiagonalizationNumba import \
            numba_get_frequency_greens_function_depr

        # -- Compute Lehman sum for all operator combinations
        Nop = len(op_vec)
        G = np.zeros((Nop, Nop, len(z)), dtype=np.complex)
        G0 = np.zeros((Nop, Nop), dtype=np.complex)
        
        for i1, i2 in itertools.product(range(Nop), repeat=2):

            # -- Ref calc
            G_work = np.zeros_like(z)
            G0_work = np.zeros((1), dtype=np.complex)
            
            b, bd = op_vec[i1].todense(), op_vec[i2].getH().todense()

            numba_get_frequency_greens_function_depr(G_work, G0_work,
                 z, b, bd, self.beta, self.E, self.U, xi=xi)

            G[i1, i2, :] = G_work
            G0[i1, i2] = G0_work[0]
            
        # -- Additional zero freq contrib
        if not only_n_ne_m_contribs:
            G[:, :, (z == 0.0)] += G0[:, :, None]
        else:
            #print '--> WARNING: Removing zero freq. contrib in ED'
            pass

        # -- Normalization by partition function
        G /= self.Z

        # -- Change axes from [2, 2, z] to [z, 2, 2]
        G = np.rollaxis(G, -1)
        
        return G

    # ------------------------------------------------------------------
    def get_frequency_greens_function_numba(self, z, op_vec, xi,
                                      verbose=False,
                                      only_n_ne_m_contribs=False):

        r""" For i\omega_n - (E_m - E_n) != 0 we have:

        G(i\omega_n) = 
            Z^{-1} \sum_{nm} <n|b|m><m|b^+|n>/(z - (E_m-E_n)) 
            * (e^{-beta E_n} - \xi e^{-\beta E_m})
            = Z^{-1} \sum{nm} b_{nm} (b^+)_{mn}/(z - dE_{nm}) * M_{nm}

        While for i\omega_0 - (E_n - E_n) == 0 we get the additional contrib

        G(i\omega_0) += -Z^{-1} \sum_{n} <n|b|n><n|b^+|n> \beta e^{-\beta E_n}
        """

        from ExactDiagonalizationNumba import \
            numba_get_frequency_greens_function

        Nop = len(op_vec)
        G = np.zeros((Nop, Nop, len(z)), dtype=np.complex)
        G0 = np.zeros((Nop, Nop), dtype=np.complex)
        dop_vec = self._operators_to_eigenbasis(op_vec)
            
        for i1, i2 in itertools.product(range(Nop), repeat=2):

            G0_work = np.zeros((1), dtype=np.complex)            
            op1, op2 = dop_vec[i1], dop_vec[i2]

            numba_get_frequency_greens_function(G[i1, i2], G0_work,
                 z, op1, op2, self.beta, self.E, self.U, xi=xi)

            G0[i1, i2] = G0_work[0]
            
        # -- Additional zero freq contrib
        if not only_n_ne_m_contribs:
            G[:, :, (z == 0.0)] += G0[:, :, None]
        else:
            #print '--> WARNING: Removing zero freq. contrib in ED'
            pass

        # -- Normalization by partition function
        G /= self.Z

        # -- Change axes from [2, 2, z] to [z, 2, 2]
        G = np.rollaxis(G, -1)
        
        return G
    
    # ------------------------------------------------------------------
    def get_high_frequency_tail_coeff(self, op_vec, xi, Norder=3):

        r""" The high frequency tail corrections can be derived 
        directly from the imaginary time expression for the Green's function
        
        G(t) = -1/Z Tr[e^{-\beta H} e^{tH} b e^{-tH} b^+]

        and the observation that the high frequency components of the 
        Matsubara Green's function G(i\omega_n) can be obtained by partial
        integration in

        G(i\omega_n) = \int_0^\beta dt e^{i\omega_n t} G(t)
                     = \sum_k=0^\infty (-1)^k
                       (\xi G^{(k)}(\beta^-) - G^{(k)}(0^+))/(i\omega_n)^(k+1)
                     = \sum_{k=1} c_k / (i\omega_n)^{k}

        where the n:th order derivative G^{(n)}(t) can be expressed as

        G^{(k)}(t) = - < [[ H , b(t) ]]^{(k)} b^+ >

        where [[H, b]]^{(k)} = [H, [H, [H, ... [H, b] ... ]]] is the k:th order
        left side commutator of H with b.

        Using this the high frequency coefficients c_k takes the form

        c_k = (-1)^(k-1) (\xi G^{(k-1)}(\beta^-) - G^{(k-1)}(0^+)) 
            = (-1)^k < [ [[ H , b ]]^{(k-1)} , b^+ ]_{-\xi} >

        """
        
        def xi_commutator(A, B, xi):
            return A * B - xi * B * A
            
        def commutator(A, B):
            return A * B - B * A

        #def nth_order_leftside_commutator(A, B, order=1):
        #    C = B
        #    for idx in xrange:
        #        C = commutator(A, C)
        #    return C

        H = self.H
        #Hba = nth_order_leftside_commutator(H, ba, n=1)
        #coeff = xi_commutator(Hba, bc)
        
        Nop = len(op_vec)
        Gc = np.zeros((Norder, Nop, Nop), dtype=np.complex)
        for i1, i2 in itertools.product(range(Nop), repeat=2):
            ba, bc = op_vec[i1], op_vec[i2].getH()

            Hba = ba
            for order in xrange(Norder):
                tail_op = xi_commutator(Hba, bc, xi)                
                Gc[order, i1, i2] = (-1.)**(order) * \
                                    self.get_expectation_value(tail_op)
                Hba = commutator(H, Hba)
                
        return Gc        

    # ------------------------------------------------------------------
    def get_high_frequency_tail(self, iwn, Gc, start_order=-1):

        """ from the high frequency coefficients Gc calculate the 
        Matsubara Green's function tail

        G(i\omega_n) = \sum_k Gc[k] / (i\omega_n)^k """
        
        Nop = Gc.shape[-1]
        Nw = len(iwn)
        G = np.zeros((Nw, Nop, Nop), dtype=np.complex)
        iwn_idx = np.nonzero(iwn)[0] # -- Only eval for non-zero freq.
        for idx, gc in enumerate(Gc):
            G[iwn_idx, :, :] += \
                iwn[iwn_idx, None, None]**(-idx+start_order) * gc[None, :, :]

        return G            

    # ------------------------------------------------------------------

# ----------------------------------------------------------------------
