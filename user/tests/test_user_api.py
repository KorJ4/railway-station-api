from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

REGISTER_URL = reverse("user:create")
TOKEN_URL = reverse("user:token_obtain_pair")
ME_URL = reverse("user:manage")


class UserApiTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()

    def test_register_user(self) -> None:
        payload = {"email": "new@railway.com", "password": "password123"}

        res = self.client.post(REGISTER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(email=payload["email"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertNotIn("password", res.data)

    def test_register_with_short_password_returns_400(self) -> None:
        payload = {"email": "new@railway.com", "password": "short"}

        res = self.client.post(REGISTER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_obtain_jwt_and_get_profile(self) -> None:
        get_user_model().objects.create_user("me@railway.com", "password123")

        res = self.client.post(
            TOKEN_URL, {"email": "me@railway.com", "password": "password123"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {res.data['access']}"
        )
        me = self.client.get(ME_URL)

        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["email"], "me@railway.com")

    def test_me_requires_auth(self) -> None:
        res = self.client.get(ME_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
