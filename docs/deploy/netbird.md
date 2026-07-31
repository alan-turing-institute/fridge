# Connecting to FRIDGE using Netbird

You will require access to a Netbird Management server.
For testing, the free Netbird cloud management server is sufficient.
However, for production, we recommend using [self-hosted Netbird](https://docs.netbird.io/selfhosted/selfhosted-quickstart).

## Configuring Netbird

Once you have access to a Netbird management server, you are ready to begin setup.

The FRIDGE deployment controls the movement of traffic within the FRIDGE itself, but you will also need to configure [network access within Netbird](https://docs.netbird.io/manage/access-control/manage-network-access).
We make use of Groups and Access Policies.
Individual Netbird peers can be associated with Groups.
A peer is allowed to access any other resource in Groups it is associated with.

Access Policies can be used to determine which Groups of peers can connect to each other, as well as in which directions and on what ports.

We recommend creating Groups for

You will need to configure a machine with the Netbird agent to connect to the Netbird agent inside FRIDGE.

In the Netbird management console, you will need to generate a setup key for use within the FRIDGE.
Configure that setup key to automatically register the peer using it as a member of the `fridge` group.

Create a second setup key that register a peer using it as a member of the `home-tre` group.

Netbird groups

Netbird policies


## Enabling user access to the FRIDGE API


## Enabling admin access to the Kubernetes API
