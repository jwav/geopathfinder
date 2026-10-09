"""Local, file-based configuration for GeoPathfinder."""

from __future__ import annotations

from pathlib import Path

from geopathfinder.exceptions import ConfigurationError


ORS_API_KEY_RELATIVE_PATH = Path("api_keys") / "ORS_API_KEY.key"
"""Default location of the local ORS key, relative to the project directory."""


def default_ors_api_key_file() -> Path:
    """Locate the default ORS key file without using environment variables.

    Prefer a key file beside the directory from which the CLI is launched. This
    makes a normal installed package usable. When running the editable project
    checkout from elsewhere, fall back to its project-local key file.
    """

    current_directory_file = Path.cwd() / ORS_API_KEY_RELATIVE_PATH
    if current_directory_file.is_file():
        return current_directory_file
    return Path(__file__).resolve().parents[2] / ORS_API_KEY_RELATIVE_PATH


def load_ors_api_key(key_file: Path | None = None) -> str:
    """Read the ORS key from a local text file without exposing its value."""

    path = key_file if key_file is not None else default_ors_api_key_file()
    try:
        raw_key = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ConfigurationError(
            f"ORS API key file not found: {path}. "
            "Create it and put the Basic Key on one line."
        ) from error
    except OSError as error:
        raise ConfigurationError(f"Unable to read the ORS API key file: {path}.") from error

    api_key = raw_key.strip()
    if not api_key or any(character.isspace() for character in api_key):
        raise ConfigurationError(
            f"ORS API key file must contain one non-empty key: {path}."
        )
    return api_key
