"""Security regression tests (found by this suite)."""
import json, os
import pytest
import app

pytestmark = pytest.mark.functional


class TestXss:
    def test_sidebar_title_escaped(self, client, user, text_model):
        client.post(f"/api/chat?t={user[1]}", json={"sid": "s1", "message": "<img src=x onerror=alert(1)>"})
        html = client.get(f"/chat/s1?t={user[1]}").text
        assert "<img src=x" not in html

    def test_username_escaped_in_header(self, client):
        client.post("/register", data={"username": "<b>x</b>", "password": "p"})
        r = client.post("/login", data={"username": "<b>x</b>", "password": "p"})
        if r.status_code == 303:   # if registration allowed it, it must still be escaped
            html = client.get(r.headers["location"]).text
            assert "<b>x</b>" not in html


class TestPathTraversal:
    def test_session_token_cannot_point_at_user_file(self, client, user):
        """Without validation, ?t=../user_data/afrin reads user_data/afrin.json as a 'session'
        and authenticates the attacker as that user with no password."""
        r = client.get("/chat?t=../user_data/afrin")
        assert r.status_code in (302, 307)

    def test_api_chat_with_traversal_token_unauthorized(self, client, user):
        r = client.post("/api/chat?t=../user_data/afrin", json={"message": "hi"})
        assert r.status_code == 401

    def test_logout_cannot_delete_arbitrary_json(self, client, user, tmp_path):
        victim = tmp_path / "user_data" / "afrin.json"
        assert victim.exists()
        client.get("/logout?t=../user_data/afrin")
        assert victim.exists()

    @pytest.mark.parametrize("name", ["../evil", "..\\evil", "a/b", "a\x00b", ".hidden/../x", ""])
    def test_malicious_usernames_rejected(self, client, tmp_path, name):
        r = client.post("/register", data={"username": name, "password": "p"})
        assert "Account created" not in r.text
        assert not (tmp_path / "evil.json").exists()
        assert not list(tmp_path.glob("*.json"))

    def test_load_user_ignores_traversal(self):
        assert app.load_user("../sessions/x") is None

    @pytest.mark.parametrize("name", ["afrin", "a.b-c_d", "User123"])
    def test_valid_usernames_still_allowed(self, client, name):
        assert "Account created" in client.post("/register", data={"username": name, "password": "p"}).text
