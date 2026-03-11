# Legacy Workspace

These files are preserved for older live/demo trading and manual research
experiments. They are not part of the public MCP install path.

Use the MCP server for the supported public workflow:

```bash
pip install .
kalshi-research-mcp
```

If you intentionally need the legacy scripts:

```bash
pip install ".[legacy]"
python legacy/test_auth.py
python legacy/runner.py --config legacy/config.yaml --dry-run
```

Legacy research helpers also live here:

```bash
python legacy/backtester.py
python legacy/grid_search.py
python legacy/analyze_results.py
```

The shared `mm.py` module remains at the repo root because the backtester still
reuses its strategy primitives.
