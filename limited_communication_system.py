import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import copy
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


def noisy(values):
    """Возвращает копию values со случайным множителем в пределах ±10%."""
    noise = random.gauss(0, 0.03)
    noise = max(-0.1, min(0.1, noise))
    multiplier = 1 + noise

    if isinstance(values, (int, float)):
        return values * multiplier

    cloned = copy.deepcopy(values)
    if isinstance(cloned, list):
        for index, value in enumerate(cloned):
            cloned[index] = value * multiplier
        return cloned

    if isinstance(cloned, dict):
        for key, value in cloned.items():
            cloned[key] = noisy(value)
        return cloned

    return cloned



class NumberAgent():
    def __init__(self,   number: float) -> None:
        self.number = number
        self.identifier = str(uuid.uuid4())
        self.neighbors = None
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


class CorruptedNumberAgent(NumberAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.bash = 0
        self._in_action = True
        self.delayed_meassages = [[],[]]
        self.delayed_death = [[],[]]
        self.knowledge = {self.identifier: [float(self.number)]}

    def merge_knowledge(self,destination: Dict[str, List[float]], incoming: Dict[str, List[float]]) -> bool:
        """Сливает списки наблюдений, новые элементы считаем знанием."""
        updated = False
        for agent_id, values in incoming.items():
            if agent_id not in destination:
                destination[agent_id] = list(values)
                updated = True
            else:
                before = len(destination[agent_id])
                destination[agent_id].extend(values)
                if len(destination[agent_id]) != before:
                    updated = True
        return updated
    
    def send_messages(self):
        if self.is_silent:
            return 0
        
        if self.bash>=1:
            self.bash-=1


        if self.bash> 0:
            return 0 


        cost = 0
        
        if len(self.death_real)>0:
            for neighbor in self.neighbors:
                if neighbor.identifier not in self.death_real:
                    unluck = random.randint(1,10)
                    if unluck ==1:
                        unluck = random.randint(1,10)
                        if unluck >=3:
                            neighbor.delayed_death[0].append(self.identifier)
                        else:
                            neighbor.delayed_death[1].append(self.identifier)
                    else:
                        neighbor.death_list.append(self.identifier)
                    cost+=NEIGHBOR_MESSAGE_COST
            self.is_silent = True
            return cost


        if self.pending_report:
            per_agent_avg = [
                sum(values) / len(values)
                for values in self.knowledge.values()
                if len(values) > 0
            ]
            average = sum(per_agent_avg) / len(per_agent_avg) if per_agent_avg else 0.0
            for neighbor in self.neighbors:
                unluck = random.randint(1,10)
                if unluck ==1:
                    unluck = random.randint(1,10)
                    if unluck >=3:
                        neighbor.delayed_death[0].append(self.identifier)
                    else:
                        neighbor.delayed_death[1].append(self.identifier)
                else:
                    neighbor.death_list.append(self.identifier)
                cost+=NEIGHBOR_MESSAGE_COST
            self.is_silent=True
            print(f"{self.identifier} отправил в центр {average}")
            return SUPERVISOR_MESSAGE_COST + cost
        


        for neighbor in self.neighbors:
            corrupted_dict = copy.deepcopy(dict(self.knowledge))
            for x in corrupted_dict:
                corrupted_dict[x] = noisy(corrupted_dict[x])
            unluck = random.randint(1,10)
            if unluck ==1:
                unluck = random.randint(1,10)
                if unluck >=3:
                    neighbor.delayed_meassages[0].append(dict(corrupted_dict))
                else:
                    neighbor.delayed_meassages[1].append(dict(corrupted_dict))
            else:
                neighbor.buffer.append(dict(corrupted_dict))
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



        for message in self.delayed_meassages[0]:
            self.buffer.append(copy.deepcopy(message))
        self.delayed_meassages[0].clear()
        for message in self.delayed_meassages[1]:
            self.delayed_meassages[0].append(copy.deepcopy(message))
        self.delayed_meassages[1].clear()

        for message in self.delayed_death[0]:
            self.death_list.append(copy.deepcopy(message))
        self.delayed_death[0].clear()
        for message in self.delayed_death[1]:
            self.delayed_death[0].append(copy.deepcopy(message))
        self.delayed_death[1].clear()



    





def simulate(adjacency_matrix: List[List[int]], normal: bool) -> int:
    if normal:
        agents = [
            NumberAgent(number=index)
            for index in range(len(adjacency_matrix))
        ]
    else:
        agents = [
            CorruptedNumberAgent(number=index)
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

    total_cost = simulate(adjacency_matrix, False)
    print(f"Total communication cost: ${total_cost}")


if __name__ == "__main__":
    main()
