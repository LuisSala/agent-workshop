"""
pytest Test Template for ADK Agents

Demonstrates common testing patterns for ADK agents and tools.
"""

import pytest
from google.adk.agents import Agent
from google.adk.tools import FunctionTool, ToolContext
from google.adk.runners import Runner
from unittest.mock import Mock


# Sample tool for testing
def sample_tool(param: str) -> dict:
    """Sample tool for testing."""
    return {"status": "success", "result": f"Processed: {param}"}


# Fixtures
@pytest.fixture
def basic_agent():
    """Create a basic agent for testing."""
    return Agent(
        name="test_agent",
        model="gemini-2.5-flash",
        instruction="You are a test assistant."
    )


@pytest.fixture
def agent_with_tools():
    """Create an agent with tools for testing."""
    return Agent(
        name="tool_agent",
        model="gemini-2.5-flash",
        instruction="You are an assistant with tools.",
        tools=[FunctionTool(sample_tool)]
    )


@pytest.fixture
def mock_tool():
    """Create a mock tool for testing."""
    mock = Mock()
    mock.return_value = {"status": "success", "data": "mocked"}
    return FunctionTool(mock)


# Unit Tests
class TestAgent:
    """Test suite for ADK agents."""

    def test_agent_creation(self, basic_agent):
        """Test that agent is created correctly."""
        assert basic_agent.name == "test_agent"
        assert basic_agent.model == "gemini-2.5-flash"

    def test_agent_has_instruction(self, basic_agent):
        """Test that agent has instruction."""
        assert basic_agent.instruction
        assert "test assistant" in basic_agent.instruction.lower()

    def test_agent_with_tools(self, agent_with_tools):
        """Test that agent has tools."""
        tools = agent_with_tools.get_tools()
        assert len(tools) > 0


# Integration Tests
class TestAgentExecution:
    """Test suite for agent execution."""

    @pytest.mark.asyncio
    async def test_basic_agent_run(self, basic_agent):
        """Test basic agent execution."""
        runner = Runner(basic_agent)

        events = []
        async for event in runner.run_async("Hello"):
            events.append(event)

        # Should have at least one event
        assert len(events) > 0

        # Should have a final response
        final_events = [e for e in events if e.is_final_response()]
        assert len(final_events) > 0

    @pytest.mark.asyncio
    async def test_agent_response_content(self, basic_agent):
        """Test that agent responds with content."""
        runner = Runner(basic_agent)

        final_response = None
        async for event in runner.run_async("Say hello"):
            if event.is_final_response():
                final_response = event.content.text
                break

        assert final_response is not None
        assert len(final_response) > 0

    @pytest.mark.asyncio
    async def test_agent_with_mock_tool(self, mock_tool):
        """Test agent with mocked tool."""
        agent = Agent(
            name="test",
            model="gemini-2.5-flash",
            tools=[mock_tool]
        )

        runner = Runner(agent)

        events = []
        async for event in runner.run_async("Use the tool"):
            events.append(event)

        # Tool might or might not be called depending on LLM
        # This is a basic structure test
        assert len(events) > 0


# Tool Tests
class TestTools:
    """Test suite for tools."""

    def test_sample_tool_success(self):
        """Test sample tool returns success."""
        result = sample_tool("test input")

        assert result["status"] == "success"
        assert "Processed" in result["result"]

    def test_sample_tool_with_parameter(self):
        """Test sample tool processes parameter."""
        result = sample_tool("hello")

        assert result["result"] == "Processed: hello"


# Parametrized Tests
class TestParametrizedAgent:
    """Test agent with multiple scenarios."""

    @pytest.mark.parametrize("user_input,expected_response_type", [
        ("Hello", str),
        ("What is 2+2?", str),
        ("Tell me a joke", str),
    ])
    @pytest.mark.asyncio
    async def test_various_inputs(self, basic_agent, user_input, expected_response_type):
        """Test agent with various inputs."""
        runner = Runner(basic_agent)

        final_response = None
        async for event in runner.run_async(user_input):
            if event.is_final_response():
                final_response = event.content.text
                break

        assert final_response is not None
        assert isinstance(final_response, expected_response_type)


# Async Tool Tests
class TestAsyncTools:
    """Test suite for async tools."""

    @pytest.mark.asyncio
    async def test_async_tool_execution(self):
        """Test async tool execution."""
        async def async_tool(param: str) -> dict:
            """Async sample tool."""
            # Simulate async operation
            import asyncio
            await asyncio.sleep(0.1)
            return {"status": "success", "result": param}

        result = await async_tool("test")
        assert result["status"] == "success"


# Fixture Cleanup
@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup after each test."""
    yield
    # Add cleanup code here if needed


if __name__ == "__main__":
    # Run tests with: pytest test_template.py
    pytest.main([__file__, "-v"])
