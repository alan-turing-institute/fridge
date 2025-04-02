from pulumi_kubernetes.core.v1 import Namespace, Secret
from pulumi_random import RandomPassword


POSTGRES_PASSWORD_KEY = "postgres-password"

postgres_password = RandomPassword(
    POSTGRES_PASSWORD_KEY,
    length=32,
    special=False,
)

guacamole_ingress_namespace = Namespace(
    "guacamole",
    metadata={
        "name": "guacamole",
        "annotations": {
            "pod-security.kubernetes.io/enforce": "restricted",
            "pod-security.kubernetes.io/enforce-version": "latest"
        }
    }
)

guacamole_secret = Secret(
    "guacamole",
    metadata={
        "namespace": guacamole_ingress_namespace.metadata.name
    },
    string_data={
        POSTGRES_PASSWORD_KEY: postgres_password.result,
    }
)
