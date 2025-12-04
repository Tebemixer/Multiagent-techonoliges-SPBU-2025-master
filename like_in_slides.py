import random
from typing import List, Dict, Tuple
import copy
from matrix_generator import random_connected_adj_matrix
alpha = 0.1           # шаг протокола
MAX_DELAY = 2         # максимум задержки (0,1,2 такта)
NOISE_STD = 0.5       # дисперсия шума измерений
LINK_FAIL_PROB = 0.2  # вероятность, что линк "выключился" в этом такте
NEIGHBOR_MESSAGE_COST = 10
SUPERVISOR_MESSAGE_COST = 1000

class VotingAgent:
    """
    Агент для локального голосования.
    Хранит только своё состояние x_i^t.
    """
    def __init__(self, idx: int, x0: float) -> None:
        self.idx = idx
        self.x = x0
        self.neighbors: List["VotingAgent"] = []
        # история состояний для моделирования задержек у "коррапченных" агентов
        self.history: List[float] = [x0]
        self.potratil = 0

    def set_neighbors(self, neighbors: List["VotingAgent"]) -> None:
        self.neighbors = neighbors

    def step(self) -> None:
        """
        Один шаг протокола *без* шума и задержек.
        y_ii = x_i, y_ij = x_j, b_ij = 1 если есть ребро.
        x_i^{t+1} = x_i^t + alpha * sum_j (y_ij - y_ii)
        """
        y_ii = self.x
        control = 0.0

        for nbr in self.neighbors:
            y_ij = nbr.x          # идеальное измерение
            control += (y_ij - y_ii)

        u_i = alpha * control
        self.x = self.x + u_i     # w_i^t = 0
        self.history.append(self.x)


class CorruptedVotingAgent(VotingAgent):
    """
    Агент с шумом, задержками и пропадающими линками.
    Формула:
    u_i^t = alpha * sum_j b_ij^t (y_ij^t - y_ii^t)
    x_i^{t+1} = x_i^t + u_i^t + w_i^t  (здесь w_i^t = 0).
    """
    def __init__(self, idx: int, x0: float) -> None:
        super().__init__(idx, x0)

    def _noisy(self, value: float) -> float:
        return value + random.gauss(0.0, NOISE_STD)

    def get_delayed_state(self, agent: "CorruptedVotingAgent") -> float:
        """
        Выбираем случайную задержку
        и возвращаем x_j^{t-d} из истории соседа.
        Если история короче — берём самый ранний доступный элемент.
        """
        d = random.randint(0, MAX_DELAY)
        hist = agent.history
        idx = max(0, len(hist) - 1 - d)
        return hist[idx]

    def step(self) -> None:
        """
        Один шаг с шумом, задержками и переключающимися линками.
        """
        # собственное измерение: y_ii^t = x_i^t + v_ii^t
        y_ii = self._noisy(self.x)

        control = 0.0
        for nbr in self.neighbors:
            if random.random() < LINK_FAIL_PROB:
                continue

            # запаздывающее состояние соседа
            xj_delayed = self.get_delayed_state(nbr)
            # зашумлённое измерение: y_ij^t = x_j^{t-d} + v_ij^t
            y_ij = self._noisy(xj_delayed)

            #вес
            b_ij = 1.0

            control += b_ij * (y_ij - y_ii)
            self.potratil+=NEIGHBOR_MESSAGE_COST

        u_i = alpha * control
        # возмущение w_i^t со средним 0
        self.x = self.x + u_i
        self.history.append(self.x)

def simulate_local_voting(
    adjacency_matrix: List[List[int]],
    corrupted: bool,
    num_iterations: int = 100
) -> Tuple[List[float], List[List[float]]]:
    n = len(adjacency_matrix)
    x0 = [float(i) for i in range(n)]

    if corrupted:
        agents = [CorruptedVotingAgent(i, x0[i]) for i in range(n)]
    else:
        agents = [VotingAgent(i, x0[i]) for i in range(n)]

    for i, agent in enumerate(agents):
        neighbors = [
            agents[j] for j, connected in enumerate(adjacency_matrix[i])
            if connected
        ]
        agent.set_neighbors(neighbors)


    true_avg = sum(x0) / n
    trajectories = [[agent.x] for agent in agents]
    summa = 0
    for t in range(num_iterations):
        print(f'Итерация {t+1}')
        for agent in agents:
            agent.step()

        for i, agent in enumerate(agents):
            trajectories[i].append(agent.x)
            print(f'Агент {i} думает, что среднее {agent.x}')
    for agent in agents:
        summa += agent.potratil

    return [true_avg], trajectories, summa


def main() -> None:
    N = 5
    adjacency_matrix = random_connected_adj_matrix(N)
    print("Матрица смежности:")
    for row in adjacency_matrix:
        print(row)

    true_avg, traj, summa = simulate_local_voting(adjacency_matrix, corrupted=True, num_iterations=100)

    print("Истинное среднее:", true_avg[0])
    print("Финальные значения агентов:")
    for i, history in enumerate(traj):
        print(f"агент {i}: x_T = {history[-1]}")
    print(f'Итоговая сумма {summa+SUPERVISOR_MESSAGE_COST}')


if __name__ == '__main__':
    main()
