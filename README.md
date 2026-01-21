# PetroModeler (Streamlit)

A modular, extensible interactive modeling & plotting tool for 7 geochemical process models:

- FC (Fractional crystallization)
- AFC (Assimilation–fractional crystallization)
- FCA (Decoupled assimilation–fractional crystallization)
- MM (Magma mixing)
- Rayleigh (Rayleigh fractionation)
- Water–Rock reaction (open-system exchange)
- Mush extraction (crystal–melt separation)

This repository is a **starter implementation** following a clean separation:

- `domain/` – pure math & rules (no Streamlit imports)
- `application/` – state + services (resolver, simulation, plotting helpers)
- `ui/` – Streamlit pages/widgets (rendering)

## Run

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Development

The test baseline uses the standard-library `unittest` runner:

```bash
python -m unittest discover -s petromodeler/tests -q
```

Optional lint/type-check tooling is declared in `pyproject.toml`:

```bash
pip install -e ".[dev]"
python -m ruff check petromodeler
python -m mypy
```

## Notes

- The Streamlit UI is intentionally simple but the architecture is designed for extension.
- Model formulas and parameter meanings are based on the provided `建模方法.md`.
