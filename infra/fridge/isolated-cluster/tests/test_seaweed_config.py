"""Test component registration without a Pulumi engine or Kubernetes cluster.

From the repository root, install the isolated-cluster requirements and pytest,
then run: pytest infra/fridge/isolated-cluster/tests
"""

import importlib.util
from pathlib import Path
import socket
import sys

import pulumi
from pulumi.runtime import MockResourceArgs, Mocks, set_mocks
from pulumi.runtime.mocks import MockMonitor
from pulumi_kubernetes.core.v1 import Namespace
import pytest


CLUSTER_ROOT = Path(__file__).resolve().parents[1]
# Loading the module directly avoids the deployment's components/__init__.py.
sys.path.insert(0, str(CLUSTER_ROOT))
spec = importlib.util.spec_from_file_location(
    "seaweed_config_under_test", CLUSTER_ROOT / "components" / "seaweed_config.py"
)
seaweed_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seaweed_config)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unit tests must not contact external services")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


class ResourceMocks(Mocks):
    def new_resource(self, args: MockResourceArgs):
        return f"{args.name}-id", args.inputs

    def call(self, args):
        raise AssertionError(f"Unexpected provider invocation: {args.token}")


class RecordingMonitor(MockMonitor):
    def __init__(self, mocks):
        super().__init__(mocks)
        self.output_registrations = []
        self.resource_requests = []

    def RegisterResource(self, request):
        self.resource_requests.append(request)
        return super().RegisterResource(request)

    def RegisterResourceOutputs(self, request):
        self.output_registrations.append(request)
        return super().RegisterResourceOutputs(request)


class SyntheticConfig:
    def __init__(self):
        self.requested = []

    def require_secret(self, key):
        self.requested.append(key)
        return pulumi.Output.secret(f"synthetic-{key}")


class StorageFixture(pulumi.ComponentResource):
    def __init__(self):
        super().__init__("tests:fixture:Storage", "storage")
        self.seaweedfs_ns = Namespace(
            "storage-namespace",
            metadata={"name": "seaweedfs-test"},
            opts=pulumi.ResourceOptions(parent=self),
        )
        self.seaweedfs_s3_endpoint = pulumi.Output.from_input("s3.example.invalid")
        self.register_outputs({})


def build_component(preview):
    mocks = ResourceMocks()
    monitor = RecordingMonitor(mocks)
    set_mocks(
        mocks, project="unit-tests", stack="test", preview=preview, monitor=monitor
    )
    config = SyntheticConfig()
    result = {}

    @pulumi.runtime.test
    def construct():
        storage = StorageFixture()
        component = seaweed_config.SeaweedConfigJob(
            "config", seaweed_config.SeaweedConfigArgs(config, storage)
        )
        return pulumi.Output.all(component.urn, storage.seaweedfs_ns.urn).apply(
            lambda urns: result.update(component=urns[0], namespace=urns[1])
        )

    construct()
    return monitor, config, result


@pytest.mark.parametrize("preview", [False, True])
def test_component_reports_completion(preview):
    monitor, _, urns = build_component(preview)

    registrations = [
        entry
        for entry in monitor.output_registrations
        if entry.urn == urns["component"]
    ]

    assert len(registrations) == 1
    assert not registrations[0].outputs.fields


@pytest.mark.parametrize("preview", [False, True])
def test_job_resources_and_security_settings_are_preserved(preview):
    monitor, config, urns = build_component(preview)
    resources = monitor.get_registered_resources()
    child_requests = [
        entry
        for entry in monitor.resource_requests
        if entry.parent == urns["component"]
    ]
    assert {entry.type for entry in child_requests} == {
        "kubernetes:core/v1:ConfigMap",
        "kubernetes:core/v1:Secret",
        "kubernetes:batch/v1:Job",
    }
    assert len(child_requests) == 3
    job_request = next(entry for entry in child_requests if entry.type.endswith(":Job"))
    assert urns["namespace"] in job_request.dependencies
    job = next(
        value.state
        for key, value in resources.items()
        if key.endswith("::seaweedfs-config-job")
    )
    assert job["metadata"]["namespace"] == "seaweedfs-test"
    assert job["spec"]["backoffLimit"] == 2
    assert job["spec"]["ttlSecondsAfterFinished"] == 3600
    pod = job["spec"]["template"]["spec"]
    assert pod["restartPolicy"] == "Never"
    assert pod["automountServiceAccountToken"] is False
    container = pod["containers"][0]
    assert container["command"] == ["/bin/sh", "-c"]
    assert container["args"] == ["/tmp/scripts/setup.sh"]
    assert container["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"] == {"drop": ["ALL"]}
    env = {entry["name"]: entry for entry in container["env"]}
    assert env["S3_URL"]["value"] == "https://s3.example.invalid"
    assert env["S3_ACCESS_KEY"]["valueFrom"]["secretKeyRef"]["key"] == "accessKey"
    assert env["S3_SECRET_KEY"]["valueFrom"]["secretKeyRef"]["key"] == "secretKey"
    assert config.requested == ["s3_admin_access_key", "s3_admin_secret_key"]
