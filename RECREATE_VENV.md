# Recreate the Virtual Environment

A Python virtual environment hardcodes absolute paths in its `bin/` scripts (e.g. `pip`).
If you **rename or move the project folder**, the venv breaks with errors like:

```
bad interpreter: .../.venv/bin/python3.13: no such file or directory
```

The fix is to delete and recreate the venv.

## Steps

Run these from the project root:

```bash
deactivate 2>/dev/null            # exit the venv if it's active (ignore error if not)
rm -rf .venv                      # delete the old environment
python3.13 -m venv .venv          # recreate it
source .venv/bin/activate         # activate it
pip install -r requirements.txt   # reinstall dependencies
```

## One-liner

Skips activation—useful if you just want it rebuilt:

```bash
rm -rf .venv && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
