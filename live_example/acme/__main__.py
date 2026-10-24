"""Support python -m acme without running the CLI on import."""

from acme.cli import main

if __name__ == "__main__":
    main()
