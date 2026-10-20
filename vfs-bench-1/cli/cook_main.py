import sys

from cli_main import run_cli
from cook_cli import COOK, CookConfig

if __name__ == "__main__":
    sys.exit(run_cli("cook", COOK, CookConfig, {"corpus": "HOWTOCOOK_CORPUS"}))
