from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model

from ninja_jwt.compat import reverse
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import AccessToken

from .utils import APIViewTestCase

User = get_user_model()


@pytest.mark.django_db
class TestTestView(APIViewTestCase):
    view_name = "jwt:test_view"

    @pytest.fixture(autouse=True)
    def setUp(self):
        super().setUp()
        self.username = "test_user"
        self.password = "test_password"

        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
        )

    def test_no_authorization(self):
        res = self.view_get()

        assert res.status_code == 401
        assert "Unauthorized" in res.data["detail"]

    def test_wrong_auth_type(self):
        res = self.view_post(
            url=reverse("jwt:token_obtain_sliding"),
            data={
                User.USERNAME_FIELD: self.username,
                "password": self.password,
            },
            content_type="application/json",
        )

        token = res.data["token"]
        self.authenticate_with_token("Wrong", token)

        res = self.view_get()

        assert res.status_code == 401
        assert "Unauthorized" in res.data["detail"]

    def test_expired_token(self, monkeypatch):
        old_lifetime = AccessToken.lifetime
        AccessToken.lifetime = timedelta(seconds=0)
        try:
            res = self.view_post(
                url=reverse("jwt:token_obtain_pair"),
                data={
                    User.USERNAME_FIELD: self.username,
                    "password": self.password,
                },
                content_type="application/json",
            )
        finally:
            AccessToken.lifetime = old_lifetime

        access = res.data["access"]
        self.authenticate_with_token("Bearer", access)

        with monkeypatch.context() as m:
            m.setattr(
                api_settings, "AUTH_TOKEN_CLASSES", ("ninja_jwt.tokens.AccessToken",)
            )
            res = self.view_get()

        assert res.status_code == 401
        assert "token_not_valid" == res.data["code"]

    def test_user_can_get_sliding_token_and_use_it(self, monkeypatch):
        res = self.view_post(
            url=reverse("jwt:token_obtain_sliding"),
            data={
                User.USERNAME_FIELD: self.username,
                "password": self.password,
            },
            content_type="application/json",
        )

        token = res.data["token"]
        self.authenticate_with_token("Bearer", token)

        with monkeypatch.context() as m:
            m.setattr(
                api_settings, "AUTH_TOKEN_CLASSES", ("ninja_jwt.tokens.SlidingToken",)
            )
            res = self.view_get()

        assert res.status_code == 200
        assert res.data["foo"] == "bar"

    def test_user_can_get_access_and_refresh_tokens_and_use_them(self, monkeypatch):
        res = self.view_post(
            url=reverse("jwt:token_obtain_pair"),
            data={
                User.USERNAME_FIELD: self.username,
                "password": self.password,
            },
            content_type="application/json",
        )

        access = res.data["access"]
        refresh = res.data["refresh"]

        self.authenticate_with_token("Bearer", access)

        with monkeypatch.context() as m:
            m.setattr(
                api_settings, "AUTH_TOKEN_CLASSES", ("ninja_jwt.tokens.AccessToken",)
            )
            res = self.view_get()

        assert res.status_code == 200
        assert res.data["foo"] == "bar"

        res = self.view_post(
            url=reverse("jwt:token_refresh"),
            data={"refresh": refresh},
            content_type="application/json",
        )

        access = res.data["access"]

        self.authenticate_with_token("Bearer", access)
        with monkeypatch.context() as m:
            m.setattr(
                api_settings, "AUTH_TOKEN_CLASSES", ("ninja_jwt.tokens.AccessToken",)
            )
            res = self.view_get()

        assert res.status_code == 200
        assert res.data["foo"] == "bar"
