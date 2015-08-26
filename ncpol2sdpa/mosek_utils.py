# -*- coding: utf-8 -*-
"""
The module contains helper functions to work with MOSEK.

Created on Tue Nov 18 10:51:14 2014

@author: Peter Wittek
"""
import sys
import numpy as np
from .sdpa_utils import convert_row_to_sdpa_index


def streamprinter(text):
    """Helper function for printing MOSEK messages in the Python console.
    """
    sys.stdout.write(text)
    sys.stdout.flush()

def moseksol_to_xmat(vec, block_struct):
    n = int(np.sqrt(1+8*len(vec))-1)/2
    if n*(n+1)/2 != len(vec):
        raise ValueError('vec should be of dimension n(n+1)/2')
    M = np.zeros((block_struct[0], block_struct[0]))
    row, column, block, index = 0, 0, 0, 0
    result = []
    while True:
        if column == block_struct[block]:
            row += 1
            column = row
            index += sum(block_struct[block+1:])
        if row == block_struct[block]:
            result.append(M.copy())
            block += 1
            if block == len(block_struct):
                break
            M = np.zeros((block_struct[block], block_struct[block]))
            row, column = 0, 0
        M[row, column] = vec[index]
        M[column, row] = vec[index]
        index += 1
        column += 1
    return result

def parse_mosek_solution(sdpRelaxation, task):
    import mosek
    soltype = mosek.soltype.itr
    primal, dual = task.getprimalobj(soltype), task.getdualobj(soltype)
    x_mat, y_mat = [], []
    size_ = sum(bs for bs in sdpRelaxation.block_struct)
    primal_solution = np.zeros(int(size_*(size_+1)/2))
    task.getbarxj(soltype, 0, primal_solution)
    y_mat = moseksol_to_xmat(primal_solution, sdpRelaxation.block_struct)
    dual_solution = np.zeros(size_*(size_+1)/2)
    task.getbarsj(soltype, 0, dual_solution)
    x_mat = moseksol_to_xmat(dual_solution, sdpRelaxation.block_struct)
    status = repr(task.getsolsta(soltype))
    return primal, dual, x_mat, y_mat, status

def solve_with_mosek(sdpRelaxation, solverparameters=None):
    task = convert_to_mosek(sdpRelaxation)
    import mosek
    if solverparameters is not None:
        for par,val in solverparameters.items():
            try:
                mskpar = eval('mosek.iparam.' + par)
                task.putintparam(mskpar, val)
            except AttributeError:
                try:
                    mskpar = eval('mosek.dparam.' + par)
                    task.putdouparam(mskpar, val)
                except AttributeError:
                    raise Exception('Unknown mosek parameter')
    task.optimize()
    primal, dual, x_mat, y_mat, status = parse_mosek_solution(sdpRelaxation, task)
    return -primal+sdpRelaxation.constant_term, \
           -dual+sdpRelaxation.constant_term, x_mat, y_mat, status


def convert_to_mosek_index(block_struct, row_offsets, block_offsets, row):
    """MOSEK requires a specific sparse format to define the lower-triangular
    part of a symmetric matrix. This function does the conversion from the
    sparse upper triangular matrix format of Ncpol2SDPA.
    """
    block_index, i, j = convert_row_to_sdpa_index(block_struct, row_offsets,
                                                  row)

    offset = block_offsets[block_index]
    ci = offset + i
    cj = offset + j
    return cj, ci  # Note that MOSEK expect lower-triangular matrices


def convert_to_mosek_matrix(sdpRelaxation):
    """Converts the entire sparse representation of the Fi constraint matrices
    to sparse MOSEK matrices.
    """
    barci = []
    barcj = []
    barcval = []
    barai = []
    baraj = []
    baraval = []
    for k in range(sdpRelaxation.n_vars):
        barai.append([])
        baraj.append([])
        baraval.append([])
    row_offsets = [0]
    block_offsets = [0]
    cumulative_sum = 0
    cumulative_square_sum = 0
    for block_size in sdpRelaxation.block_struct:
        cumulative_sum += block_size
        cumulative_square_sum += block_size ** 2
        row_offsets.append(cumulative_square_sum)
        block_offsets.append(cumulative_sum)
    for row in range(len(sdpRelaxation.F_struct.rows)):
        if len(sdpRelaxation.F_struct.rows[row]) > 0:
            col_index = 0
            for k in sdpRelaxation.F_struct.rows[row]:
                value = sdpRelaxation.F_struct.data[row][col_index]
                i, j = convert_to_mosek_index(sdpRelaxation.block_struct,
                                              row_offsets, block_offsets, row)
                if k > 0:
                    barai[k - 1].append(i)
                    baraj[k - 1].append(j)
                    baraval[k - 1].append(-value)
                else:
                    barci.append(i)
                    barcj.append(j)
                    barcval.append(value)
                col_index += 1
    return barci, barcj, barcval, barai, baraj, baraval


def convert_to_mosek(sdpRelaxation):
    """Convert an SDP relaxation to a MOSEK task.

    :param sdpRelaxation: The SDP relaxation to convert.
    :type sdpRelaxation: :class:`ncpol2sdpa.SdpRelaxation`.

    :returns: :class:`mosek.Task`.
    """
    import mosek
    barci, barcj, barcval, barai, baraj, baraval = \
        convert_to_mosek_matrix(sdpRelaxation)
    bkc = [mosek.boundkey.fx] * sdpRelaxation.n_vars
    blc = [-v for v in sdpRelaxation.obj_facvar]
    buc = [-v for v in sdpRelaxation.obj_facvar]

    env = mosek.Env()
    task = env.Task(0, 0)
    if sdpRelaxation.verbose>0:
        task.set_Stream(mosek.streamtype.log, streamprinter)
    numvar = 0
    numcon = len(bkc)
    BARVARDIM = [sum(sdpRelaxation.block_struct)]

    task.appendvars(numvar)
    task.appendcons(numcon)
    task.appendbarvars(BARVARDIM)
    for i in range(numcon):
        task.putconbound(i, bkc[i], blc[i], buc[i])

    symc = task.appendsparsesymmat(BARVARDIM[0], barci, barcj, barcval)
    task.putbarcj(0, [symc], [1.0])

    for i in range(len(barai)):
        syma = task.appendsparsesymmat(BARVARDIM[0], barai[i], baraj[i],
                                       baraval[i])
        task.putbaraij(i, 0, [syma], [1.0])

    # Input the objective sense (minimize/maximize)
    task.putobjsense(mosek.objsense.minimize)

    return task
