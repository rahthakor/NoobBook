# Refactoring Guide

## Backend Service Architecture

```
ai_agents/          → Orchestration only (the "brain")
ai_services/        → Single-purpose AI functions (the "skills")
tool_executors/     → Tool execution logic (the "hands")
```

---

## The Pattern

### ai_agents/ - Orchestration

**Purpose:** Run the agentic loop. Manage messages. Decide what to do next.

**Should contain:**
- Message loop (user → Claude → tool → Claude → ...)
- Stop conditions (termination tool, max iterations)
- Message serialization
- Execution logging

**Should NOT contain:**
- Tool execution logic
- File I/O operations
- External API calls
- Business logic

```python
# GOOD: Agent delegates to executor
result = some_executor.execute_tool(tool_name, tool_input, project_id)

# BAD: Agent does the work itself
if tool_name == "create_file":
    with open(file_path, 'w') as f:
        f.write(content)
```

---

### ai_services/ - Single-Purpose AI Functions

**Purpose:** One AI call. One job. Returns result.

**Should contain:**
- Single Claude API call
- Prompt construction
- Response parsing
- Return structured result

**Should NOT contain:**
- Loops or iterations
- Multiple API calls
- Tool handling
- State management

```python
# GOOD: Single purpose
def extract_pdf_page(page_bytes, page_num) -> Dict:
    response = claude_service.send_message(...)
    return parse_extraction(response)

# BAD: Does too much
def process_entire_pdf(pdf_path) -> Dict:
    for page in pages:
        # multiple calls, loops, state...
```

---

### tool_executors/ - Tool Execution

**Purpose:** Execute a tool. Handle the messy details. Return clean result.

**Should contain:**
- Tool-specific logic
- File operations
- External API calls
- Error handling
- Result formatting

**Should NOT contain:**
- Claude API calls
- Message management
- Loop logic

```python
# GOOD: Executor handles details
class WebsiteToolExecutor:
    def execute(self, tool_name, tool_input, context):
        if tool_name == "create_file":
            return self._create_file(tool_input, context)

    def _create_file(self, tool_input, context):
        # All the file I/O, validation, placeholder replacement...
        return {"success": True, "message": "File created"}
```

---

## Refactoring Checklist

When refactoring an agent:

1. **Identify tool handlers** - Any `if tool_name == "xyz":` block with >5 lines
2. **Extract to executor** - Move logic to `tool_executors/{agent}_executor.py`
3. **Agent calls executor** - `result = executor.execute_tool(name, input, context)`
4. **Executor returns dict** - Clean result the agent can use

---

## The Goal

**Before:** 760-line agent with everything mixed in

**After:**
- 150-line agent (orchestration only)
- 200-line executor (tool logic)
- Clear separation, easy to test, easy to extend

---

## Refactored Agents

| Agent | Before | After | Executor | Status |
|-------|--------|-------|----------|--------|
| `blog_agent_service.py` | 534 lines | 202 lines | `blog_tool_executor.py` (232 lines) | Done |
| `website_agent_service.py` | 760 lines | 197 lines | `website_tool_executor.py` (338 lines) | Done |
| `business_report_agent_service.py` | 619 lines | 299 lines | `business_report_tool_executor.py` (280 lines) | Done |

---

## Refactored Services (Single AI Call)

| Service | Before | After | Moved To | Utils Extracted | Status |
|---------|--------|-------|----------|-----------------|--------|
| `wireframe_service.py` | 359 lines (studio_services/) | 173 lines | `ai_services/` | `excalidraw_utils.py` (120 lines) | Done |

---

## Shared Utilities

| Utility | Location | Purpose | Used By |
|---------|----------|---------|---------|
| `get_source_content()` | `app/utils/source_content_utils.py` | Load source content with smart sampling for large sources | blog_agent, website_agent, wireframe_service |
| `get_source_name()` | `app/utils/source_content_utils.py` | Get source name by ID | (available) |
| `convert_to_excalidraw_elements()` | `app/utils/excalidraw_utils.py` | Convert simplified elements to Excalidraw format | wireframe_service |

---

## Prompt Config Pattern

User messages and mappings should be in prompt JSON configs, not hardcoded in agents.

```json
// data/prompts/{agent}_prompt.json
{
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.6,
  "max_tokens": 16000,
  "user_message": "Create content based on:\n{source_content}\n\nDirection: {direction}",
  "some_types": {
    "type_a": "Display Name A",
    "type_b": "Display Name B"
  },
  "system_prompt": "..."
}
```

Agent uses:
```python
config = prompt_loader.get_prompt_config("agent_name")
user_message = config.get("user_message", "").format(
    source_content=source_content,
    direction=direction
)
```

---

## Refactoring Steps

When refactoring a service:

1. **Identify service type**
   - Agentic loop (multiple Claude calls) → `ai_agents/`
   - Single AI call → `ai_services/`
   - Non-AI processing → keep in current location

2. **Check for duplicated utilities**
   - `_get_source_content` → use `source_content_utils.get_source_content()`
   - Data transformation logic → extract to `utils/`

3. **Externalize to prompt config**
   - User message templates → `user_message` in JSON
   - Type mappings → `some_types` dict in JSON

4. **Extract tool handlers** (for agents only)
   - Move to `tool_executors/{name}_executor.py`
   - Keep agent as orchestration only

5. **Update REFACTORING.md**
   - Add to Refactored Agents/Services table
   - Add any new shared utilities