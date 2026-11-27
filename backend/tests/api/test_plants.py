import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import AuthHeaders

Plant = dict[str, object]


class TestCreate:
    async def test_creates_plant_with_nested_species(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant_payload: Plant
    ) -> None:
        response = await client.post("/plants", json=plant_payload, headers=auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert body["nickname"] == "Jiboia da sala"
        assert body["environment"] == "indoor"
        assert body["species"]["scientific_name"] == "Epipremnum aureum"
        assert body["created_at"] and body["updated_at"]

    async def test_requires_authentication(self, client: AsyncClient, plant_payload: Plant) -> None:
        response = await client.post("/plants", json=plant_payload)
        assert response.status_code == 401

    async def test_rejects_unknown_species(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant_payload: Plant
    ) -> None:
        payload = {**plant_payload, "species_id": str(uuid.uuid4())}
        response = await client.post("/plants", json=payload, headers=auth_headers)
        assert response.status_code == 422

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("latitude", 91),
            ("longitude", -181),
            ("pot_volume_liters", 0),
            ("environment", "garage"),
            ("nickname", ""),
        ],
    )
    async def test_rejects_invalid_values(
        self,
        client: AsyncClient,
        auth_headers: AuthHeaders,
        plant_payload: Plant,
        field: str,
        value: object,
    ) -> None:
        response = await client.post(
            "/plants", json={**plant_payload, field: value}, headers=auth_headers
        )
        assert response.status_code == 422


class TestRead:
    async def test_list_returns_only_own_plants(
        self,
        client: AsyncClient,
        auth_headers: AuthHeaders,
        other_auth_headers: AuthHeaders,
        plant_payload: Plant,
        plant: Plant,
    ) -> None:
        await client.post(
            "/plants", json={**plant_payload, "nickname": "Da vizinha"}, headers=other_auth_headers
        )

        mine = (await client.get("/plants", headers=auth_headers)).json()
        theirs = (await client.get("/plants", headers=other_auth_headers)).json()

        assert [p["id"] for p in mine] == [plant["id"]]
        assert [p["nickname"] for p in theirs] == ["Da vizinha"]

    async def test_list_paginates(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant_payload: Plant
    ) -> None:
        for i in range(3):
            await client.post(
                "/plants", json={**plant_payload, "nickname": f"P{i}"}, headers=auth_headers
            )

        page = await client.get("/plants", params={"limit": 2, "offset": 1}, headers=auth_headers)

        assert [p["nickname"] for p in page.json()] == ["P1", "P2"]

    async def test_get_own_plant(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.get(f"/plants/{plant['id']}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == plant

    async def test_other_users_plant_is_404(
        self, client: AsyncClient, other_auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.get(f"/plants/{plant['id']}", headers=other_auth_headers)
        assert response.status_code == 404

    async def test_unknown_plant_is_404(
        self, client: AsyncClient, auth_headers: AuthHeaders
    ) -> None:
        response = await client.get(f"/plants/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404


class TestUpdate:
    async def test_partial_update_changes_only_sent_fields(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.patch(
            f"/plants/{plant['id']}", json={"nickname": "Jiboia do quarto"}, headers=auth_headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["nickname"] == "Jiboia do quarto"
        assert body["environment"] == plant["environment"]
        assert body["pot_volume_liters"] == plant["pot_volume_liters"]

    async def test_changing_species_returns_new_species(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        aloe = (await client.get("/species", params={"q": "Aloe"})).json()[0]

        response = await client.patch(
            f"/plants/{plant['id']}", json={"species_id": aloe["id"]}, headers=auth_headers
        )

        assert response.json()["species"]["common_name"] == "Babosa"

    async def test_rejects_unknown_species(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.patch(
            f"/plants/{plant['id']}", json={"species_id": str(uuid.uuid4())}, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_rejects_explicit_null(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.patch(
            f"/plants/{plant['id']}", json={"nickname": None}, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_cannot_update_other_users_plant(
        self,
        client: AsyncClient,
        auth_headers: AuthHeaders,
        other_auth_headers: AuthHeaders,
        plant: Plant,
    ) -> None:
        response = await client.patch(
            f"/plants/{plant['id']}", json={"nickname": "Roubada"}, headers=other_auth_headers
        )
        assert response.status_code == 404
        unchanged = await client.get(f"/plants/{plant['id']}", headers=auth_headers)
        assert unchanged.json()["nickname"] == plant["nickname"]


class TestDelete:
    async def test_deletes_own_plant(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.delete(f"/plants/{plant['id']}", headers=auth_headers)

        assert response.status_code == 204
        missing = await client.get(f"/plants/{plant['id']}", headers=auth_headers)
        assert missing.status_code == 404

    async def test_cannot_delete_other_users_plant(
        self,
        client: AsyncClient,
        auth_headers: AuthHeaders,
        other_auth_headers: AuthHeaders,
        plant: Plant,
    ) -> None:
        response = await client.delete(f"/plants/{plant['id']}", headers=other_auth_headers)

        assert response.status_code == 404
        still_there = await client.get(f"/plants/{plant['id']}", headers=auth_headers)
        assert still_there.status_code == 200
