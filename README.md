# OXE-BT-PIPELINE

This repository contains the **OXE-BT-PIPELINE**, a framework to convert episodes from the **Open-X Embodiment (OXE)** dataset into grounded triplets linking visual evidence, task descriptions, and executable Behavior Trees in **BehaviorTree.CPP** format.

---

## Project Structure

```
oxe-bt-pipeline/
├─ pipeline/                       # Core pipeline modules
│  ├─ __init__.py
│  ├─ frame_select.py              # Extracts keyframes from videos/episodes
│  ├─ detect.py                    # Runs detectors (YOLO, GroundingDINO)
│  ├─ schema.py                    # JSON Schema definition and validator
│  ├─ plan_types.py                # Pydantic models: Plan, Step, ArgLink, etc.
│  ├─ teacher_iface.py             # Teacher interface for VLM/LLM
│  ├─ teachers/                    # Teacher implementations
│  │  ├─ __init__.py
│  │  ├─ manual_paste.py           # Manual teacher (baseline)
│  │  └─ qwen_vl.py                # Example VLM teacher backend
│  ├─ compile_bt.py                # Compiler: Plan → BehaviorTree.CPP XML
│  ├─ validate.py                  # Validators: schema, invariants, grounding
│  ├─ export.py                    # Exports triplets, XMLs, dataset summary
│  └─ cli.py                       # Typer CLI entrypoint
│
├─ frames/                         # Extracted keyframes (output)
├─ detections/                     # Detector outputs (*.dets.json)
├─ triplets/                       # JSON triplets (frame, plan, bt xml)
├─ behavior_trees/                 # BehaviorTree.CPP XML outputs
│
├─ tests/                          # Unit tests
│  ├─ test_schema.py               # Validate JSON schema and pydantic models
│  ├─ test_compiler.py             # Ensure XML correctness and structure
│  ├─ test_invariants.py           # Check pipeline invariants
│  └─ conftest.py                  # Shared pytest config
│
├─ docs/                           # Documentation and prompts
│  └─ prompts/                     # Prompt engineering examples for VLMs
│
├─ config.py                       # Configuration (thresholds, paths, etc.)
├─ keys.py                         # Secure loading of Azure OpenAI keys
├─ environment.yml                 # Conda environment specification
├─ Makefile                        # Utility commands (optional)
├─ README.md                       # Project overview and quickstart (this file)
├─ DEV_SETUP.md                    # Setup instructions (Windows/Linux/Colab)
├─ GIT_GUIDE.md                    # Git usage conventions
└─ .gitignore                      # Ignore build artifacts and local files
```

---

## Key Components

### `pipeline/`
The heart of the system. Modules implement each phase:
- **frame_select.py**: Extracts representative frames from OXE episodes.
- **detect.py**: Runs detectors (YOLOv8, GroundingDINO). Produces `.dets.json`.
- **schema.py**: Defines the JSON Schema for plans.
- **plan_types.py**: Pydantic data models for plans, steps, arguments.
- **teacher_iface.py**: Standard interface for teachers (Manual, VLM).
- **teachers/**: Collection of teacher implementations.
- **compile_bt.py**: Converts validated plans into deterministic BehaviorTree.CPP XML.
- **validate.py**: Runs multiple validators: schema, invariants, grounding.
- **export.py**: Writes JSON triplets, XML, and aggregates dataset summary.
- **cli.py**: Typer-based command line interface.

### Output Folders
- **frames/**: Extracted keyframes (JPG).
- **detections/**: Object detections with scores.
- **triplets/**: Final triplets in JSON format linking frames, plans, and BT XML.
- **behavior_trees/**: Behavior trees compiled to XML, compatible with BehaviorTree.CPP.

### Testing
The `tests/` folder contains unit tests ensuring robustness of schema validation, compiler correctness, and invariant checking.

### Documentation
- **DEV_SETUP.md**: Explains setup on Windows, Linux, Colab.
- **GIT_GUIDE.md**: Guidelines for Git usage and workflow.
- **docs/prompts/**: Examples of prompt engineering strategies for teacher models.

---

## Getting Started



## License
MIT (or project-specific).

