import uuid

from httpx import AsyncClient

from app.db.seed import load_species_seed


async def test_lists_the_whole_seeded_catalog_sorted(client: AsyncClient) -> None:
    response = await client.get("/species")

    assert response.status_code == 200
    names = [species["common_name"] for species in response.json()]
    assert len(names) == len(load_species_seed())
    assert names == sorted(names)


async def test_search_matches_common_and_scientific_names(client: AsyncClient) -> None:
    by_common = (await client.get("/species", params={"q": "jiboia"})).json()
    by_scientific = (await client.get("/species", params={"q": "epipremnum"})).json()

    assert [s["scientific_name"] for s in by_common] == ["Epipremnum aureum"]
    assert by_common == by_scientific


async def test_get_by_id(client: AsyncClient, species_id: str) -> None:
    response = await client.get(f"/species/{species_id}")

    assert response.status_code == 200
    assert response.json()["common_name"] == "Jiboia"


async def test_unknown_species_is_404(client: AsyncClient) -> None:
    response = await client.get(f"/species/{uuid.uuid4()}")
    assert response.status_code == 404
