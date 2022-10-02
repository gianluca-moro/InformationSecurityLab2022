import math
import random
from fpylll import LLL
from fpylll import BKZ
from fpylll import IntegerMatrix
from fpylll import CVP
from fpylll import SVP
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def egcd(a, b):
    # Implement the Euclidean algorithm for gcd computation
    # copied from "module_1_ECC_ECDSA.py"
    if a == 0:
        return b, 0, 1
    else:
        g, y, x = egcd(b % a, a)
        return g, x - (b // a) * y, y


def mod_inv(a, p):
    # Implement a function to compute the inverse of a modulo p
    # Hint: Use the gcd algorithm implemented above
    # copied from "module_1_ECC_ECDSA.py" 
    if a < 0:
        return p - mod_inv(-a, p)
    g, x, y = egcd(a, p)
    if g != 1:
        raise ArithmeticError("Modular inverse does not exist")
    else:
        return x % p


def check_x(x, Q):
    """ Given a guess for the secret key x and a public key Q = [x]P,
        checks if the guess is correct.

        :params x:  secret key, as an int
        :params Q:  public key, as a tuple of two ints (Q_x, Q_y)
    """
    x = int(x)
    if x <= 0:
        return False
    Q_x, Q_y = Q
    sk = ec.derive_private_key(x, ec.SECP256R1())
    pk = sk.public_key()
    xP = pk.public_numbers()
    return xP.x == Q_x and xP.y == Q_y


def recover_x_known_nonce(k, h, r, s, q):
    # Implement the "known nonce" cryptanalytic attack on ECDSA
    # The function is given the nonce k, (h, r, s) and the base point order q
    # The function should compute and return the secret signing key x
    return (mod_inv(r, q) * (k * s - h)) % q


def recover_x_repeated_nonce(h_1, r_1, s_1, h_2, r_2, s_2, q):
    # Implement the "repeated nonces" cryptanalytic attack on ECDSA
    # The function is given the (hashed-message, signature) pairs (h_1, r_1, s_1) and (h_2, r_2, s_2) generated using the same nonce
    # The function should compute and return the secret signing key x
    return ((h_1 * s_2 - h_2 * s_1) * mod_inv(r_2 * s_1 - r_1 * s_2, q)) % q


def bit_list_to_int(bit_list):
    out = 0
    for bit in bit_list:
        out = (out << 1) | bit
    return out


def MSB_to_Padded_Int(N, L, list_k_MSB):
    # Implement a function that does the following: 
    # Let a is the integer represented by the L most significant bits of the nonce k 
    # The function should return a.2^{N - L} + 2^{N -L -1}
    #raise NotImplementedError()
    a = bit_list_to_int(list_k_MSB)
    return a * 2**(N - L) + 2**(N - L - 1)


def LSB_to_Int(list_k_LSB):
    # Implement a function that does the following: 
    # Let a is the integer represented by the L least significant bits of the nonce k 
    # The function should return a
    #raise NotImplementedError()
    return bit_list_to_int(list_k_LSB)


def setup_hnp_single_sample(N, L, list_k_MSB, h, r, s, q, givenbits="msbs", algorithm="ecdsa"):
    # Implement a function that sets up a single instance for the hidden number problem (HNP)
    # The function is given a list of the L most significant bts of the N-bit nonce k, along with (h, r, s) and the base point order q
    # The function should return (t, u) computed as described in the lectures
    # In the case of EC-Schnorr, r may be set to h
    if algorithm == "ecschnorr":
        r = h

    # TODO: is the rest really the same, independent of algorithm???? I don't think so...
    #       -> later part of the lab

    t = (r * mod_inv(s, q)) % q
    z = (h * mod_inv(s, q)) % q
    u = MSB_to_Padded_Int(N, L, list_k_MSB) - z
    return (t, u)


def setup_hnp_all_samples(N, L, num_Samples, listoflists_k_MSB, list_h, list_r, list_s, q, givenbits="msbs", algorithm="ecdsa"):
    # Implement a function that sets up n = num_Samples many instances for the hidden number problem (HNP)
    # For each instance, the function is given a list the L most significant bits of the N-bit nonce k, along with (h, r, s) and the base point order q
    # The function should return a list of t values and a list of u values computed as described in the lectures
    # Hint: Use the function you implemented above to set up the t and u values for each instance
    # In the case of EC-Schnorr, list_r may be set to list_h
    #raise NotImplementedError()
    if algorithm == "ecschnorr":
        list_r = list_h

    list_t = []
    list_u = []
    for i in range(num_Samples):
        t, u = setup_hnp_single_sample(N, L, listoflists_k_MSB[i], list_h[i], list_r[i], list_s[i], q, givenbits, algorithm)
        list_t.append(t)
        list_u.append(u)

    return list_t, list_u


def hnp_to_cvp(N, L, num_Samples, list_t, list_u, q):
    # Implement a function that takes as input an instance of HNP and converts it into an instance of the closest vector problem (CVP)
    # The function is given as input a list of t values, a list of u values and the base point order q
    # The function should return the CVP basis matrix B (to be implemented as a nested list) and the CVP target vector u (to be implemented as a list)
    # NOTE: The basis matrix B and the CVP target vector u should be scaled appropriately. Refer lecture slides and lab sheet for more details 
    n = num_Samples
    # TODO: correct scaling??? scale with (2**(L+1)) (?) so last value is 1 ???
    scale_factor = 2**(L + 1)
    
    B_cvp = [[0 for _ in range(n + 1)] for _ in range(n + 1)]
    for i in range(n):
        B_cvp[i][i] = int(q * scale_factor)
        B_cvp[n][i] = int(list_t[i] * scale_factor)

    B_cvp[n][n] = 1     # int((1 / 2)**(L + 1) * scale_factor)

    u_cvp = [int(u * scale_factor) for u in list_u] + [0]
        
    return B_cvp, u_cvp
    

def cvp_to_svp(N, L, num_Samples, cvp_basis_B, cvp_list_u):
    # Implement a function that takes as input an instance of CVP and converts it into an instance of the shortest vector problem (SVP)
    # Your function should use the Kannan embedding technique in the lecture slides
    # The function is given as input a CVP basis matrix B and the CVP target vector u
    # The function should use the Kannan embedding technique to output the corresponding SVP basis matrix B' of apropriate dimensions.
    # The SVP basis matrix B' should again be implemented as a nested list
    
    # Note: type(cvp_basis_B) = nested list
    # Note: type(cvp_list_u) = list

    size_B_cvp = len(cvp_basis_B)
    B_svp = [[0 for _ in range(size_B_cvp + 1)] for _ in range(size_B_cvp + 1)]
    for i in range(size_B_cvp):
        for j in range(size_B_cvp):
            B_svp[i][j] = cvp_basis_B[i][j]

        B_svp[-1][i] = cvp_list_u[i]

    # TODO: what is correct value of M?????? -> probably explained in exercise
    M = 1

    B_svp[-1][-1] = M

    return B_svp


def solve_cvp(cvp_basis_B, cvp_list_u):
    # Implement a function that takes as input an instance of CVP and solves it using in-built CVP-solver functions from the fpylll library
    # The function is given as input a CVP basis matrix B and the CVP target vector u
    # The function should output the solution vector v (to be implemented as a list)
    # NOTE: The basis matrix B should be processed appropriately before being passes to the fpylll CVP-solver. See lab sheet for more details
    # https://github.com/fplll/fpylll/blob/master/src/fpylll/fplll/svpcvp.pyx
    # https://github.com/fplll/fpylll/blob/master/src/fpylll/fplll/integer_matrix.pyx
    rows, cols = len(cvp_basis_B), len(cvp_basis_B[0])
    B = IntegerMatrix(rows, cols)
    B.set_matrix(cvp_basis_B)
    B = LLL.reduction(B)
    v = CVP.closest_vector(B, cvp_list_u)
    return list(v)


def solve_svp(svp_basis_B):
    # Implement a function that takes as input an instance of SVP and solves it using in-built SVP-solver functions from the fpylll library
    # The function is given as input the SVP basis matrix B
    # The function should output a list of candidate vectors that may contain x as a coefficient
    # NOTE: Recall from the lecture and also from the exercise session that for ECDSA cryptanalysis based on partial nonces, you might want
    #       your function to include in the list of candidate vectors the *second* shortest vector (or even a later one). 
    # If required, figure out how to get the in-built SVP-solver functions from the fpylll library to return the second (or later) shortest vector
    rows, cols = len(svp_basis_B), len(svp_basis_B[0])
    B = IntegerMatrix(rows, cols)
    B.set_matrix(svp_basis_B)

    # TODO: this might be wrong
    SVP.shortest_vector(B)
    return list(B)


def recover_x_partial_nonce_CVP(Q, N, L, num_Samples, listoflists_k_MSB, list_h, list_r, list_s, q, givenbits="msbs", algorithm="ecdsa"):
    # Implement the "repeated nonces" cryptanalytic attack on ECDSA and EC-Schnorr using the in-built CVP-solver functions from the fpylll library
    # The function is partially implemented for you. Note that it invokes some of the functions that you have already implemented
    list_t, list_u = setup_hnp_all_samples(N, L, num_Samples, listoflists_k_MSB, list_h, list_r, list_s, q)
    cvp_basis_B, cvp_list_u = hnp_to_cvp(N, L, num_Samples, list_t, list_u, q)
    v_List = solve_cvp(cvp_basis_B, cvp_list_u)
    # The function should recover the secret signing key x from the output of the CVP solver and return it

    x = v_List[-1] % q
    
    # TODO: remove/comment before submit
    #if not check_x(x, Q):
    #    print("CVP: Not correct")

    return x


def recover_x_partial_nonce_SVP(Q, N, L, num_Samples, listoflists_k_MSB, list_h, list_r, list_s, q, givenbits="msbs", algorithm="ecdsa"):
    # Implement the "repeated nonces" cryptanalytic attack on ECDSA and EC-Schnorr using the in-built CVP-solver functions from the fpylll library
    # The function is partially implemented for you. Note that it invokes some of the functions that you have already implemented
    list_t, list_u = setup_hnp_all_samples(N, L, num_Samples, listoflists_k_MSB, list_h, list_r, list_s, q)
    cvp_basis_B, cvp_list_u = hnp_to_cvp(N, L, num_Samples, list_t, list_u, q)
    svp_basis_B = cvp_to_svp(N, L, num_Samples, cvp_basis_B, cvp_list_u)
    list_of_f_List = solve_svp(svp_basis_B)
    # The function should recover the secret signing key x from the output of the SVP solver and return it
    f = list_of_f_List[1]   # use second shortest

    # TODO: HOW TO GET x?????
    x = (cvp_list_u[-2] - f[-2]) % q

    # TODO: remove/comment before submit
    #if not check_x(x, Q):
    #    print("SVP: Not correct")
    return x



# testing code: do not modify

from module_1_ECDSA_Cryptanalysis_tests import run_tests

run_tests(recover_x_known_nonce,
    recover_x_repeated_nonce,
    recover_x_partial_nonce_CVP,
    recover_x_partial_nonce_SVP
)
