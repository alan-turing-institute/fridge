import * as openstack from "@pulumi/openstack";

import {
  isolatedNetworkId,
  publicNetworkId,
  accessNetworkId,
} from "./networks";
import { bastionSgId, isolatedSgId, proxySgId } from "./security-groups";
import { routersObj } from "./routers";

// function to create server ports
function createServerPorts(name: string): openstack.networking.Port {
  if (name.includes("bastion")) {
    return new openstack.networking.Port("operator-bastion-port", {
      name: "operator-bastion-port",
      networkId: accessNetworkId,
      adminStateUp: true,
      securityGroupIds: [bastionSgId],
      // adding this
      // Allow the bastion to handle forwarded traffic
      allowedAddressPairs: [{ ipAddress: "0.0.0.0/0" }],
    });
  } else if (name === "access-controller") {
    return new openstack.networking.Port("access-controller-port", {
      name: "access-controller-port",
      networkId: accessNetworkId,
      adminStateUp: true,
      securityGroupIds: [proxySgId],
    });
  } else if (name === "access-worker1") {
    return new openstack.networking.Port("access-worker1-port", {
      name: "access-worker1-port",
      networkId: accessNetworkId,
      adminStateUp: true,
      securityGroupIds: [proxySgId],
    });
  } else if (name === "access-worker2") {
    return new openstack.networking.Port("access-worker2-port", {
      name: "access-worker2-port",
      networkId: accessNetworkId,
      adminStateUp: true,
      securityGroupIds: [proxySgId],
    });
  } else if (name === "isolated-controller") {
    return new openstack.networking.Port("isolated-controller-port", {
      name: "isolated-controller-port",
      networkId: isolatedNetworkId,
      adminStateUp: true,
      securityGroupIds: [isolatedSgId],
    });
  } else if (name === "isolated-worker1") {
    return new openstack.networking.Port("isolated-worker1-port", {
      name: "isolated-worker1-port",
      networkId: isolatedNetworkId,
      adminStateUp: true,
      securityGroupIds: [isolatedSgId],
    });
  } else if (name === "isolated-worker2") {
    return new openstack.networking.Port("isolated-worker2-port", {
      name: "isolated-worker2-port",
      networkId: isolatedNetworkId,
      adminStateUp: true,
      securityGroupIds: [isolatedSgId],
    });
  } else {
    throw new Error(`Unknown server name: ${name}`);
  }
}

// create servers function

function createServers() {
  const servers: openstack.compute.Instance[] = [];
  const names = [
    "bastion-server",
    "access-controller-server",
    "access-worker1-server",
    "access-worker2-server",
    "isolated-controller-server",
    "isolated-worker1-server",
    "isolated-worker2-server",
  ];

  for (const name of names) {
    const flavorName =
      name.includes("isolated") && name.includes("worker")
        ? "vm.rcp.1x.pvc.1t.quarter"
        : "vm.v1.small";

    // generate port for server
    const port = createServerPorts(name.replace("-server", ""));
    const instance = new openstack.compute.Instance(
      name,
      {
        name,
        flavorName: flavorName,
        imageName: "Ubuntu-Jammy-22.04-20250318",
        keyPair: "bo307-mywsl1",
        networks: [{ port: port.id }],
      },
      {
        dependsOn: [
          routersObj.accessRouter,
          routersObj.isolatedRouter,
          // routersObj.isolatedRouterInternet,
        ],
      },
    );
    servers.push(instance);
    // create floating ip only for bastion server and associate it
    if (name === "bastion-server") {
      const bastionFip = new openstack.networking.FloatingIp(
        "bastion-floating-ip",
        {
          pool: "CUDN-Internet",
        },
      );

      new openstack.networking.FloatingIpAssociate("bastion-fip-assoc", {
        floatingIp: bastionFip.address,
        portId: port.id,
      });

      // export public IP

      (exports as any)["bastion_public_ip"] = bastionFip.address;
    }
    const exportName = name.replace(/-/g, "-") + "_ip";
    (exports as any)[exportName] = port.fixedIps.apply(
      (ips) => ips?.[0]?.ipAddress ?? "N/A",
    );
  }
  return servers;
}

export { createServers };
