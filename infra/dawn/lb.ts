import * as openstack from "@pulumi/openstack";
import { accessSubnetId, isolatedSubnetId } from "./networks";

//Get the External Network Data
const externalNetwork = openstack.networking.getNetwork({
  name: "CUDN-Internet",
});

//Create the Load Balancer
const lb = new openstack.loadbalancer.LoadBalancer("k3s-lb", {
  vipSubnetId: accessSubnetId,
});

// Listner
const httpListner = new openstack.loadbalancer.Listener("http-listener", {
  protocol: "TCP",
  protocolPort: 80,
  loadbalancerId: lb.id,
});

const httpPool = new openstack.loadbalancer.Pool("ingress-pool", {
  protocol: "TCP",
  lbMethod: "ROUND_ROBIN",
  listenerId: httpListner.id,
});

const k3AccesNodeIps = ["10.10.0.252", "10.10.0.92", "10.10.0.240"];
// const nginxNodePorthttp = 32080;
const nginxNodePorthttp = 30180;
// const nginxNodePorthttps = 32443;
const nginxNodePorthttps = 30443;

k3AccesNodeIps.map((ip, index) => {
  new openstack.loadbalancer.Member(`access-member-${index}`, {
    address: ip,
    protocolPort: nginxNodePorthttp,
    poolId: httpPool.id,
    subnetId: accessSubnetId,
  });
});

// const k3IsolatedNodeIps = ["10.20.0.228", "10.20.0.244", "10.20.0.164"];

// k3IsolatedNodeIps.map((ip, index) => {
//   new openstack.loadbalancer.Member(`isolated-member-${index}`, {
//     address: ip,
//     protocolPort: nginxNodePorthttp,
//     poolId: httpPool.id,
//     subnetId: isolatedSubnetId,
//   });
// });

// add htpps listener
const httpsListner = new openstack.loadbalancer.Listener("https-listner", {
  protocol: "TCP",
  protocolPort: 443,
  loadbalancerId: lb.id,
});

const httpsPool = new openstack.loadbalancer.Pool("https-pool", {
  protocol: "TCP",
  lbMethod: "ROUND_ROBIN",
  listenerId: httpsListner.id,
});

k3AccesNodeIps.map((ip, index) => {
  new openstack.loadbalancer.Member(`access-member-https-${index}`, {
    address: ip,
    protocolPort: nginxNodePorthttps,
    poolId: httpsPool.id,
    subnetId: accessSubnetId,
  });
});

// k3IsolatedNodeIps.map((ip, index) => {
//   new openstack.loadbalancer.Member(`isolated-member-https-${index}`, {
//     address: ip,
//     protocolPort: nginxNodePorthttps,
//     poolId: httpsPool.id,
//     subnetId: isolatedSubnetId,
//   });
// });
/////////////////////////
//  Create TCP Listener for SSH
const sshListener = new openstack.loadbalancer.Listener("ssh-listener", {
  protocol: "TCP",
  protocolPort: 2222,
  loadbalancerId: lb.id,
});

//  Create Pool
const sshPool = new openstack.loadbalancer.Pool("ssh-pool", {
  protocol: "TCP",
  lbMethod: "ROUND_ROBIN",
  listenerId: sshListener.id,
});

// Add Access Cluster Nodes as Members
k3AccesNodeIps.map((ip, index) => {
  new openstack.loadbalancer.Member(`ssh-member-${index}`, {
    address: ip,
    protocolPort: 32222,
    poolId: sshPool.id,
    subnetId: accessSubnetId,
  });
});
///////////////////////////
// 3. Create the Floating IP using the validated pool name
const fip = new openstack.networking.FloatingIp(
  "lb-fip",
  {
    pool: externalNetwork.then((net) => net.name || "CUDN-Internet"),
  },
  { dependsOn: [lb] },
);

// 4. Associate using the LB's VIP Port ID
const fipAssoc = new openstack.networking.FloatingIpAssociate(
  "lb-fip-assoc",
  {
    floatingIp: fip.address,
    portId: lb.vipPortId,
  },
  { dependsOn: [fip] },
);

export const lbIp = fip.address;
