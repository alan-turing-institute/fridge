import * as k8s from "@pulumi/kubernetes";

//Create the ingress-nginx namespace
const ingressNamespace = new k8s.core.v1.Namespace("ingress-nginx", {
  metadata: { name: "ingress-nginx" },
});

//Install the ingress-nginx Helm chart
const nginxIngress = new k8s.helm.v3.Chart(
  "ingress-nginx",
  {
    chart: "ingress-nginx",
    version: "4.14.3",
    fetchOpts: {
      repo: "https://kubernetes.github.io/ingress-nginx",
    },
    namespace: ingressNamespace.metadata.name,
    values: {
      controller: {
        service: {
          type: "NodePort",
          nodePorts: {
            http: 30180,
            https: 30443,
            tcp: {
              "2222": 32222,
            },
          },
        },
        tcp: {
          "2222": "default/jump-host-svc:2222",
        },
      },
      tcp: {
        "2222": "default/jump-host-svc:2222",
      },
    },
  },
  { dependsOn: [ingressNamespace] },
);

export const ingressNamespaceName = ingressNamespace.metadata.name;
