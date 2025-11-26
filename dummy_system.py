import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List

NUM_AGENTS = 10


@dataclass
class Message:
    sender_id: str
    number: float


@dataclass
class NumberAgent:
    number: float
    identifier: str = field(default_factory=lambda: str(uuid.uuid4()))

    def create_message(self) -> Message:
        return Message(sender_id=self.identifier, number=self.number)


class Supervisor:
    def __init__(self, expected_messages: int) -> None:
        self.expected_messages = expected_messages
        self.received_numbers: Dict[str, float] = {}

    def receive(self, message: Message) -> None:
        self.received_numbers[message.sender_id] = message.number

    def average(self) -> float:
        if len(self.received_numbers) < self.expected_messages:
            raise RuntimeError("Supervisor did not receive enough messages to compute an average.")
        numbers = list(self.received_numbers.values())
        return sum(numbers) / len(numbers)


def main() -> None:
    supervisor = Supervisor(expected_messages=NUM_AGENTS)
    agents: List[NumberAgent] = []

    for _ in range(NUM_AGENTS):
        number = random.randint(-1000, 1000)
        agents.append(NumberAgent(number=number))

    random.shuffle(agents)

    for agent in agents:
        message = agent.create_message()
        supervisor.receive(message)
        print(f"Agent {agent.identifier} sent number {agent.number}")

    average = supervisor.average()
    print(f"Average from {NUM_AGENTS} agents: {average}")


if __name__ == "__main__":
    main()
