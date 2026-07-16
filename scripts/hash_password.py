import getpass

from app.core.security import hash_password


def main() -> None:
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not password or password != confirmation:
        raise SystemExit("Passwords are empty or do not match")
    print(hash_password(password))


if __name__ == "__main__":
    main()
