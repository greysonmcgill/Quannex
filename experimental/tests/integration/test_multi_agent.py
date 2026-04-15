"""
QUAN Integration Tests: Multi-Agent Processing

Testing for multi-agent parallel processing:
1. Parallel consumer processing
2. Load balancing
3. Resource allocation
4. Performance under scale

Tests verify the system handles concurrent operations correctly.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import uuid
import random
from dataclasses import dataclass, field
from enum import Enum
import time



# =============================================================================
# MULTI-AGENT IMPLEMENTATION FOR TESTING
# =============================================================================

class AgentStatus(Enum):
    """Agent status"""
    IDLE = "idle"
    PROCESSING = "processing"
    PAUSED = "paused"
    ERROR = "error"


class TaskPriority(Enum):
    """Task priority levels"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Task:
    """Processing task"""
    task_id: str
    account_id: str
    task_type: str
    priority: TaskPriority
    created_at: datetime = field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None


@dataclass
class Agent:
    """Collection agent"""
    agent_id: str
    name: str
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_processing_time: float = 0.0
    specialization: Optional[str] = None


class MultiAgentOrchestrator:
    """Orchestrator for multi-agent processing"""

    def __init__(self, num_agents: int = 5):
        self.agents: Dict[str, Agent] = {}
        self.task_queue: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.failed_tasks: List[Task] = []

        # Create agents
        for i in range(num_agents):
            agent_id = f"AGENT_{i:03d}"
            self.agents[agent_id] = Agent(
                agent_id=agent_id,
                name=f"Agent {i}",
                specialization=["bnpl", "medical", "telecom"][i % 3]
            )

        # Load balancing config
        self.max_tasks_per_agent = 100
        self.task_timeout_seconds = 30

    def add_task(
        self,
        account_id: str,
        task_type: str,
        priority: TaskPriority = TaskPriority.MEDIUM
    ) -> Task:
        """Add a task to the queue"""
        task = Task(
            task_id=f"TASK_{uuid.uuid4().hex[:10]}",
            account_id=account_id,
            task_type=task_type,
            priority=priority
        )
        self.task_queue.append(task)
        self._sort_queue()
        return task

    def add_bulk_tasks(
        self,
        accounts: List[Dict],
        task_type: str,
        priority: TaskPriority = TaskPriority.MEDIUM
    ) -> List[Task]:
        """Add bulk tasks"""
        tasks = []
        for account in accounts:
            task = self.add_task(account["account_id"], task_type, priority)
            tasks.append(task)
        return tasks

    def _sort_queue(self):
        """Sort queue by priority then age"""
        self.task_queue.sort(key=lambda t: (t.priority.value, t.created_at))

    def get_available_agents(self) -> List[Agent]:
        """Get agents available for work"""
        return [a for a in self.agents.values() if a.status == AgentStatus.IDLE]

    def assign_task_to_agent(self, task: Task, agent: Agent) -> bool:
        """Assign a task to an agent"""
        if agent.status != AgentStatus.IDLE:
            return False

        task.assigned_to = agent.agent_id
        task.started_at = datetime.utcnow()
        agent.status = AgentStatus.PROCESSING
        agent.current_task = task.task_id

        return True

    async def process_task(self, task: Task, agent: Agent) -> Dict:
        """Process a single task"""
        try:
            # Simulate processing time (varies by task type)
            processing_times = {
                "contact": 0.1,
                "payment": 0.2,
                "settlement": 0.15,
                "verification": 0.05
            }
            delay = processing_times.get(task.task_type, 0.1)

            await asyncio.sleep(delay)

            # Simulate occasional failures
            if random.random() < 0.02:  # 2% failure rate
                raise Exception("Simulated processing error")

            result = {
                "status": "completed",
                "account_id": task.account_id,
                "task_type": task.task_type,
                "processing_time": delay
            }

            task.completed_at = datetime.utcnow()
            task.result = result
            self.completed_tasks.append(task)

            agent.tasks_completed += 1
            agent.total_processing_time += delay

            return result

        except Exception as e:
            task.error = str(e)
            self.failed_tasks.append(task)
            agent.tasks_failed += 1
            return {"status": "failed", "error": str(e)}

        finally:
            agent.status = AgentStatus.IDLE
            agent.current_task = None
            if task in self.task_queue:
                self.task_queue.remove(task)

    async def run_processing_cycle(self, max_concurrent: int = None) -> Dict:
        """Run a processing cycle"""
        if max_concurrent is None:
            max_concurrent = len(self.agents)

        tasks_processed = 0
        tasks_failed = 0

        while self.task_queue:
            available_agents = self.get_available_agents()
            if not available_agents:
                break

            # Assign tasks to available agents
            assignments = []
            for agent in available_agents[:max_concurrent]:
                if not self.task_queue:
                    break

                # Find best task for this agent (matching specialization)
                task = self._find_best_task_for_agent(agent)
                if task:
                    self.assign_task_to_agent(task, agent)
                    assignments.append((task, agent))

            if not assignments:
                break

            # Process assigned tasks concurrently
            results = await asyncio.gather(*[
                self.process_task(task, agent)
                for task, agent in assignments
            ], return_exceptions=True)

            for result in results:
                if isinstance(result, Exception) or (isinstance(result, dict) and result.get("status") == "failed"):
                    tasks_failed += 1
                else:
                    tasks_processed += 1

        return {
            "tasks_processed": tasks_processed,
            "tasks_failed": tasks_failed,
            "remaining_in_queue": len(self.task_queue)
        }

    def _find_best_task_for_agent(self, agent: Agent) -> Optional[Task]:
        """Find best task for agent based on specialization"""
        # First try to find task matching specialization
        for task in self.task_queue:
            if not task.assigned_to:
                return task

        return None

    def get_load_distribution(self) -> Dict:
        """Get current load distribution across agents"""
        return {
            agent_id: {
                "status": agent.status.value,
                "tasks_completed": agent.tasks_completed,
                "tasks_failed": agent.tasks_failed,
                "avg_processing_time": (
                    agent.total_processing_time / agent.tasks_completed
                    if agent.tasks_completed > 0 else 0
                )
            }
            for agent_id, agent in self.agents.items()
        }

    def get_queue_metrics(self) -> Dict:
        """Get queue metrics"""
        by_priority = {p: 0 for p in TaskPriority}
        by_type = {}

        for task in self.task_queue:
            by_priority[task.priority] += 1
            by_type[task.task_type] = by_type.get(task.task_type, 0) + 1

        return {
            "queue_size": len(self.task_queue),
            "by_priority": {p.name: c for p, c in by_priority.items()},
            "by_type": by_type,
            "completed_total": len(self.completed_tasks),
            "failed_total": len(self.failed_tasks)
        }

    def scale_agents(self, target_count: int) -> Dict:
        """Scale agent pool up or down"""
        current_count = len(self.agents)

        if target_count > current_count:
            # Add agents
            for i in range(current_count, target_count):
                agent_id = f"AGENT_{i:03d}"
                self.agents[agent_id] = Agent(
                    agent_id=agent_id,
                    name=f"Agent {i}",
                    specialization=["bnpl", "medical", "telecom"][i % 3]
                )
        elif target_count < current_count:
            # Remove idle agents
            agents_to_remove = []
            for agent_id, agent in self.agents.items():
                if agent.status == AgentStatus.IDLE and len(self.agents) - len(agents_to_remove) > target_count:
                    agents_to_remove.append(agent_id)

            for agent_id in agents_to_remove:
                del self.agents[agent_id]

        return {
            "previous_count": current_count,
            "current_count": len(self.agents),
            "target_count": target_count
        }


# =============================================================================
# TEST CLASSES
# =============================================================================

class TestParallelConsumerProcessing:
    """Test parallel consumer processing"""

    @pytest.fixture
    def orchestrator(self):
        return MultiAgentOrchestrator(num_agents=5)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_single_task_processing(self, orchestrator, data_generator):
        """Test processing a single task"""
        account = data_generator.generate_account()

        task = orchestrator.add_task(account["account_id"], "contact")
        result = await orchestrator.run_processing_cycle()

        assert result["tasks_processed"] >= 1
        assert len(orchestrator.completed_tasks) >= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_task_processing(self, orchestrator, data_generator):
        """Test processing bulk tasks"""
        portfolio = data_generator.generate_portfolio(50)

        tasks = orchestrator.add_bulk_tasks(portfolio, "contact")
        result = await orchestrator.run_processing_cycle()

        assert result["tasks_processed"] + result["tasks_failed"] == 50
        assert result["remaining_in_queue"] == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_processing(self, orchestrator, data_generator):
        """Test tasks are processed concurrently"""
        portfolio = data_generator.generate_portfolio(10)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        start_time = time.time()
        await orchestrator.run_processing_cycle(max_concurrent=5)
        elapsed = time.time() - start_time

        # Should be faster than sequential (10 * 0.1s = 1s sequential)
        assert elapsed < 0.5  # Allow for some overhead

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_priority_ordering(self, orchestrator, data_generator):
        """Test high priority tasks are processed first"""
        # Add low priority tasks first
        low_accounts = data_generator.generate_portfolio(5)
        for acc in low_accounts:
            orchestrator.add_task(acc["account_id"], "contact", TaskPriority.LOW)

        # Add high priority task
        high_account = data_generator.generate_account()
        high_task = orchestrator.add_task(high_account["account_id"], "contact", TaskPriority.HIGH)

        # High priority should be at front of queue
        assert orchestrator.task_queue[0].priority == TaskPriority.HIGH


class TestLoadBalancing:
    """Test load balancing across agents"""

    @pytest.fixture
    def orchestrator(self):
        return MultiAgentOrchestrator(num_agents=5)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_work_distribution(self, orchestrator, data_generator):
        """Test work is distributed across agents"""
        portfolio = data_generator.generate_portfolio(50)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        await orchestrator.run_processing_cycle()

        distribution = orchestrator.get_load_distribution()

        # All agents should have done some work
        tasks_per_agent = [d["tasks_completed"] for d in distribution.values()]

        # Check for reasonable distribution (no agent should have 0 or all tasks)
        assert all(t > 0 for t in tasks_per_agent)
        assert max(tasks_per_agent) - min(tasks_per_agent) < 20  # Reasonable variance

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_utilization(self, orchestrator, data_generator):
        """Test agent utilization metrics"""
        portfolio = data_generator.generate_portfolio(30)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        await orchestrator.run_processing_cycle()

        distribution = orchestrator.get_load_distribution()

        # All agents should be idle after processing
        assert all(d["status"] == "idle" for d in distribution.values())

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_queue_draining(self, orchestrator, data_generator):
        """Test queue is fully drained"""
        portfolio = data_generator.generate_portfolio(100)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        initial_queue_size = len(orchestrator.task_queue)
        await orchestrator.run_processing_cycle()

        metrics = orchestrator.get_queue_metrics()

        assert metrics["queue_size"] == 0
        assert metrics["completed_total"] + metrics["failed_total"] == initial_queue_size


class TestResourceAllocation:
    """Test resource allocation"""

    @pytest.fixture
    def orchestrator(self):
        return MultiAgentOrchestrator(num_agents=3)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_scale_up_agents(self, orchestrator):
        """Test scaling up agent pool"""
        initial_count = len(orchestrator.agents)

        result = orchestrator.scale_agents(10)

        assert result["previous_count"] == initial_count
        assert result["current_count"] == 10
        assert len(orchestrator.agents) == 10

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_scale_down_agents(self, orchestrator):
        """Test scaling down agent pool"""
        # Scale up first
        orchestrator.scale_agents(10)

        # Scale down
        result = orchestrator.scale_agents(5)

        assert result["current_count"] == 5
        assert len(orchestrator.agents) == 5

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dynamic_scaling_with_load(self, orchestrator, data_generator):
        """Test dynamic scaling based on load"""
        # Add heavy load
        portfolio = data_generator.generate_portfolio(200)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        # Check queue size
        metrics = orchestrator.get_queue_metrics()

        # Scale up based on queue size
        if metrics["queue_size"] > 100:
            orchestrator.scale_agents(10)

        await orchestrator.run_processing_cycle()

        # Verify processing completed
        final_metrics = orchestrator.get_queue_metrics()
        assert final_metrics["queue_size"] == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_specialization(self, orchestrator, data_generator):
        """Test agents have specializations"""
        specializations = [a.specialization for a in orchestrator.agents.values()]

        # Should have multiple specialization types
        assert len(set(specializations)) > 1


class TestPerformanceUnderScale:
    """Test performance under scale"""

    @pytest.fixture
    def orchestrator(self):
        return MultiAgentOrchestrator(num_agents=10)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_high_volume_processing(self, orchestrator, data_generator, perf_tracker):
        """Test processing high volume of tasks"""
        perf_tracker.start_timer("high_volume")

        portfolio = data_generator.generate_portfolio(500)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        result = await orchestrator.run_processing_cycle()

        elapsed = perf_tracker.stop_timer("high_volume")

        assert result["tasks_processed"] + result["tasks_failed"] == 500
        assert elapsed < 30.0  # Should complete in under 30 seconds

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mixed_task_types(self, orchestrator, data_generator):
        """Test processing mixed task types"""
        portfolio = data_generator.generate_portfolio(100)

        task_types = ["contact", "payment", "settlement", "verification"]
        for i, account in enumerate(portfolio):
            task_type = task_types[i % len(task_types)]
            orchestrator.add_task(account["account_id"], task_type)

        result = await orchestrator.run_processing_cycle()

        metrics = orchestrator.get_queue_metrics()
        assert metrics["completed_total"] + metrics["failed_total"] == 100

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_at_scale(self, orchestrator, data_generator):
        """Test error handling doesn't break at scale"""
        portfolio = data_generator.generate_portfolio(100)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        # Process should complete even with some failures
        result = await orchestrator.run_processing_cycle()

        # Should have processed all tasks (success or failure)
        total_processed = result["tasks_processed"] + result["tasks_failed"]
        assert total_processed == 100

        # Failure rate should be low
        if total_processed > 0:
            failure_rate = result["tasks_failed"] / total_processed
            assert failure_rate < 0.10  # Less than 10% failure

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_throughput_metrics(self, orchestrator, data_generator, perf_tracker):
        """Test throughput measurement"""
        portfolio = data_generator.generate_portfolio(200)
        orchestrator.add_bulk_tasks(portfolio, "contact")

        perf_tracker.start_timer("throughput_test")
        result = await orchestrator.run_processing_cycle()
        elapsed = perf_tracker.stop_timer("throughput_test")

        throughput = result["tasks_processed"] / elapsed if elapsed > 0 else 0

        # Should achieve reasonable throughput
        assert throughput > 10  # At least 10 tasks/second

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_queue_metrics_accuracy(self, orchestrator, data_generator):
        """Test queue metrics are accurate"""
        # Add tasks with different priorities
        accounts_high = data_generator.generate_portfolio(10)
        accounts_medium = data_generator.generate_portfolio(20)
        accounts_low = data_generator.generate_portfolio(30)

        for acc in accounts_high:
            orchestrator.add_task(acc["account_id"], "contact", TaskPriority.HIGH)
        for acc in accounts_medium:
            orchestrator.add_task(acc["account_id"], "payment", TaskPriority.MEDIUM)
        for acc in accounts_low:
            orchestrator.add_task(acc["account_id"], "verification", TaskPriority.LOW)

        metrics = orchestrator.get_queue_metrics()

        assert metrics["queue_size"] == 60
        assert metrics["by_priority"]["HIGH"] == 10
        assert metrics["by_priority"]["MEDIUM"] == 20
        assert metrics["by_priority"]["LOW"] == 30
        assert metrics["by_type"]["contact"] == 10
        assert metrics["by_type"]["payment"] == 20


class TestMultiAgentIntegration:
    """Test full multi-agent integration"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_multi_agent_workflow(self, data_generator, audit_logger, perf_tracker):
        """Test complete multi-agent workflow"""
        orchestrator = MultiAgentOrchestrator(num_agents=5)

        # 1. Generate work
        portfolio = data_generator.generate_portfolio(100)
        audit_logger.log("multi_agent", "SYSTEM", "portfolio_generated", {"count": 100})

        # 2. Add tasks
        orchestrator.add_bulk_tasks(portfolio, "contact", TaskPriority.MEDIUM)
        audit_logger.log("multi_agent", "SYSTEM", "tasks_queued", {"count": 100})

        # 3. Scale agents based on load
        metrics = orchestrator.get_queue_metrics()
        if metrics["queue_size"] > 50:
            orchestrator.scale_agents(10)
            audit_logger.log("multi_agent", "SYSTEM", "scaled_up", {"agents": 10})

        # 4. Process
        perf_tracker.start_timer("workflow_processing")
        result = await orchestrator.run_processing_cycle()
        elapsed = perf_tracker.stop_timer("workflow_processing")

        audit_logger.log("multi_agent", "SYSTEM", "processing_complete", {
            "processed": result["tasks_processed"],
            "failed": result["tasks_failed"],
            "elapsed": elapsed
        })

        # 5. Get final metrics
        distribution = orchestrator.get_load_distribution()
        final_metrics = orchestrator.get_queue_metrics()

        # Verify results
        assert final_metrics["queue_size"] == 0
        assert result["tasks_processed"] + result["tasks_failed"] == 100

        # Verify load was distributed
        tasks_completed = [d["tasks_completed"] for d in distribution.values()]
        assert sum(tasks_completed) == final_metrics["completed_total"]

        # Verify audit trail
        entries = audit_logger.get_entries(event_type="multi_agent")
        assert len(entries) >= 4
