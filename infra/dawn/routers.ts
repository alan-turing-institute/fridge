import * as openstack from "@pulumi/openstack";
import {
  isolatedNetworkId,
  accessNetworkId,
  accessSubnetId,
  publicNetworkId,
  isolatedSubnetId,
} from "./networks";

function createConnectedRouters() {
  const accessRouter = new openstack.networking.Router("access-router", {
    name: "accessRouter",
    externalNetworkId: publicNetworkId,
  });

  const isolatedRouter = new openstack.networking.Router("isolated-router", {
    name: "isolatedRouter",
  });

  //Port connecting Isolated Router to Access Network
  const isolatedRouterAccessPort = new openstack.networking.Port(
    "iso-to-acc-port",
    {
      networkId: accessNetworkId,
      fixedIps: [{ ipAddress: "10.10.0.25" }],
      allowedAddressPairs: [{ ipAddress: "10.20.0.0/24" }],
    },
  );

  // Port connecting Isolated Router to Isolated Network
  const isolatedRouterInternalPort = new openstack.networking.Port(
    "iso-internal-port",
    {
      networkId: isolatedNetworkId,
      fixedIps: [{ subnetId: isolatedSubnetId, ipAddress: "10.20.0.25" }],
      allowedAddressPairs: [{ ipAddress: "10.10.0.0/24" }],
    },
  );

  //Attach Interfaces
  new openstack.networking.RouterInterface("access-iface", {
    routerId: accessRouter.id,
    subnetId: accessSubnetId,
  });

  new openstack.networking.RouterInterface("isolated-to-access-iface", {
    routerId: isolatedRouter.id,
    portId: isolatedRouterAccessPort.id,
  });

  new openstack.networking.RouterInterface("isolated-to-isolated-iface", {
    routerId: isolatedRouter.id,
    portId: isolatedRouterInternalPort.id,
  });

  //TEMPORARY INTERNET ROUTER
  const isolatedRouterInternet = new openstack.networking.Router(
    "iso-router-internet",
    {
      name: "isolated-router-internet",
      externalNetworkId: publicNetworkId,
    },
  );

  new openstack.networking.RouterInterface("iso-router-internet-iface", {
    routerId: isolatedRouterInternet.id,
    subnetId: isolatedSubnetId,
  });

  return {
    accessRouter,
    isolatedRouter,
    isolatedRouterInternet,
  };
}

const routers = createConnectedRouters();

export const routersObj = {
  accessRouter: routers.accessRouter,
  isolatedRouter: routers.isolatedRouter,
  isolatedRouterInternet: routers.isolatedRouterInternet,
};

export const accessRouterID = routers.accessRouter.id;
export const isolatedRouterID = routers.isolatedRouter.id;
export const isolatedRouterInternetID = routers.isolatedRouterInternet.id;
