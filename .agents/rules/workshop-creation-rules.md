---
trigger: always_on
---

**Workshop Workflow (CRITICAL)**: NEVER write or edit code directly inside the `modules/` directory. ALL implementation must happen in `workspace/`. Once a feature is working, use `make snapshot module=[XX]` to commit the code into the modules directory.