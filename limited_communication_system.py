import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from matrix_generator import generate_adjacency_matrix

NUM_AGENTS = 5
NEIGHBOR_MESSAGE_COST = 10
SUPERVISOR_MESSAGE_COST = 1000


@dataclass
class KnowledgeMessage:
    sender_id: str
    receiver_id: str
    iteration: int
    knowledge: Dict[str, float]


@dataclass
class SilenceMessage:
    sender_id: str
    receiver_id: str


@dataclass
class SupervisorReport:
    agent_id: str
    average: float
    known_agents: int




class NumberAgent():
    def __init__(self,   number: float) -> None:
        self.number = number
        self.identifier = str(uuid.uuid4())
        self.neighbors = None
        self.knowledge= {}
        self.is_silent = False
        self.pending_report = False
        self.knowledge = {self.identifier: float(self.number)}
        self.buffer = []
        self.death_list = []
        self.death_real = []

    def set_neighbors(self, neighbors: List["NumberAgent"]) -> None:
        self.neighbors = neighbors

    
    def merge_knowledge(self,destination: Dict[str, float], incoming: Dict[str, float]) -> bool:
        """Сливает числовые знания из incoming в destination.
        Возвращает True, если появились новые ключи.
        """
        updated = False
        for agent_id, number in incoming.items():
            if agent_id not in destination:
                destination[agent_id] = float(number)
                updated = True
        return updated
    
    def send_messages(self):
        if self.is_silent:
            return 0
        cost = 0
        if len(self.death_real)>0:
            for neighbor in self.neighbors:
                if neighbor.identifier not in self.death_real:
                    neighbor.death_list.append(self.identifier)
                    cost+=NEIGHBOR_MESSAGE_COST
            self.is_silent = True
            return cost


        if self.pending_report:
            average = sum(self.knowledge.values()) / (len(self.knowledge.keys()))
            for neighbor in self.neighbors:
                neighbor.death_list.append(self.identifier)
                cost+=NEIGHBOR_MESSAGE_COST
            self.is_silent=True
            print(f"{self.identifier} отправил в центр {average}")
            return SUPERVISOR_MESSAGE_COST + cost
        


        for neighbor in self.neighbors:
            neighbor.buffer.append(dict(self.knowledge))
            cost+=NEIGHBOR_MESSAGE_COST
        return cost
    
    def process_messages(self):
        if self.is_silent:
            return None
        update = False

        if len(self.death_list)>0:
            self.death_real = self.death_list.copy()
            return None
        for message in self.buffer:
            
            update = self.merge_knowledge(self.knowledge,message) or update
        self.buffer.clear()
        if not(update):
            self.pending_report = True






    





def simulate(adjacency_matrix: List[List[int]]) -> int:
    agents = [
        NumberAgent(number=index)
        for index in range(len(adjacency_matrix))
    ]

    for index, agent in enumerate(agents):
        neighbors = [
            agents[neighbor_index]
            for neighbor_index, connected in enumerate(adjacency_matrix[index])
            if connected
        ]
        agent.set_neighbors(neighbors)
        print(f"Agent {agent.identifier} initialized with number {agent.number}")

    iteration = 1
    total_cost = 0
    active_agents: List[NumberAgent] = list(agents)
    agent_by_id = {agent.identifier: agent for agent in agents}
    while True:
        print('Iteration ',iteration)
        counter_sleepers=0
        count = 0
        for agent_id in agent_by_id:
            if agent_by_id[agent_id].is_silent:
                counter_sleepers+=1
                continue
            buffer = agent_by_id[agent_id].send_messages()
            count += buffer
            total_cost+=buffer
        for agent_id in agent_by_id:
            agent_by_id[agent_id].process_messages()
        if counter_sleepers==NUM_AGENTS:
            break
        iteration+=1
        print(f'За итерацию потрачено {count}')
    

    return total_cost


def main() -> None:
    adjacency_matrix = generate_adjacency_matrix(NUM_AGENTS)
    print("Adjacency matrix:")
    for row in adjacency_matrix:
        print(row)

    total_cost = simulate(adjacency_matrix)
    print(f"Total communication cost: ${total_cost}")


if __name__ == "__main__":
    main()
