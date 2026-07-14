import cpmpy as cp
import numpy as np

from solver.puzzle import Puzzle

#exaple puzzle
puzzle = Puzzle([
            [0, 0, 1],
            [0, 2, 1],
            [2, 2, 1],
        ])

n = puzzle.n

Q = cp.boolvar(shape=(n, n)) #n x n numpy array of boolean decision variables
m = cp.Model()                

#add constraints to model

#row and col sums must be 1; one queen per row and column

#region sum must be 1; one queen per region

#no diagonal queens(we already check horizontal and 
#vertical adjacency with row col sum constraint)


solution_exists = m.solve()
Q.value()  