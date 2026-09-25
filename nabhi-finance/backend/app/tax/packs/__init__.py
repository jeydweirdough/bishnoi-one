"""Country packs: each country's tax rules, as the engine applies them.

Add a country by writing its module here and listing it in PACKS. The
Philippines came first (benchmarks/decisions.md, D8).
"""

from types import ModuleType

from app.tax.packs import ph

PACKS: dict[str, ModuleType] = {ph.country: ph}


def pack_for(country: str) -> ModuleType:
    try:
        return PACKS[country]
    except KeyError:
        raise ValueError(f"There's no tax pack for {country!r} yet.") from None
