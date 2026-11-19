"""
Helpers for reading object-valued Pulumi config keys, such as `netbird` and `monitoring`.

A stack that sets an object key replaces the project's `value:` for it entirely: an
unset `netbird.hostname` is simply missing, not filled in from Pulumi.yaml (checked
with `pulumi preview`). So the fields described under `value:` in Pulumi.yaml are
documentation only. Pulumi does not check them, and any `default:` there is not
applied, so required fields are checked and defaults applied in code.
"""

from collections.abc import Iterable
from typing import Any

import pulumi

NETBIRD_CLOUD_MANAGEMENT_URL = "https://api.netbird.io"


def is_set(value: Any) -> bool:
    """True for a non-empty string or another scalar; False for None, "" or a dict."""
    if isinstance(value, str):
        return value.strip() != ""
    return isinstance(value, (bool, int, float))


def require_fields(
    config: pulumi.Config,
    key: str,
    fields: Iterable[str],
    secret_fields: Iterable[str] = (),
) -> dict:
    """
    Check that every field in `fields` of the object `key` is set.

    Raises one error listing each missing field with the command that sets it.
    Returns the plain object, for checking optional fields; read values that are
    secret from `config.require_secret_object(key)` instead.
    """
    obj = config.get_object(key)
    obj = obj if isinstance(obj, dict) else {}
    secret_fields = set(secret_fields)

    missing = [f for f in fields if not is_set(obj.get(f))]
    if missing:
        commands = "\n".join(
            f"  pulumi config set{' --secret' if f in secret_fields else ''} "
            f"--path {key}.{f} <value>"
            for f in missing
        )
        raise pulumi.RunError(
            f"Missing required config: {', '.join(f'{key}.{f}' for f in missing)}.\n"
            f"Set with:\n{commands}"
        )
    return obj
