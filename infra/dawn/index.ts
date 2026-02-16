import * as pulumi from "@pulumi/pulumi";
import * as openstack from "@pulumi/openstack";

import {
  accessRouterID,
  isolatedRouterID,
  isolatedRouterInternetID,
} from "./routers";

import {
  accessNetworkId,
  accessSubnetId,
  isolatedNetworkId,
  isolatedSubnetId,
} from "./networks";

import { bastionSgId, isolatedSgId, proxySgId } from "./security-groups";
import { createServers } from "./instances";

import * as lb from "./lb";

// create all servers
createServers();

export const outputs = {
  network: accessNetworkId,
  accessRouter: accessRouterID,
  isolatedRouter: isolatedRouterID,
  isolatedRouterInternet: isolatedRouterInternetID,
  accessSubnet: accessSubnetId,
  isolatedNetwork: isolatedNetworkId,
  isolatedSubnet: isolatedSubnetId,
  bastionSecurityGroup: bastionSgId,
  isolatedSecurityGroup: isolatedSgId,
  proxySecurityGroup: proxySgId,
};

export const k8sApiPublicEndPoint = lb.lbIp;
