# setup_instagram_auth.py
"""
Instagram authentication setup script.
1. First, tries to load existing session (no password needed).
2. If no session -> asks for login and password, saves session.
"""

import instaloader
from pathlib import Path
import os


SESSION_DIR = Path("./sessions")   # папка для хранения сессий
SESSION_DIR.mkdir(exist_ok=True)


def update_env(username: str):
    """Обновляет .env с логином и файлом сессии"""
    env_path = Path(".env")
    env_content = []

    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if not line.startswith("INSTAGRAM_USERNAME") and not line.startswith("INSTAGRAM_SESSION_FILE"):
                    env_content.append(line)

    env_content.append("\n# Instagram credentials\n")
    env_content.append(f"INSTAGRAM_USERNAME={username}\n")
    env_content.append(f"INSTAGRAM_SESSION_FILE={SESSION_DIR / username}\n")

    with open(env_path, "w") as f:
        f.writelines(env_content)

    print(f"✅ Updated .env with Instagram credentials")


def test_session(username: str):
    """Тестирует сохранённую сессию"""
    L = instaloader.Instaloader(quiet=True)
    try:
        L.load_session_from_file(username, SESSION_DIR / username)
        profile = instaloader.Profile.from_username(L.context, username)
        print(f"✅ Session test successful!")
        print(f"   Profile: @{profile.username}")
        print(f"   Followers: {profile.followers:,}")
        print(f"   Posts: {profile.mediacount:,}")
        return True
    except Exception as e:
        print(f"❌ Session test failed: {e}")
        return False


def create_session(username: str, password: str):
    """Создаёт новую сессию по логину и паролю"""
    L = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        save_metadata=False,
        compress_json=False
    )

    try:
        print(f"\n🔄 Logging in as {username}...")
        L.login(username, password)
        L.save_session_to_file(SESSION_DIR / username)
        print(f"✅ Session saved to {SESSION_DIR / username}")
        update_env(username)
        return test_session(username)
    except instaloader.exceptions.BadCredentialsException:
        print("❌ Invalid username or password")
        return False
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        print("⚠️ 2FA required!")
        code = input("Enter 2FA code: ").strip()
        try:
            L.two_factor_login(code)
            L.save_session_to_file(SESSION_DIR / username)
            print(f"✅ 2FA successful, session saved!")
            update_env(username)
            return test_session(username)
        except Exception as e:
            print(f"❌ 2FA failed: {e}")
            return False
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" ALTEL AI MODERATOR - Instagram Setup")
    print("=" * 60)

    username = input("Enter Instagram username: ").strip()
    if not username:
        print("❌ Username required")
        exit(1)

    session_file = SESSION_DIR / username

    if session_file.exists():
        print(f"🔎 Found existing session for {username}, testing...")
        if test_session(username):
            print("\n✅ Using existing session, no login required")
            exit(0)
        else:
            print("⚠️ Existing session invalid, creating new one")

    password = input("Enter Instagram password: ").strip()
    if not password:
        print("❌ Password required")
        exit(1)

    if create_session(username, password):
        print("\n✅ Instagram authentication setup complete!")
    else:
        print("\n❌ Setup failed, try again")
