#!/usr/bin/env python3
"""Sobe o bot do Telegram. Fica rodando até você interromper com Ctrl+C."""

import logging
import sys

from inbox import config
from inbox.bot import Bot


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        Bot(config.load()).run()
    except KeyboardInterrupt:
        print("\nbot encerrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
