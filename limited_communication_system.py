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
class SupervisorReport:
    agent_id: str
    average: float
    known_agents: int


@dataclass
class NumberAgent:
    number: float
    lead_printer: bool = False
    identifier: str = field(default_factory=lambda: str(uuid.uuid4()))
    neighbors: List["NumberAgent"] = field(default_factory=list)
    knowledge: Dict[str, float] = field(init=False)

    def __post_init__(self) -> None:
        self.knowledge = {self.identifier: float(self.number)}

    def set_neighbors(self, neighbors: List["NumberAgent"]) -> None:
        self.neighbors = neighbors

    def compose_messages(self, iteration: int) -> List[KnowledgeMessage]:
        payload = dict(self.knowledge)
        messages: List[KnowledgeMessage] = []
        for neighbor in self.neighbors:
            messages.append(
                KnowledgeMessage(
                    sender_id=self.identifier,
                    receiver_id=neighbor.identifier,
                    iteration=iteration,
                    knowledge=payload,
                )
            )
        return messages

    def process_messages(self, iteration: int, messages: List[KnowledgeMessage]) -> bool:
        updated = False
        for message in messages:
            if message.iteration != iteration:
                continue
            for agent_id, number in message.knowledge.items():
                if agent_id not in self.knowledge:
                    self.knowledge[agent_id] = float(number)
                    updated = True
        return updated

    def prepare_report(self) -> SupervisorReport:
        average = sum(self.knowledge.values()) / max(len(self.knowledge), 1)
        return SupervisorReport(
            agent_id=self.identifier,
            average=average,
            known_agents=len(self.knowledge),
        )


class Supervisor:
    def __init__(self) -> None:
        self.report: Optional[SupervisorReport] = None

    def receive_report(self, report: SupervisorReport) -> None:
        if self.report is None:
            self.report = report


def simulate(adjacency_matrix: List[List[int]]) -> Tuple[SupervisorReport, int]:
    supervisor = Supervisor()
    agents = [
        NumberAgent(number=index, lead_printer=(index == 0))
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

    while supervisor.report is None and active_agents:
        lead_agent = next((agent for agent in active_agents if agent.lead_printer), None)
        if lead_agent is not None:
            print(f"Iteration {iteration}")

        outgoing_messages: List[KnowledgeMessage] = []
        for agent in active_agents:
            outgoing_messages.extend(agent.compose_messages(iteration))

        total_cost += len(outgoing_messages) * NEIGHBOR_MESSAGE_COST

        inboxes: Dict[str, List[KnowledgeMessage]] = {agent.identifier: [] for agent in active_agents}
        for message in outgoing_messages:
            if message.receiver_id in inboxes:
                inboxes[message.receiver_id].append(message)

        next_active_agents: List[NumberAgent] = []
        for agent in active_agents:
            inbox = inboxes.get(agent.identifier, [])
            updated = agent.process_messages(iteration, inbox)
            if updated:
                next_active_agents.append(agent)
            else:
                if supervisor.report is None:
                    report = agent.prepare_report()
                    supervisor.receive_report(report)
                    total_cost += SUPERVISOR_MESSAGE_COST

        if supervisor.report is not None:
            break

        if not next_active_agents:
            # All agents stalled simultaneously; the first active agent reports.
            report = active_agents[0].prepare_report()
            supervisor.receive_report(report)
            total_cost += SUPERVISOR_MESSAGE_COST
            break

        active_agents = next_active_agents
        iteration += 1

    if supervisor.report is None:
        raise RuntimeError("Supervisor did not receive a final report.")

    return supervisor.report, total_cost


def main() -> None:
    adjacency_matrix = generate_adjacency_matrix(NUM_AGENTS)
    print("Adjacency matrix:")
    for row in adjacency_matrix:
        print(row)

    report, total_cost = simulate(adjacency_matrix)
    print(
        f"Agent {report.agent_id} reported average {report.average} over {report.known_agents} agents."
    )
    print(f"Total communication cost: ${total_cost}")


if __name__ == "__main__":
    main()
