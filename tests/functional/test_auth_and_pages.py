import pytest
import app

pytestmark = pytest.mark.functional


class TestRegistration:
    def test_register_success(self, client):
        r = client.post("/register", data={"username": "a", "password": "b"})
        assert r.status_code == 200 and "Account created" in r.text
        assert app.load_user("a") is not None

    def test_password_stored_hashed(self, client):
        client.post("/register", data={"username": "a", "password": "plain"})
        assert app.load_user("a")["password"] == app.hash_pw("plain")
        assert "plain" not in str(app.load_user("a"))

    def test_duplicate_username_rejected(self, client):
        client.post("/register", data={"username": "a", "password": "b"})
        r = client.post("/register", data={"username": "a", "password": "c"})
        assert "already exists" in r.text

    def test_blank_username_rejected(self, client):
        r = client.post("/register", data={"username": "   ", "password": "b"})
        assert "required" in r.text

    def test_missing_fields_is_422(self, client):
        assert client.post("/register", data={"username": "a"}).status_code == 422


class TestLogin:
    def test_login_redirects_with_token_and_cookie(self, client, user):
        r = client.post("/login", data={"username": "afrin", "password": "pw12345"})
        assert r.status_code == 303 and "/chat?t=" in r.headers["location"]
        assert "sm_tok" in r.headers["set-cookie"] and "httponly" in r.headers["set-cookie"].lower()

    def test_unknown_user(self, client):
        assert "User not found" in client.post("/login", data={"username": "x", "password": "y"}).text

    def test_wrong_password(self, client, user):
        assert "Incorrect password" in client.post("/login", data={"username": "afrin", "password": "nope"}).text


class TestAccessControl:
    @pytest.mark.parametrize("path", ["/chat", "/new", "/chat/123"])
    def test_protected_pages_redirect_anonymous(self, client, path):
        r = client.get(path)
        assert r.status_code in (302, 307) and r.headers["location"] == "/"

    def test_api_chat_requires_auth(self, client):
        r = client.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 401 and r.json() == {"error": "unauthorized"}

    def test_invalid_token_is_rejected(self, client):
        assert client.get("/chat?t=forged").status_code in (302, 307)

    def test_root_shows_login_when_anonymous(self, client):
        assert "Login" in client.get("/").text or "login" in client.get("/").text

    def test_root_redirects_when_authenticated(self, client, user):
        assert client.get(f"/?t={user[1]}").status_code in (302, 307)

    def test_logout_invalidates_session(self, client, user):
        _, tok = user
        assert client.get(f"/chat?t={tok}").status_code == 200
        client.get(f"/logout?t={tok}")
        assert client.get(f"/chat?t={tok}").status_code in (302, 307)

    def test_user_cannot_read_another_users_chat(self, client, user, text_model):
        _, tok = user
        client.post(f"/api/chat?t={tok}", json={"sid": "s1", "message": "my secret question"})
        client.post("/register", data={"username": "mallory", "password": "pw"})
        r = client.post("/login", data={"username": "mallory", "password": "pw"})
        mtok = r.headers["location"].split("t=")[1]
        page = client.get(f"/chat/s1?t={mtok}")
        assert "my secret question" not in page.text


class TestPages:
    def test_new_chat_page(self, client, user):
        r = client.get(f"/new?t={user[1]}")
        assert r.status_code == 200 and "StudyMate" in r.text

    def test_chat_home_empty_state(self, client, user):
        assert client.get(f"/chat?t={user[1]}").status_code == 200

    def test_chat_home_opens_latest_chat(self, client, user, text_model):
        client.post(f"/api/chat?t={user[1]}", json={"sid": "s1", "message": "first"})
        assert "first" in client.get(f"/chat?t={user[1]}").text

    def test_history_renders_markdown_not_raw_asterisks(self, client, user, text_model):
        # regression: reload path after first message must show formatted text
        text_model.reply = "**Key Points**\n## Summary\n- one"
        client.post(f"/api/chat?t={user[1]}", json={"sid": "s1", "message": "q"})
        html = client.get(f"/chat/s1?t={user[1]}").text
        assert "<strong>Key Points</strong>" in html
        assert "**Key Points**" not in html and "## Summary" not in html

    def test_user_message_html_is_escaped_in_history(self, client, user, text_model):
        client.post(f"/api/chat?t={user[1]}", json={"sid": "s1", "message": "<script>alert(1)</script>"})
        html = client.get(f"/chat/s1?t={user[1]}").text
        assert "<script>alert(1)</script>" not in html
