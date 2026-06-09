"""Exceptions raised by dkn_cloud_na."""

from __future__ import annotations


class DknError(Exception):
    """Base class for all dkn_cloud_na errors."""


class DknAuthError(DknError):
    """Login failed or the session could not be (re)authenticated."""


class DknConnectionError(DknError):
    """A network/transport error talking to the cloud or socket."""


class DknApiError(DknError):
    """The API returned an error response.

    The backend signals errors with a JSON body containing an ``_id`` field
    (e.g. ``userNotExist``, ``tokenNotFound``); it is exposed as ``error_id``.
    """

    def __init__(self, message: str, *, status: int | None = None, error_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.error_id = error_id
