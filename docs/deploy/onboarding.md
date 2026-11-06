# AIRR onboarding

Deploying FRIDGE on shared research infrastructure requires a small set of information to be exchanged between the hosting organisation and the TRE administrators before deployment begins.

## Information from TRE administrators

The TRE administrators should provide the hosting organisation with:

- approved source IP addresses or CIDR ranges for access to FRIDGE resources, including bastion hosts and any load balancers whose access is restricted by source address;
- approved SSH public keys for administrators who need to connect to bastion hosts.

Keep these values limited to the people and networks that require access. If they change, provide the updated values to the hosting organisation before changing the deployment configuration.

## Information from the hosting organisation

The hosting organisation should provide the TRE administrators with the addresses required to configure and reach the deployment.

For Dawn this includes:

- the public IP address of the SSH bastion host used for cluster administration;
- the public IP address of the FRIDGE load balancer;
- the internal IP address of the isolated Kubernetes API endpoint (the controller-server address), used by network policies in the access cluster.

For other AIRR platforms, provide the equivalent public and internal endpoints required by that platform's FRIDGE deployment.

## Before deployment

Before starting the deployment, confirm that:

- approved IP addresses or CIDR ranges have been exchanged and are current;
- required administrator SSH public keys have been exchanged;
- the hosting organisation has supplied the required public endpoints;
- where required by the platform, internal cluster endpoints needed by FRIDGE network policies have also been supplied.
