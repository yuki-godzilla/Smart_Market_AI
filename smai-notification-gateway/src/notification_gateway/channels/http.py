from __future__ import annotations

from typing import Mapping
from urllib.request import Request, urlopen

from notification_gateway.channels.base import HttpResponse


class UrllibHttpTransport:
    """Optional standard-library transport; channels depend only on HttpTransport."""

    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse:
        request = Request(
            url,
            data=data,
            headers=dict(headers),
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(status_code=response.status)
