import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Dict, List
import random
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message
from spade.template import Template


NUM_AGENTS = 10
AGENT_DOMAIN = "localhost"
DEFAULT_PASSWORD = "password"
CONVERSATION_ID = "average-computation"


@dataclass
class AgentConfig:
    username: str
    password: str
    number: float

    @property
    def jid(self) -> str:
        return f"{self.username}@{AGENT_DOMAIN}"


class NumberAgent(Agent):
    def __init__(self, jid: str, password: str, number: float, supervisor_jid: str) -> None:
        super().__init__(jid, password)
        self.supervisor_jid = supervisor_jid
        self.number = number
        self.identifier = str(uuid.uuid4())

    async def setup(self) -> None:
        behaviour = self.SendNumberBehaviour()
        self.add_behaviour(behaviour)

    class SendNumberBehaviour(OneShotBehaviour):
        async def run(self) -> None:
            payload = json.dumps(
                {
                    "id": self.agent.identifier,
                    "number": self.agent.number,
                }
            )
            msg = Message(to=self.agent.supervisor_jid)
            msg.set_metadata("performative", "inform")
            msg.set_metadata("conversation", CONVERSATION_ID)
            msg.body = payload
            await self.send(msg)
            await self.agent.stop()


class SupervisorAgent(Agent):
    def __init__(self, jid: str, password: str, expected_messages: int) -> None:
        super().__init__(jid, password)
        self.expected_messages = expected_messages
        self.received_numbers: Dict[str, float] = {}
        self.average_future: asyncio.Future[float] = asyncio.get_event_loop().create_future()

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("conversation", CONVERSATION_ID)
        behaviour = self.CollectNumbersBehaviour()
        self.add_behaviour(behaviour, template)

    class CollectNumbersBehaviour(CyclicBehaviour):
        async def run(self) -> None:
            msg = await self.receive(timeout=10)
            if msg is None:
                if not self.agent.average_future.done():
                    self.agent.average_future.set_exception(
                        TimeoutError("Supervisor timed out while waiting for agent messages.")
                    )
                await self.agent.stop()
                return

            try:
                payload = json.loads(msg.body)
            except json.JSONDecodeError:
                return

            agent_id = payload.get("id")
            number = payload.get("number")
            if agent_id is None or number is None:
                return

            self.agent.received_numbers[agent_id] = float(number)

            if len(self.agent.received_numbers) >= self.agent.expected_messages:
                numbers = list(self.agent.received_numbers.values())
                average = sum(numbers) / len(numbers)
                if not self.agent.average_future.done():
                    self.agent.average_future.set_result(average)
                await self.agent.stop()


async def main() -> None:
    supervisor_username = "supervisor"
    supervisor_config = AgentConfig(
        username=supervisor_username,
        password=DEFAULT_PASSWORD,
        number=0.0,
    )

    supervisor = SupervisorAgent(
        jid=supervisor_config.jid,
        password=supervisor_config.password,
        expected_messages=NUM_AGENTS,
    )
    await supervisor.start(auto_register=True)

    agent_configs: List[AgentConfig] = []
    for index in range(NUM_AGENTS):
        config = AgentConfig(
            username=f"number_agent_{index}",
            password=DEFAULT_PASSWORD,
            number=random.randint(-1000,1000),
        )
        agent_configs.append(config)

    await asyncio.sleep(1)

    agents: List[NumberAgent] = []
    for config in agent_configs:
        agent = NumberAgent(
            jid=config.jid,
            password=config.password,
            number=config.number,
            supervisor_jid=supervisor_config.jid,
        )
        agents.append(agent)
        print(f"Agent {agent.identifier} sending number {agent.number}")
        await agent.start(auto_register=True)

    try:
        average = await supervisor.average_future
        print(f"Average from {NUM_AGENTS} agents: {average}")
    finally:
        for agent in agents:
            if agent.is_alive():
                await agent.stop()
        if supervisor.is_alive():
            await supervisor.stop()


if __name__ == "__main__":
    asyncio.run(main())
