import asyncio
import json
import random
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional
from matrix_generator import generate_adjacency_matrix
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template


NUM_AGENTS = 10
AGENT_DOMAIN = "localhost"
DEFAULT_PASSWORD = "password"
KNOWLEDGE_CONVERSATION = "knowledge-sharing"
REPORT_CONVERSATION = "final-report"
NEIGHBOR_MESSAGE_COST = 10
SUPERVISOR_MESSAGE_COST = 1000
RECEIVE_WINDOW = 0.5


class CostTracker:
    def __init__(self) -> None:
        self._total_cost = 0
        self._lock = asyncio.Lock()

    async def add(self, amount: int) -> None:
        async with self._lock:
            self._total_cost += amount

    async def total(self) -> int:
        async with self._lock:
            return self._total_cost


COST_TRACKER = CostTracker()
STOP_EVENT = asyncio.Event()
START_EVENT = asyncio.Event()
STOP_LOCK = asyncio.Lock()


class IterationCoordinator:
    def __init__(self, agent_count: int) -> None:
        self.agent_count = agent_count
        self.iteration = 0
        self.send_event = asyncio.Event()
        self.process_event = asyncio.Event()
        self.lock = asyncio.Lock()
        self.send_counter = agent_count
        self.process_counter = agent_count
        self.any_updates = False

    async def start(self) -> None:
        async with self.lock:
            self.iteration = 1
            self.send_counter = self.agent_count
            self.process_counter = self.agent_count
            self.any_updates = False
            self.send_event.clear()
            self.process_event.clear()
            self.send_event.set()

    async def wait_for_send_phase(self) -> int:
        await self.send_event.wait()
        return self.iteration

    async def notify_send_completed(self) -> None:
        async with self.lock:
            if STOP_EVENT.is_set():
                return
            self.send_counter -= 1
            if self.send_counter == 0:
                self.send_event.clear()
                self.process_event.set()

    async def wait_for_process_phase(self) -> int:
        await self.process_event.wait()
        return self.iteration

    async def notify_process_completed(self, updated: bool) -> None:
        async with self.lock:
            self.process_counter -= 1
            if STOP_EVENT.is_set():
                if self.process_counter == 0:
                    self.send_event.set()
                    self.process_event.clear()
                return

            if updated:
                self.any_updates = True

            if self.process_counter == 0:
                if self.any_updates:
                    self.iteration += 1
                    self.send_counter = self.agent_count
                    self.process_counter = self.agent_count
                    self.any_updates = False
                    self.process_event.clear()
                    self.send_event.set()
                else:
                    STOP_EVENT.set()
                    self.send_event.set()


COORDINATOR = IterationCoordinator(NUM_AGENTS)


@dataclass
class AgentConfig:
    username: str
    password: str
    number: float

    @property
    def jid(self) -> str:
        return f"{self.username}@{AGENT_DOMAIN}"


class NumberAgent(Agent):
    def __init__(
        self,
        jid: str,
        password: str,
        number: float,
        supervisor_jid: str,
        neighbor_jids: List[str],
        lead_printer: bool = False,
    ) -> None:
        super().__init__(jid, password)
        self.supervisor_jid = supervisor_jid
        self.number = number
        self.neighbor_jids = neighbor_jids
        self.lead_printer = lead_printer
        self.identifier = str(uuid.uuid4())
        self.knowledge: Dict[str, float] = {self.identifier: self.number}

    async def setup(self) -> None:
        behaviour = self.KnowledgeExchangeBehaviour()
        self.add_behaviour(behaviour)

    def knowledge_payload(self, iteration: int) -> str:
        payload = {
            "agent_id": self.identifier,
            "knowledge": self.knowledge,
            "iteration": iteration,
        }
        return json.dumps(payload)

    def merge_knowledge(self, incoming: Dict[str, float]) -> bool:
        updated = False
        for agent_id, number in incoming.items():
            if agent_id not in self.knowledge:
                self.knowledge[agent_id] = float(number)
                updated = True
        return updated

    async def prepare_report(self) -> Optional[str]:
        async with STOP_LOCK:
            if STOP_EVENT.is_set():
                return None
            STOP_EVENT.set()
            average = sum(self.knowledge.values()) / len(self.knowledge)
            payload = {
                "agent_id": self.identifier,
                "average": average,
                "known_agents": len(self.knowledge),
            }
            return json.dumps(payload)

    class KnowledgeExchangeBehaviour(CyclicBehaviour):
        async def run(self) -> None:
            if not START_EVENT.is_set():
                await START_EVENT.wait()

            if STOP_EVENT.is_set():
                self.kill()
                await self.agent.stop()
                return

            iteration = await COORDINATOR.wait_for_send_phase()

            if STOP_EVENT.is_set():
                self.kill()
                await self.agent.stop()
                return

            if self.agent.lead_printer:
                print(f"Iteration {iteration}")

            payload = self.agent.knowledge_payload(iteration)
            for neighbor in self.agent.neighbor_jids:
                msg = Message(to=neighbor)
                msg.set_metadata("conversation", KNOWLEDGE_CONVERSATION)
                msg.body = payload
                await COST_TRACKER.add(NEIGHBOR_MESSAGE_COST)
                await self.send(msg)

            await COORDINATOR.notify_send_completed()

            await COORDINATOR.wait_for_process_phase()

            loop = asyncio.get_running_loop()
            deadline = loop.time() + RECEIVE_WINDOW
            updated = False
            while not STOP_EVENT.is_set():
                timeout = deadline - loop.time()
                if timeout <= 0:
                    break
                msg = await self.receive(timeout=timeout)
                if msg is None:
                    break
                if msg.metadata.get("conversation") != KNOWLEDGE_CONVERSATION:
                    continue
                try:
                    incoming_payload = json.loads(msg.body)
                except (TypeError, json.JSONDecodeError):
                    continue
                if incoming_payload.get("iteration") != iteration:
                    continue
                incoming_knowledge = incoming_payload.get("knowledge", {})
                if self.agent.merge_knowledge(incoming_knowledge):
                    updated = True

            report_payload: Optional[str] = None
            if not updated:
                report_payload = await self.agent.prepare_report()
                if report_payload is not None:
                    msg = Message(to=self.agent.supervisor_jid)
                    msg.set_metadata("conversation", REPORT_CONVERSATION)
                    msg.body = report_payload
                    await COST_TRACKER.add(SUPERVISOR_MESSAGE_COST)
                    await self.send(msg)

            await COORDINATOR.notify_process_completed(updated)

            if report_payload is not None or STOP_EVENT.is_set():
                self.kill()
                await self.agent.stop()


class SupervisorAgent(Agent):
    def __init__(self, jid: str, password: str) -> None:
        super().__init__(jid, password)
        self.result_future: asyncio.Future[Dict[str, float]] = asyncio.get_running_loop().create_future()

    async def setup(self) -> None:
        template = Template()
        template.set_metadata("conversation", REPORT_CONVERSATION)
        behaviour = self.ReportBehaviour()
        self.add_behaviour(behaviour, template)

    class ReportBehaviour(CyclicBehaviour):
        async def run(self) -> None:
            msg = await self.receive(timeout=1)
            if msg is None:
                return
            try:
                payload = json.loads(msg.body)
            except (TypeError, json.JSONDecodeError):
                return
            if not self.agent.result_future.done():
                self.agent.result_future.set_result(payload)
            self.kill()
            await self.agent.stop()


async def main() -> None:
    adjacency_matrix = generate_adjacency_matrix(NUM_AGENTS)
    print("Adjacency matrix:")
    for row in adjacency_matrix:
        print(row)

    supervisor_username = "supervisor"
    supervisor_config = AgentConfig(
        username=supervisor_username,
        password=DEFAULT_PASSWORD,
        number=0.0,
    )

    supervisor = SupervisorAgent(
        jid=supervisor_config.jid,
        password=supervisor_config.password,
    )
    await supervisor.start(auto_register=True)

    agent_configs: List[AgentConfig] = []
    for index in range(NUM_AGENTS):
        config = AgentConfig(
            username=f"graph_agent_{index}",
            password=DEFAULT_PASSWORD,
            number=index,
        )
        agent_configs.append(config)

    agents: List[NumberAgent] = []
    for index, config in enumerate(agent_configs):
        neighbors = [
            agent_configs[neighbor_index].jid
            for neighbor_index, connected in enumerate(adjacency_matrix[index])
            if connected
        ]
        agent = NumberAgent(
            jid=config.jid,
            password=config.password,
            number=config.number,
            supervisor_jid=supervisor_config.jid,
            neighbor_jids=neighbors,
            lead_printer=(index == 0),
        )
        agents.append(agent)
        print(f"Agent {agent.identifier} initialized with number {agent.number}")
        await agent.start(auto_register=True)

    await COORDINATOR.start()
    START_EVENT.set()

    try:
        await STOP_EVENT.wait()
        report = await supervisor.result_future
        total_cost = await COST_TRACKER.total()
        reporter = report.get("agent_id")
        average = report.get("average")
        known_agents = report.get("known_agents")
        print(f"Agent {reporter} reported average {average} over {known_agents} agents.")
        print(f"Total communication cost: ${total_cost}")
    finally:
        for agent in agents:
            if agent.is_alive():
                await agent.stop()
        if supervisor.is_alive():
            await supervisor.stop()


if __name__ == "__main__":
    asyncio.run(main())
