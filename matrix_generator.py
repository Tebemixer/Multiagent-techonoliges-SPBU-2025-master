from typing import List
def generate_adjacency_matrix(count: int) -> List[List[int]]:
    if count <= 1:
        return [[0]]

    matrix = [[0 for _ in range(count)] for _ in range(count)]
    for index in range(count-1):
        matrix[index][index+1] = 1
        matrix[index+1][index] = 1
    return matrix

if __name__=='__main__':
    print(generate_adjacency_matrix(5))