# Tasks: Context Management Overhaul

- [x] **Core System Migration**
    - [x] Async OpenAI & Threaded Tools
    - [x] Arabic Language Optimization
    - [x] Sequential Stability Fix

- [ ] **Absolute Fast-Path (Latency Killer)**
    - [ ] Move length check to TOP of `WorkflowController.detect_node`
    - [ ] Reorder keywords (GENERAL first) in `WorkflowController.py`
    - [ ] Add timestamps to all `[AGENT]` logs in `NLPController.py`

- [ ] **Verification**
    - [ ] Test "Hello" response time (<1s)
    - [ ] Verify console logs show precise timestamps
