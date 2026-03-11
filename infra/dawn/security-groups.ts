import * as openstack from "@pulumi/openstack";
import { group } from "console";

//create a function that creates bastion security group and rules

function createSecurityGroups(name: string): openstack.networking.SecGroup {
  if (name.includes("bastion")) {
    const bastionSecurityGroup = new openstack.networking.SecGroup(
      `${name}-sg`,
      {
        name: `${name}-sg`,
        description: "Allow SSH ",
      },
    );

    //   create security group rules
    if (bastionSecurityGroup) {
      new openstack.networking.SecGroupRule(`${name}-ssh`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 22,
        portRangeMax: 22,
        remoteIpPrefix: "0.0.0.0/0",
        securityGroupId: bastionSecurityGroup.id,
      });
      return bastionSecurityGroup;
    }
  }

  if (name.includes("isolated")) {
    const isolatedSecurityGroup = new openstack.networking.SecGroup(
      `${name}-sg`,
      {
        name: `${name}-sg`,
        description: "Allow internal traffic and SSH from bastion ",
      },
    );
    //   create security group rules
    if (isolatedSecurityGroup) {
      new openstack.networking.SecGroupRule("proxy-k3s-api-isolated-net", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 6443,
        portRangeMax: 6443,
        remoteIpPrefix: "10.20.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule("proxy-k3s-api-access-net", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 6443,
        portRangeMax: 6443,
        remoteIpPrefix: "10.10.0.0/24", //fix this
        securityGroupId: isolatedSecurityGroup.id,
      });

      new openstack.networking.SecGroupRule("proxy-udp-isolated-net", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "udp",
        portRangeMin: 8472,
        portRangeMax: 8472,
        remoteIpPrefix: "10.20.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });

      new openstack.networking.SecGroupRule("allow-icmp-from-access-network", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "icmp",
        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-icmp`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "icmp",
        remoteIpPrefix: "10.20.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-ssh-from-access-net`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 22,
        portRangeMax: 22,
        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-https`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 443,
        portRangeMax: 443,
        remoteIpPrefix: "10.20.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-http`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 80,
        portRangeMax: 80,
        remoteIpPrefix: "10.20.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-nodeport1`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 30180,
        portRangeMax: 30180,
        remoteIpPrefix: "10.20.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-nodeport2`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 30443,
        portRangeMax: 30443,
        remoteIpPrefix: "10.20.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-nodeport3`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 30180,
        portRangeMax: 30180,

        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      // new openstack.networking.SecGroupRule("jump-host-ssh-isolated", {
      //   direction: "ingress",
      //   ethertype: "IPv4",
      //   protocol: "tcp",
      //   portRangeMin: 2222,
      //   portRangeMax: 2222,
      //   securityGroupId: isolatedSecurityGroup.id,
      // });
      new openstack.networking.SecGroupRule("pod-cidr-isolated1", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 30180,
        portRangeMax: 30180,
        remoteIpPrefix: "10.42.0.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      new openstack.networking.SecGroupRule("pod-cidr-isolated2", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 30180,
        portRangeMax: 30180,
        remoteIpPrefix: "10.42.1.0/24",
        securityGroupId: isolatedSecurityGroup.id,
      });
      return isolatedSecurityGroup;
    }
  }

  if (name.includes("proxy")) {
    const proxySecurityGroup = new openstack.networking.SecGroup(`${name}-sg`, {
      name: `${name}-sg`,
      description: "Allow SSH from bastion and k3s",
    });
    //   create security group rules
    if (proxySecurityGroup) {
      new openstack.networking.SecGroupRule(`${name}-ssh-bastion`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 22,
        portRangeMax: 22,
        remoteGroupId: bastionSg.id,
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-k3s-api-bastion`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 6443,
        portRangeMax: 6443,
        remoteGroupId: bastionSg.id,
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(
        `${name}-k3s-api-access-net-proxysg`,
        {
          direction: "ingress",
          ethertype: "IPv4",
          protocol: "tcp",
          portRangeMin: 6443,
          portRangeMax: 6443,
          remoteIpPrefix: "10.10.0.0/24",
          securityGroupId: proxySecurityGroup.id,
        },
      );
      new openstack.networking.SecGroupRule(`${name}-udp-access-net`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "udp",
        portRangeMin: 8472,
        portRangeMax: 8472,
        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule("isolated-ssh-from-controller", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 22,
        portRangeMax: 22,
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-proxy_https`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 443,
        portRangeMax: 443,
        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-proxy_http`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 80,
        portRangeMax: 80,
        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-nodeport1`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 30180,
        portRangeMax: 30180,
        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-nodeport2`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 30443,
        portRangeMax: 30443,
        remoteIpPrefix: "10.10.0.0/24",
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule(`${name}-http-any`, {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 80,
        portRangeMax: 80,
        remoteIpPrefix: "0.0.0.0/0",
        securityGroupId: proxySecurityGroup.id,
      });
      //   below was commented out before
      new openstack.networking.SecGroupRule("jump-host-ssh-access", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 2222,
        portRangeMax: 2222,
        remoteIpPrefix: "0.0.0.0/0",
        securityGroupId: proxySecurityGroup.id,
      });
      new openstack.networking.SecGroupRule("allow-node-security-access", {
        direction: "ingress",
        ethertype: "IPv4",
        protocol: "tcp",
        portRangeMin: 32222,
        portRangeMax: 32222,
        remoteIpPrefix: "0.0.0.0/0",
        securityGroupId: proxySecurityGroup.id,
      });
      // new openstack.networking.SecGroupRule("allow-cilium-agents-access", {
      //   direction: "ingress",
      //   ethertype: "IPv4",
      //   protocol: "tcp",
      //   portRangeMin: 4240,
      //   portRangeMax: 4240,
      //   remoteIpPrefix: "10.10.0.0/24",
      //   securityGroupId: proxySecurityGroup.id,
      // });
      // new openstack.networking.SecGroupRule("allow-hubble-relay-access", {
      //   direction: "ingress",
      //   ethertype: "IPv4",
      //   protocol: "tcp",
      //   portRangeMin: 4244,
      //   portRangeMax: 4244,
      //   remoteIpPrefix: "10.10.0.0/24",
      //   securityGroupId: proxySecurityGroup.id,
      // });
      return proxySecurityGroup;
    }
  }
  throw new Error("Unknow security group");
}
//create a function that creates proxy security group and rules

const bastionSg = createSecurityGroups("bastion");
const isolatedSg = createSecurityGroups("isolated");
const proxySg = createSecurityGroups("proxy");

export const bastionSgId = bastionSg.id;
export const isolatedSgId = isolatedSg.id;
export const proxySgId = proxySg.id;
