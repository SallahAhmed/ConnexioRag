# Implementation Plan — Eliminate 5-Minute Hang

The 5-minute delay occurs during the "Intent Detection" phase. This happens because the system is skipping the keyword check and falling back to the LLM, which triggers a "Cold Start" (model loading) in Ollama. 

We will fix this by making the "Fast-Path" absolute and refining keyword priority.

## 🚀 Proposed Changes

### 1. Absolute Fast-Path Priority
We will move the **Length Check** to the very beginning of the detection logic. This ensures that any short query (like your greeting) returns a "General" node instantly, without even looking at keywords or calling the AI.

#### [MODIFY] WorkflowController.py
- Move `if len(query_lower.strip()) < 50` to the top of `detect_node`.
- Reorder `keywords` dictionary so that `GENERAL` is checked **first**.
- *Benefit*: Instant response for greetings, no Ollama wait time.

---

### 2. Precise Diagnostic Logging
We will add timestamps to the console logs so we can distinguish between a "loading" delay and a "processing" delay.

#### [MODIFY] NLPController.py
- Import `datetime`.
- Change logs to: `[AGENT] [14:20:01] Detecting intent...`
- *Benefit*: Accurate bottleneck identification.

---

### 3. Model Pre-loading Tip
The 5-minute hang is aggravated by Ollama swapping models between VRAM and RAM. 

> [!TIP]
> If you have enough RAM, you can tell Ollama to keep models loaded by setting `OLLAMA_KEEP_ALIVE=-1` in your environment variables.

---

## Verification Plan

### Manual Verification
- Ask "Hello, how can you help me today?". 
- **Expected**: It should hit the `< 50` char rule and respond **instantly**. 
- Verify the console log shows `Node: WorkflowNodeEnum.GENERAL` (it was previously hitting `BLOCKER`).
