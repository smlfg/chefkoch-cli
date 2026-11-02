"""Fehlerklassen mit festem Exit-Code und JSON-Typ."""

from __future__ import annotations


class CliError(Exception):
    exit_code = 1
    error_type = "internal"

    def __init__(self, message: str, *, next_step: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.next_step = next_step

    def full_message(self) -> str:
        if self.next_step:
            return f"{self.message} {self.next_step}".strip()
        return self.message


class UsageError(CliError):
    exit_code = 2
    error_type = "usage"


class StateError(CliError):
    exit_code = 1
    error_type = "state"


class ConfigError(CliError):
    exit_code = 1
    error_type = "internal"


class UserAbortError(CliError):
    exit_code = 1
    error_type = "internal"


class NetworkError(CliError):
    exit_code = 3
    error_type = "network"


class HttpError(CliError):
    exit_code = 3
    error_type = "http"


class NotFoundError(CliError):
    exit_code = 3
    error_type = "not_found"


class NoResultsError(CliError):
    exit_code = 3
    error_type = "no_results"


class ParseError(CliError):
    exit_code = 4
    error_type = "parse"
