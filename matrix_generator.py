from typing import List
import random
import numpy as np

def generate_adjacency_matrix(count: int) -> List[List[int]]:
    if count <= 1:
        return [[0]]

    matrix = [[0 for _ in range(count)] for _ in range(count)]
    for index in range(count-1):
        matrix[index][index+1] = 1
        matrix[index+1][index] = 1
    return matrix

def random_connected_adj_matrix(n, extra_edges=0) -> List[List[int]]:
    A = [[0]*n for _ in range(n)]
    
    # 1) Строим случайное дерево: последовательно присоединяем новую вершину к одной из старых
    for v in range(1, n):
        u = random.randrange(0, v)
        A[u][v] = A[v][u] = 1

    # 2) Собираем все отсутствующие рёбра
    possible_edges = [
        (i, j)
        for i in range(n)
        for j in range(i+1, n)
        if A[i][j] == 0
    ]
    random.shuffle(possible_edges)
    
    for (u, v) in possible_edges[:extra_edges]:
        A[u][v] = A[v][u] = 1
    
    return A


if __name__ == '__main__':
    import networkx as nx
    A = random_connected_adj_matrix(6, extra_edges=4)
    for row in A:
        print(row)
    
    A_np = np.array(A, dtype=int)
    G = nx.from_numpy_array(A_np)
    print(nx.is_connected(G))