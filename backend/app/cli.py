from .db import init_db
from .pipeline import run_daily_fetch


def main() -> None:
    init_db()
    results = run_daily_fetch()
    for result in results:
        print(
            f"source={result.source} fetched={result.fetched} inserted={result.inserted} error={result.errors}"
        )


if __name__ == "__main__":
    main()
