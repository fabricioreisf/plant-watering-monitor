import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import WateringLog
from tests.conftest import AuthHeaders

Plant = dict[str, object]


def url(plant: Plant) -> str:
    return f"/plants/{plant['id']}/waterings"


class TestCreate:
    async def test_defaults_to_now_and_full_watering(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        before = datetime.now(UTC)
        response = await client.post(url(plant), json={}, headers=auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert body["plant_id"] == plant["id"]
        assert body["amount_ml"] is None
        watered_at = datetime.fromisoformat(body["watered_at"])
        assert before - timedelta(seconds=1) <= watered_at <= datetime.now(UTC)

    async def test_accepts_past_time_and_amount(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        payload = {"watered_at": "2026-11-20T08:30:00-03:00", "amount_ml": 250}
        response = await client.post(url(plant), json=payload, headers=auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert body["amount_ml"] == 250
        assert datetime.fromisoformat(body["watered_at"]) == datetime(
            2026, 11, 20, 11, 30, tzinfo=UTC
        )

    async def test_rejects_future_time(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        response = await client.post(url(plant), json={"watered_at": future}, headers=auth_headers)
        assert response.status_code == 422

    async def test_rejects_time_without_timezone(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.post(
            url(plant), json={"watered_at": "2026-11-20T08:30:00"}, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_rejects_non_positive_amount(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.post(url(plant), json={"amount_ml": 0}, headers=auth_headers)
        assert response.status_code == 422

    async def test_cannot_log_on_other_users_plant(
        self, client: AsyncClient, other_auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.post(url(plant), json={}, headers=other_auth_headers)
        assert response.status_code == 404


class TestList:
    async def test_newest_first(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        for day in (20, 22, 21):
            await client.post(
                url(plant), json={"watered_at": f"2026-11-{day}T10:00:00Z"}, headers=auth_headers
            )

        response = await client.get(url(plant), headers=auth_headers)

        days = [datetime.fromisoformat(w["watered_at"]).day for w in response.json()]
        assert days == [22, 21, 20]

    async def test_other_user_cannot_list(
        self, client: AsyncClient, other_auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.get(url(plant), headers=other_auth_headers)
        assert response.status_code == 404


class TestDelete:
    async def test_deletes_own_log(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        log = (await client.post(url(plant), json={}, headers=auth_headers)).json()

        response = await client.delete(f"{url(plant)}/{log['id']}", headers=auth_headers)

        assert response.status_code == 204
        assert (await client.get(url(plant), headers=auth_headers)).json() == []

    async def test_other_user_cannot_delete(
        self,
        client: AsyncClient,
        auth_headers: AuthHeaders,
        other_auth_headers: AuthHeaders,
        plant: Plant,
    ) -> None:
        log = (await client.post(url(plant), json={}, headers=auth_headers)).json()

        response = await client.delete(f"{url(plant)}/{log['id']}", headers=other_auth_headers)

        assert response.status_code == 404
        assert len((await client.get(url(plant), headers=auth_headers)).json()) == 1

    async def test_log_must_belong_to_the_plant_in_the_url(
        self,
        client: AsyncClient,
        auth_headers: AuthHeaders,
        plant: Plant,
        plant_payload: Plant,
    ) -> None:
        other_plant = (
            await client.post("/plants", json=plant_payload, headers=auth_headers)
        ).json()
        log = (await client.post(url(plant), json={}, headers=auth_headers)).json()

        response = await client.delete(f"{url(other_plant)}/{log['id']}", headers=auth_headers)

        assert response.status_code == 404

    async def test_unknown_log_is_404(
        self, client: AsyncClient, auth_headers: AuthHeaders, plant: Plant
    ) -> None:
        response = await client.delete(f"{url(plant)}/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404

    async def test_deleting_plant_removes_its_logs(
        self,
        client: AsyncClient,
        auth_headers: AuthHeaders,
        plant: Plant,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        await client.post(url(plant), json={}, headers=auth_headers)
        await client.delete(f"/plants/{plant['id']}", headers=auth_headers)

        async with sessionmaker() as session:
            remaining = await session.scalar(select(func.count()).select_from(WateringLog))
        assert remaining == 0
