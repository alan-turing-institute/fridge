import * as openstack from "@pulumi/openstack";

const publicNetwork = openstack.networking.getNetworkOutput({
  name: "CUDN-Internet",
});

export const publicNetworkId = publicNetwork.id;

function createNetwork(name: string, cidr: string, useGateway: boolean = true) {
  const network = new openstack.networking.Network(`${name}-net`, {
    name: `${name}-net`,
    adminStateUp: true,
  });

  const subnet = new openstack.networking.Subnet(`${name}-subnet`, {
    name: `${name}-subnet`,
    networkId: network.id,
    cidr: cidr,
    ipVersion: 4,
    noGateway: !useGateway,
    dnsNameservers: ["131.111.8.42", "131.111.12.20"],
    ...({
      hostRoutes:
        name === "isolated"
          ? [
              {
                destinationCidr: "10.10.0.0/24",
                nextHop: "10.20.0.25",
              },
            ]
          : [],
    } as any),
  });

  return { network, subnet, networkId: network.id, subnetId: subnet.id };
}

const accessNet = createNetwork("access", "10.10.0.0/24", true);
// const isolatedNet = createNetwork("isolated", "10.20.0.0/24", false); // when no internet is required
const isolatedNet = createNetwork("isolated", "10.20.0.0/24", true); // when internet is required

// DIRECT ROUTE: Access -> Isolated

new openstack.networking.SubnetRoute("access-to-isolated-route", {
  subnetId: accessNet.subnetId,
  destinationCidr: "10.20.0.0/24",
  nextHop: "10.10.0.25",
});

// DIRECT ROUTE: Isolated -> Access
new openstack.networking.SubnetRoute("isolated-to-access-route", {
  subnetId: isolatedNet.subnetId,
  destinationCidr: "10.10.0.0/24",
  nextHop: "10.20.0.25",
});

export const accessNetworkId = accessNet.networkId;
export const accessSubnetId = accessNet.subnetId;
export const isolatedNetworkId = isolatedNet.networkId;
export const isolatedSubnetId = isolatedNet.subnetId;
