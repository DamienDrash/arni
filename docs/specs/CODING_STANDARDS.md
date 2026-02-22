# Engineering Standards & Governance (CODING_STANDARDS.md)

## 1. Model Context Protocol (MCP) Compliance
We use the **Model Context Protocol (MCP)** standard for all tool integrations.
- **Skills as Tools:** Every Skill (e.g., `gym-booking`) must be defined as an MCP Tool definition.
- **Structured IO:** All tools must accept JSON Schema inputs and return structured JSON outputs.
- **No Scripts:** Do not write loose Python scripts. Encapsulate logic in `app/tools/` classes inheriting from `BaseTool`.

## 2. Sandboxing & Execution Safety
- **Dockerized Self-Improvement:** When Ariia refactors his own code, this process MUST run inside a **Docker Container** (Ephemeral Sandbox).
- **No Root:** The Agent must NEVER have root access to the host VPS.
- **File Access:** Restricted to `./workspace/` and `./data/`. Access to `/etc/`, `/var/`, or `../` is strictly prohibited.

## 3. The BMAD Implementation Method
Follow this cycle for every new feature or refactoring:
1.  **B - Benchmark (Build Spec):** Define the success metric FIRST. (e.g., "Vision Agent must count 8 people in `test_image.jpg` >90% conf.").
2.  **M - Modularize:** Build the component in isolation (e.g., `vision_processor.py`) without external dependencies.
3.  **A - Architect:** Integrate the module into the `Swarm Router` and `Redis Bus`.
4.  **D - Deploy & Verify:** Run the specific test case defined in (B). Only commit if PASS.

## 4. Testing & Verification
- **Unit Tests:** Every module requires a corresponding `tests/test_module.py` (Pytest).
- **Mocking:** External APIs (Magicline, WhatsApp) MUST be mocked for tests. Never hit production APIs during CI/CD.