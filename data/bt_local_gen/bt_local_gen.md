repo layout (suggested)

bt_local_gen/
├── __init__.py
├── config.py
├── datasets.py
├── prompts.py
├── client_live.py
├── client_mock.py
├── caching.py
├── validators.py
├── pipeline.py
├── cli.py
└── fixtures/
├── sample_node_library.json
└── sample_llm_response.txt

tests/
├── test_pipeline_mock.py
└── test_validators.py

Usage (mock):
python -m bt_local_gen.cli --mode mock --dataset columbia_cairlab_pusht_real --from 1 --to 3
Usage (live):
OPENAI_API_KEY=... python -m bt_local_gen.cli --mode live --dataset columbia_cairlab_pusht_real --from 1 --to 3 --budget 2.00