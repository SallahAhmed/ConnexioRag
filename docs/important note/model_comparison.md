# OpenCode AI Model Comparison (Early 2026)

This document provides a comparison of the key AI models available in the OpenCode ecosystem, optimized for agentic coding tasks.

## 🚀 Model Comparison Overview

| Model                    | Best For...           | Key Strength                                                                                                                    |
| :----------------------- | :-------------------- | :------------------------------------------------------------------------------------------------------------------------------ |
| **MiniMax M2.5**         | **General Coding**    | Best "all-rounder." Extremely fast and matches SOTA models like Claude 3.5 Sonnet in pure coding accuracy.                      |
| **Big Pickle (GLM-4.6)** | **Agentic Tool Use**  | Optimized for multi-step agent tasks. It is exceptionally good at following complex instructions and using terminal/file tools. |
| **Hy3 Preview**          | **Complex Reasoning** | Tencent’s 295B MoE. Best for architectural decisions, deep logic problems, and high-level software design.                      |
| **Nemotron 3 Super**     | **Long Context**      | NVIDIA's 120B hybrid model. Best for analyzing entire large codebases thanks to its massive **1M token context window**.        |

---

## 🔍 Selection Guide

### 1. MiniMax M2.5 (Free)

- **When to use:** Standard development, writing functions, or debugging a single file.
- **Why:** One of the most cost-effective and accurate models for 90% of routine coding tasks.

### 2. Big Pickle (GLM-4.6)

- **When to use:** Complex multi-file refactoring or when allowing the AI to run terminal commands.
- **Why:** Specifically fine-tuned to behave like a senior developer who can navigate file systems and execute multi-step plans reliably.

### 3. Hy3 Preview (Free)

- **When to use:** Architectural decisions, deep logic problems, and high-level software design.
- **Why:** A massive 295B Mixture-of-Experts (MoE) model with deep reasoning capabilities for "hard" bugs.

### 4. Nemotron 3 Super (Free)

- **When to use:** Large codebase analysis and project-wide context.
- **Why:** Features a **1-million-token context window**, allowing it to digest entire repositories at once to understand cross-file dependencies.

---

## 💡 Recommended Workflow

1. **Start with MiniMax M2.5** for general coding.
2. **Switch to Big Pickle** for complex agent-driven tasks.
3. **Use Nemotron 3 Super** for answering questions about the overall codebase structure.
4. **Use Hy3** for deep architectural consulting.
