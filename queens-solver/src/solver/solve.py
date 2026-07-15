import cpmpy as cp
import numpy as np
from solver.puzzle import Puzzle

def solve(puzzle: Puzzle):
    """ solve the puzzle and return a tuple containing the status and solution """
    n = puzzle.n
    regions = puzzle.regions
    Q = cp.boolvar(shape=(n, n)) #n x n numpy array of boolean decision variables
    #create model
    m = cp.Model()  

    #add constraints
    add_row_cols(m, Q, n)    
    add_region(m, Q, n, regions)      
    add_adjacent(m, Q, n)  

    #find solution
    if not m.solve():
        return ("No solution", None)

    solution = Q.value()
    add_unique(m, Q, n, solution)
    if m.solve():
        return ("Solution not unique", solution)
    return ("Unique solution", solution)

def add_row_cols(m, Q, n):
    """ Adding one queen per row and column contraint. row and col sums must be 1 """
    for i in range(n):
        m += (cp.sum(Q[i, :]) == 1)
        m += (cp.sum(Q[:, i]) == 1) 

def add_region(m, Q, n, regions):
    """ Adding one queen per region constraint. region sum must be 1 """
    for k in range(n):
        m += (cp.sum(Q[regions == k]) == 1)

def add_adjacent(m, Q, n):
    """ Adding adjancency constraint. No diagonal queens(we already check horizontal and vertical adjacency with 
    row/col sum constraint). Adding constraints from grid top to bottom to avoid redundancy """
    for i in range(n - 1): #dont need to check bottom row
        for j in range(n):
            if j != 0:  #if its not the first column
                m += Q[i, j].implies(~Q[i+1, j-1]) #queen implies not queen bottom diagonal left
            if j != n - 1:
                m += Q[i, j].implies(~Q[i+1, j+1]) #queen implies not queen bottom diagonal right

def add_unique(m, Q, n, solution):
    """ Adding unique solution constraint. There must only be one solution """
    m += (cp.sum(Q[solution]) < n) #"< n queens fall on the same n cells as this solution