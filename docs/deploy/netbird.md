# Connecting to FRIDGE

Connections to FRIDGE use the Netbird VPN client.

You will require access to a Netbird Management server.
For testing, the free Netbird cloud management server is sufficient.
However, for production, we recommend using [self-hosted Netbird](https://docs.netbird.io/selfhosted/selfhosted-quickstart).

## Configuring Netbird

You will need to configure a machine with the Netbird agent to connect to Netbird agent inside FRIDGE.

The machine that you configure should have the hostname `home-tre`.
This will ensure that the peer registered with netbird has the expected internal FQDN - `home-tre.netbird.cloud` - expected by the VPN pod configured within the FRIDGE.

In the Netbird management console, you will need to generate a setup key for use within the FRIDGE.
Configure that setup key to automatically register the peer using it as a member of the `fridge` group.

Create a second setup key that register a peer using it as a member of the `home-tre` group.


## Enabling user access to the FRIDGE API


## Enabling admin access to the Kubernetes API
