# Schemas: Data Structures for the Intelligent Agent

## Core Philosophy: Transparency and Introspection

The data structures in `agentlz/schemas/responses.py` have been redesigned to support the new "intelligent commander" architecture. The primary goal is to provide maximum transparency into the agent's decision-making process. Instead of just returning a final answer, the new schema exposes the entire "thought -> action -> observation" loop.

## Key Data Models

### 1. `AgentStep`

This is the most fundamental new data model. It represents a single, atomic step in the agent's reasoning process. It is designed to be a generic container that logs the agent's internal monologue and its interactions with the outside world (i.e., its tools).

- **`thought: str`**: A description of the agent's thinking at that moment. Why is it taking this action? What does it expect to happen? This is the agent's internal monologue, captured directly from the LLM's output.
- **`action: str`**: A description of the action the agent is taking. This is typically the name of the tool being called and the parameters being passed to it.
- **`observation: str`**: The result of the action. This is the output returned by the tool that was called.

### 2. `ScheduleResponse`

This is the top-level response model for the `schedule_agent`. It has been simplified and now focuses on providing the final result along with the detailed history of how it got there.

- **`output: str`**: The final, synthesized answer to the user's query.
- **`intermediate_steps: List[AgentStep]`**: A list of `AgentStep` objects. This provides a complete, step-by-step log of the agent's entire workflow, from the initial plan to the final result, including any corrections or re-thinking it did along the way.

### 3. `ToolResponse` and `CheckResponse`

These models remain and are used to structure the `observation` field within an `AgentStep` when a `tools` or `check` agent is called. They provide a standardized way to represent the outputs of these specialized agents.

- **`ToolResponse`**: Contains fields like `tool_id`, `status`, `output`, and `error` to represent the result of a `tools` agent execution.
- **`CheckResponse`**: Contains fields like `check_id`, `status`, `is_passed`, and `reason` to represent the result of a `check` agent validation.

## Deprecated Models

The following models from the previous architecture have been **removed** and are no longer in use:

- `PlanStep`
- `PlanResponse`

The planning logic is now captured within the `intermediate_steps` of the `ScheduleResponse` as one or more `AgentStep` objects.
