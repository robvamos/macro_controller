"""Bootstrap rapido per il database Doomsday locale."""

from doomsday.services.bootstrap_service import bootstrap_doomsday_data


def main():
    result = bootstrap_doomsday_data()
    print("Bootstrap Doomsday completato.")
    print(result)


if __name__ == "__main__":
    main()
