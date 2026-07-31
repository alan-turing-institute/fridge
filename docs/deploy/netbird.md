# Connecting to FRIDGE using Netbird

You will require access to a Netbird Management server.
For testing, the free Netbird cloud management server is sufficient.
However, for production, we recommend using [self-hosted Netbird](https://docs.netbird.io/selfhosted/selfhosted-quickstart).

## Configuring Netbird

Once you have access to a Netbird management server, you are ready to begin setting up your mesh VPN network.

FRIDGE will deploy with a Netbird agent present in the access cluster.
You will need to provide a [setup key](https://docs.netbird.io/manage/peers/register-machines-using-setup-keys) at the time of deployment to automatically connect the agent to your mesh network.
Before creating the setup key, we recommend first setting up the configuration of your mesh network.

The FRIDGE deployment controls the movement of traffic within the FRIDGE itself, but you will also need to configure [network access within Netbird](https://docs.netbird.io/manage/access-control/manage-network-access).
We make use of Groups and Access Policies.
Individual Netbird peers can be associated with Groups.
A peer is allowed to access any other resource in Groups it is associated with.

Access Policies can be used to determine which Groups of peers can connect to each other, as well as in which directions and on what ports.

We recommend creating three Groups, into which you will place one or more peers:
1. A Group for the Netbird peer in the access cluster (e.g. `api-access`)
2. A Group for TRE Operator administrator devices (e.g. `tre-admin`)
3. A Group for TRE User access (e.g. `tre-user`)

Peers can be manually placed in these groups after creation.
It is also possible to create setup keys that automatically place peers in groups when they are used.
We recommend doing this, particularly for the Netbird peer in the access cluster.

Any TRE Operator administrator devices that are intended to be used for communication with the Kubernetes API of the isolated cluster should be allocated to the `tre-admin` group.

You can then create Access policies that allow traffic to flow between each of these groups in specific ways.

Inside the access cluster, traffic to Netbird on port 443 will be routed to the Kubernetes API of the isolated cluster.
Traffic on port 8000 will be routed to the FRIDGE API in the isolated cluster.

Thus, two access policies should be created.
1. An access policy that allows traffic to flow from the `tre-admin` group to `api-access` on port 443
2. An access policy that allows traffic to flow from the `tre-user` group to `api-access` on port 8000

## Enabling user access to the FRIDGE API


## Enabling admin access to the Kubernetes API
