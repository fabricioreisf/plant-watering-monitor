from httpx import AsyncClient

from tests.conftest import PASSWORD, AuthHeaders

EMAIL = "carla@exemplo.com.br"


async def register(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD):
    return await client.post("/auth/register", json={"email": email, "password": password})


async def login(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD):
    return await client.post("/auth/login", data={"username": email, "password": password})


class TestRegister:
    async def test_creates_user_without_exposing_password(self, client: AsyncClient) -> None:
        response = await register(client)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == EMAIL
        assert "password" not in body
        assert "password_hash" not in body

    async def test_normalizes_email_to_lowercase(self, client: AsyncClient) -> None:
        response = await register(client, email="Carla@Exemplo.COM.br")
        assert response.json()["email"] == EMAIL

    async def test_rejects_duplicate_email_case_insensitively(self, client: AsyncClient) -> None:
        await register(client)
        response = await register(client, email=EMAIL.upper())
        assert response.status_code == 409

    async def test_rejects_short_password(self, client: AsyncClient) -> None:
        response = await register(client, password="curta")
        assert response.status_code == 422

    async def test_rejects_invalid_email(self, client: AsyncClient) -> None:
        response = await register(client, email="not-an-email")
        assert response.status_code == 422


class TestLogin:
    async def test_returns_access_and_refresh_tokens(self, client: AsyncClient) -> None:
        await register(client)
        response = await login(client)

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"] and body["refresh_token"]
        assert body["expires_in"] > 0

    async def test_email_is_case_insensitive(self, client: AsyncClient) -> None:
        await register(client)
        assert (await login(client, email=" CARLA@exemplo.com.br ")).status_code == 200

    async def test_wrong_password_and_unknown_email_look_the_same(
        self, client: AsyncClient
    ) -> None:
        await register(client)
        wrong_password = await login(client, password="senha-errada")
        unknown_email = await login(client, email="ninguem@exemplo.com.br")

        assert wrong_password.status_code == unknown_email.status_code == 401
        assert wrong_password.json() == unknown_email.json()


class TestCurrentUser:
    async def test_me_returns_authenticated_user(
        self, client: AsyncClient, auth_headers: AuthHeaders
    ) -> None:
        response = await client.get("/users/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "ana@exemplo.com.br"

    async def test_me_requires_token(self, client: AsyncClient) -> None:
        response = await client.get("/users/me")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_me_rejects_invalid_token(self, client: AsyncClient) -> None:
        response = await client.get("/users/me", headers={"Authorization": "Bearer garbage"})
        assert response.status_code == 401

    async def test_me_rejects_refresh_token(self, client: AsyncClient) -> None:
        await register(client)
        refresh_token = (await login(client)).json()["refresh_token"]
        response = await client.get(
            "/users/me", headers={"Authorization": f"Bearer {refresh_token}"}
        )
        assert response.status_code == 401


class TestRefresh:
    async def test_issues_new_working_tokens(self, client: AsyncClient) -> None:
        await register(client)
        tokens = (await login(client)).json()

        response = await client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert response.status_code == 200
        new_access = response.json()["access_token"]
        assert new_access != tokens["access_token"]
        me = await client.get("/users/me", headers={"Authorization": f"Bearer {new_access}"})
        assert me.status_code == 200

    async def test_rejects_access_token(self, client: AsyncClient) -> None:
        await register(client)
        access_token = (await login(client)).json()["access_token"]
        response = await client.post("/auth/refresh", json={"refresh_token": access_token})
        assert response.status_code == 401

    async def test_rejects_garbage(self, client: AsyncClient) -> None:
        response = await client.post("/auth/refresh", json={"refresh_token": "garbage"})
        assert response.status_code == 401
