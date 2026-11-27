"""Valida a base curada de espécies sem precisar de banco."""

from app.db.seed import load_species_seed
from app.domain.water_balance import Environment, PlantProfile


def test_seed_has_between_20_and_30_species() -> None:
    assert 20 <= len(load_species_seed()) <= 30


def test_scientific_names_are_unique() -> None:
    names = [species.scientific_name for species in load_species_seed()]
    assert len(names) == len(set(names))


def test_common_names_are_unique() -> None:
    names = [species.common_name.casefold() for species in load_species_seed()]
    assert len(names) == len(set(names))


def test_every_species_is_a_valid_domain_profile() -> None:
    for species in load_species_seed():
        PlantProfile(
            kc=species.kc,
            drying_threshold=species.drying_threshold,
            environment=Environment.INDOOR,
            pot_volume_liters=1,
        )
