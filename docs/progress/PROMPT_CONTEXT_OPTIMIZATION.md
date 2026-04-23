# Progress Report: Prompt Context Optimization (2026-04-20)

## 1. Problem Identification
In previous iterations, the `AgentLoop` blindly appended the full content of tool outputs (especially sandbox execution logs and large file reads) to the `messages` history. This caused several critical issues:
- **Context Window Exhaustion**: Large logs (e.g., 10,000+ lines of compilation errors) could easily exceed the LLM's context limit.
- **Attention Dilution**: The LLM struggled to find the "root cause" of a failure when buried under thousands of lines of redundant information.
- **High Token Costs**: Every turn incurred high costs for re-sending massive, repeated logs.

## 2. Solution: Intelligent Content Truncation
Implemented a `truncate_content` mechanism in `core/loop.py`.

### 2.1 Truncation Strategy
- **Threshold**: Content exceeding **5000 characters** is triggered for truncation.
- **Dual-Anchor Retention**:
    - **Head (First 1000 chars)**: Usually contains the command executed and initial output.
    - **Tail (Last 3500 chars)**: Usually contains the most critical error messages, stack traces, and exit status.
- **Transparency**: Injected a clear indicator `[... Truncated X chars for context efficiency ...]` so the Agent is aware that the middle section was removed.

### 2.2 Implementation Details
- Added `AgentLoop.truncate_content()` helper method.
- Updated `run_one_turn` to apply truncation to all `tool_result` messages before they are appended to `state.messages`.

## 3. Impact & Results
- **Reduced Token Consumption**: Significant reduction in token usage for long-running sessions with heavy tool output.
- **Improved Reliability**: The Agent can now maintain focus on the "Tail" of the error log, which is where the most actionable information resides.
- **System Stability**: Prevents crashes related to API payload size limits.

## 4. Future Work
- **Context-Aware Truncation**: Allow Hooks to decide *how* to truncate (e.g., keep only lines matching `ERROR`).
- **Dynamic Thresholding**: Adjust truncation limits based on the remaining context window of the specific LLM model being used.
