# Claude Code Integration

## 1. Purpose

This document defines how Claude Code is integrated into AIOS.

Claude Code is not treated as a standalone product inside this repository.
Instead, it is positioned as a **development execution runtime** within AIOS.

Its responsibility is to translate natural language development intent into concrete actions on codebases, including:

* Reading and understanding repositories
* Editing files
* Running shell commands
* Managing Git workflows

In short:

> Claude Code acts as the **"hands" of AIOS for software development tasks**

---

## 2. Placement in AIOS Architecture

Claude Code is integrated under:

```
runtimes/claude-code/
```

Within the overall AIOS structure:

```
AIOS/
  kernel/                # cognition, memory, intent, planning
  runtimes/
    claude-code/         # development execution runtime
    browser-runtime/     # (future)
    filesystem-runtime/  # (future)
  plugins/
  services/
```

### Architectural Role

| Layer    | Responsibility                      |
| -------- | ----------------------------------- |
| Kernel   | Thinking (intent, planning, memory) |
| Runtimes | Execution (code, browser, devices)  |
| Plugins  | Capability extension                |

Claude Code belongs to **Runtimes layer**.

---

## 3. Integration Principles

### 3.1 Separation of Concerns

Claude Code must remain **decoupled from the AIOS kernel**.

* No direct modification of kernel logic
* No embedding of business-specific assumptions
* Treated as an interchangeable execution module

---

### 3.2 Minimal Invasive Changes

Modifications inside `runtimes/claude-code` should be minimized.

Allowed:

* Configuration changes
* Adapter/wrapper layers
* Plugin additions

Avoid:

* Deep rewrites of core logic
* Breaking compatibility with upstream

---

### 3.3 Upstream Compatibility

The integration is based on upstream repository:

https://github.com/anthropics/claude-code

We maintain the ability to:

```
git subtree pull --prefix=runtimes/claude-code claude-code main --squash
```

This requires:

* Avoiding structural changes to upstream files
* Isolating custom logic outside or on top

---

## 4. Customization Strategy

All AIOS-specific logic should be implemented **outside Claude Code core**, using one of the following methods:

### 4.1 Wrapper Layer (Recommended)

Create a wrapper runtime:

```
runtimes/dev-runtime/
```

Responsibilities:

* Accept AIOS task objects
* Translate them into Claude Code commands
* Execute and collect results
* Feed results back into kernel

---

### 4.2 Plugin-Based Extension

Leverage Claude Code plugin system:

```
runtimes/claude-code/plugins/
```

Use plugins to:

* Add custom commands
* Define domain-specific agents
* Integrate with AIOS capabilities

---

### 4.3 Capability Bus Integration

Claude Code should be exposed as a capability:

```
POST /capabilities/execute
```

Example capability:

```json
{
  "name": "code.execute",
  "runtime": "claude-code",
  "scope": "local_repo",
  "requires_confirmation": false
}
```

---

## 5. Responsibilities of Claude Code Runtime

Claude Code runtime is responsible for:

* Codebase understanding
* File manipulation
* Shell execution
* Git operations
* Task-level automation

It is **NOT responsible for**:

* Long-term memory
* User identity / persona
* Goal planning
* Governance / risk control

These belong to the AIOS kernel.

---

## 6. Data Flow

Typical flow:

```
User Intent
   ↓
AIOS Kernel (intent + planning)
   ↓
Task Object
   ↓
Claude Runtime Adapter
   ↓
Claude Code Execution
   ↓
Artifacts (files, commits, logs)
   ↓
AIOS Memory / Task System
```

---

## 7. What Can Be Modified

### Allowed Areas

* `plugins/`
* configuration files
* wrapper scripts
* integration adapters

### Restricted Areas

* core CLI logic
* internal execution engine
* upstream command definitions (unless necessary)

---

## 8. Upgrade Strategy

To sync with upstream:

```
git fetch claude-code
git subtree pull --prefix=runtimes/claude-code claude-code main --squash
```

Before pulling:

* Ensure no breaking local changes
* Keep custom logic isolated

After pulling:

* Re-test integration layer
* Verify plugins compatibility

---

## 9. Future Evolution

Claude Code is only the first runtime.

Future runtimes may include:

* browser-runtime
* device-runtime
* robotics-runtime

Long term vision:

> AIOS becomes a unified execution system where different runtimes handle different domains.

Claude Code represents:

> The **Software Development Runtime**

---

## 10. Summary

Claude Code is integrated as:

* a **runtime**, not a core system
* an **execution engine**, not a brain
* a **replaceable module**, not a dependency lock

This ensures AIOS remains:

* modular
* evolvable
* architecture-driven

---

End of document.
