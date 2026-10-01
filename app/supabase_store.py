import os
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests


class SupabaseRestClient:
    """Small service-role PostgREST client for server-side persistence."""

    def __init__(self, url: str, service_role_key: str, timeout: int = 10):
        if not url or not service_role_key:
            raise ValueError("Supabase URL and service-role key are required.")
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.service_role_key = service_role_key
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> Optional["SupabaseRestClient"]:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url and not key:
            return None
        if not url or not key:
            raise RuntimeError("Both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured.")
        return cls(url, key)

    def request(
        self,
        method: str,
        resource: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Any = None,
        prefer: Optional[str] = None,
    ) -> Any:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = requests.request(
                method,
                f"{self.base_url}/{resource}",
                headers=headers,
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise RuntimeError("Supabase database request failed.") from error
        if not response.ok:
            try:
                detail = response.json().get("message", response.text)
            except ValueError:
                detail = response.text
            raise SupabaseRequestError(response.status_code, str(detail))
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise RuntimeError("Supabase returned an invalid database response.") from error

    def insert(self, table: str, values: Dict[str, Any]) -> Dict[str, Any]:
        result = self.request(
            "POST",
            quote(table, safe=""),
            json=values,
            prefer="return=representation",
        )
        if not isinstance(result, list) or not result:
            raise RuntimeError(f"Supabase did not return the inserted {table} record.")
        return result[0]


class SupabaseRequestError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
