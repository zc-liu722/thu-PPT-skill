# Install `thu-ppt-generator`

## Core runtime

The upgraded skill uses:

- Python 3.10+ for parsing, planning, asset selection, and QA
- Node.js 18+ for `PptxGenJS` rendering

## 1. Install Node dependency

```bash
cd /Users/liuzichang/.codex/skills/thu-ppt-generator
npm install
```

This installs the only hard runtime dependency:

- `pptxgenjs`

## 2. Optional QA extras

If you want raster review and overflow checks aligned with the mature `slides` skill:

```bash
python3 -m pip install -r requirements-qa.txt
```

These extras are optional and not required for basic deck generation.

## 3. Validate the skill

```bash
cd /Users/liuzichang/.codex/skills/thu-ppt-generator
python3 scripts/run_pipeline.py \
  --input examples/technical_system.md \
  --output-dir /tmp/thu-ppt-generator-check
```

## 4. Run tests

```bash
cd /Users/liuzichang/.codex/skills/thu-ppt-generator
python3 -m unittest discover -s tests -v
```
