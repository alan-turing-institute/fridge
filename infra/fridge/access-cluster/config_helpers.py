"""
Helpers for reading nested (object) Pulumi config keys.

`Pulumi.yaml` documents the fields of object keys such as `netbird` under `value:`.
Pulumi does not treat that as a schema: `value:` is the key's *default value*.
So when a stack leaves a field (or the whole object) unset, the program can receive
the field's description dict, e.g. `{"type": "string", "description": ..., "secret": True}`,
in place of a real value, and any `default:` written inside `value:` is never applied.

`ConfigObject` hides that: a field only counts as set when it holds a real scalar
(a non-empty string, a number or a bool), and defaults are applied in code.

Merging of project `value:` with partial stack config was NOT checked: the Pulumi
CLI was not available when this was written. If a stack that sets only some fields
gets the project `value:` merged in, unset fields arrive as description dicts; if
the stack object replaces it wholesale, unset fields are simply missing. Both cases
are treated as "unset" here, so the behaviour is the same either way.
"""

from collections.abc import Iterable, Mapping
from typing import Any

import pulumi


def is_set(value: Any) -> bool:
    """
    True if a config value is a real scalar value.

    None, empty or whitespace-only strings, and dicts/lists (including the
    description dicts from `Pulumi.yaml`) all count as unset.
    """
    if isinstance(value, str):
        return value.strip() != ""
    return isinstance(value, (bool, int, float))


class ConfigObject:
    """
    Read the fields of one object-valued config key, e.g. `netbird`.

    Presence is decided from the plain `config.get_object(key)` copy, because
    Pulumi needs to know at program time whether optional features exist.
    Secret fields are read through `config.require_secret_object(key)` so they
    stay secret Outputs; see `secret()`.
    """

    def __init__(
        self,
        config: pulumi.Config,
        key: str,
        *,
        defaults: Mapping[str, Any] | None = None,
        secret_fields: Iterable[str] = (),
    ) -> None:
        self.config = config
        self.key = key
        self.defaults = dict(defaults or {})
        # Only used to print `--secret` in the "how to set this" hint
        self.secret_fields = set(secret_fields)
        plain = config.get_object(key)
        self._plain: dict = plain if isinstance(plain, dict) else {}

    def _resolve(self, obj: Any, field: str) -> Any:
        value = obj.get(field) if isinstance(obj, dict) else None
        return value if is_set(value) else self.defaults.get(field)

    def set_command(self, field: str) -> str:
        """The CLI command that sets `field`, for error messages."""
        secret = " --secret" if field in self.secret_fields else ""
        return f"pulumi config set{secret} --path {self.key}.{field} <value>"

    def is_set(self, field: str) -> bool:
        """True if the stack sets `field` to a real value (defaults don't count)."""
        return is_set(self._plain.get(field))

    def require(self, *fields: str) -> None:
        """
        Raise a clear error listing every field in `fields` that is neither set nor defaulted.
        """
        missing = [f for f in fields if not self.is_set(f) and f not in self.defaults]
        if missing:
            commands = "\n".join(f"  {self.set_command(f)}" for f in missing)
            raise pulumi.RunError(
                f"Missing required config: {', '.join(f'{self.key}.{f}' for f in missing)}.\n"
                f"Set with:\n{commands}"
            )

    def get(self, field: str) -> Any:
        """
        Plain value of a scalar field, or its code-side default, or None.

        Don't use this for secret fields whose value ends up in resources; use `secret()`.
        """
        return self._resolve(self._plain, field)

    def get_object(self, field: str, keys: Iterable[str]) -> dict[str, Any]:
        """
        The set sub-fields of a nested object field, e.g. `endpoint_overrides`.

        Only `keys` are looked at, so the field's own description dict
        (`{"type": "object", "description": ..., "properties": {...}}`) yields `{}`.
        """
        sub = self._plain.get(field)
        if not isinstance(sub, dict):
            return {}
        return {k: sub[k] for k in keys if is_set(sub.get(k))}

    def secret(self, field: str) -> pulumi.Output:
        """
        `field` as a secret Output, falling back to its default.

        Raises at program time (via `require`) if the field is neither set nor defaulted.
        """
        self.require(field)
        return self.config.require_secret_object(self.key).apply(
            lambda obj: self._resolve(obj, field)
        )


NETBIRD_CLOUD_MANAGEMENT_URL = "https://api.netbird.io"
NETBIRD_ENDPOINT_KEYS = ("signal", "stun", "relay", "turn")


def netbird_config(config: pulumi.Config) -> ConfigObject:
    """The `netbird` config object, with its code-side defaults."""
    return ConfigObject(
        config,
        "netbird",
        defaults={"management_url": NETBIRD_CLOUD_MANAGEMENT_URL},
        secret_fields={"setup_key"},
    )
