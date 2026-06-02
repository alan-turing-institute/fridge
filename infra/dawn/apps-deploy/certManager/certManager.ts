import * as k8s from "@pulumi/kubernetes";

// create cert-manager namespace
const certManagerNamespace = new k8s.core.v1.Namespace("cert-manager", {
  metadata: { name: "cert-manager" },
});

const certManager = new k8s.helm.v3.Chart("cert-manager", {
  chart: "cert-manager",
  version: "v1.19.1",
  fetchOpts: {
    repo: "https://charts.jetstack.io",
  },
  namespace: certManagerNamespace.metadata.name,
  values: {
    installCRDs: true,
  },
});

export const namespace = certManagerNamespace.metadata.name;
