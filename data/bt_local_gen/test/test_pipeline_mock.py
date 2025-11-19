import sys
import json
import textwrap
from pathlib import Path

def test_end_to_end_mock(tmp_path, monkeypatch):
    """
    End-to-end in modalità MOCK:
    - dataset fittizio in tmp_path con local_prompt.md e frame_03.jpg
    - PATHS del pacchetto reindirizzati a tmp_path
    - fixture LLM con due code block (xml + json) SENZA indentazione
    - invoca CLI mock e verifica che subtree_.xml/.json vengano generati
    """

    # 1) Setup dataset minimale (versione nel nome cartella)
    ds = tmp_path / "dataset" / "columbia_cairlab_pusht_real_0.1.0" / "episode_001" / "locals" / "local_1"
    ds.mkdir(parents=True)
    (ds / "local_prompt.md").write_text("PROMPT_MINIMALE", encoding="utf-8")
    (ds / "frame_03.jpg").write_bytes(b"0000")

    # 2) node_library minima coerente coi nodi usati nella fixture
    nl = {
        "composites": {"Sequence": {"attrs": {}}},
        "decorators": {},
        "actions": {
            "DetectObject":     {"ports": {"target": "string", "timeout_ms": "int"}},
            "MoveAbove":        {"ports": {"target": "string", "offset_z": "float", "timeout_ms": "int"}},
            "ApproachAndAlign": {"ports": {"target": "string", "tolerance": "float", "timeout_ms": "int"}},
        },
        "conditions": {},
        "port_value_spaces": {},
    }
    nl_path = tmp_path / "node_library_v_01.json"
    nl_path.write_text(json.dumps(nl), encoding="utf-8")

    # 3) Rende importabile il pacchetto dal repo root
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

    from bt_local_gen import config
    from bt_local_gen.cli import main as cli_main

    # 4) Reindirizza i PATHS del pacchetto alla sandbox (tmp_path)
    config.PATHS.project_root = tmp_path
    config.PATHS.dataset_root = tmp_path / "dataset"
    config.PATHS.node_library = nl_path

    # 5) Fixture LLM con due code block: de-indentata e senza testo extra
    fixtures_dir = tmp_path / "bt_local_gen" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    fixture_text = textwrap.dedent(
        """\
        ```xml
        <BehaviorTree ID="MainTree">
          <Sequence>
            <DetectObject target="green_bin" timeout_ms="1200"/>
            <MoveAbove target="green_bin_lid" offset_z="0.08" timeout_ms="1500"/>
            <ApproachAndAlign target="lid_edge" tolerance="0.01" timeout_ms="1500"/>
          </Sequence>
        </BehaviorTree>
        ```
        ```json
        {
          "frame_index": 3,
          "local_intent": "verify contact on lid edge",
          "plugs_into": { "path_from_root": ["MainTree"], "mode": "replace-only" },
          "bb_read": [],
          "bb_write": [],
          "assumptions": [],
          "coherence_with_global": "consistent with Detect→Approach→Verify",
          "format_checks": {
            "single_root_composite": true,
            "decorators_single_child": true,
            "only_known_nodes": true,
            "only_binned_values": true
          }
        }
        ```"""
    ).strip() + "\n"  # newline finale per sicurezza
    fix_path = fixtures_dir / "sample_llm_response.txt"
    fix_path.write_text(fixture_text, encoding="utf-8")

    # 6) Invoca il CLI in MOCK (niente "-m")
    sys.argv = [
        "bt_local_gen.cli",
        "--mode", "mock",
        "--dataset", "columbia_cairlab_pusht_real_0.1.0",
        "--fixture", str(fix_path),
    ]
    cli_main()

    # 7) Verifiche
    xml_p = ds / "subtree_.xml"
    json_p = ds / "subtree_.json"
    assert xml_p.exists(), "subtree_.xml non generato"
    assert json_p.exists(), "subtree_.json non generato"

    xml = xml_p.read_text(encoding="utf-8")
    js  = json_p.read_text(encoding="utf-8")
    assert "<BehaviorTree" in xml and "ApproachAndAlign" in xml
    assert '"format_checks"' in js and '"only_known_nodes": true' in js
