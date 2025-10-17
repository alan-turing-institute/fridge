# private netwrok with access to the internet

resource "openstack_networking_network_v2" "private_network" {
  name = var.private_network
}

resource "openstack_networking_subnet_v2" "private_subnet" {
  name = "${var.private_network}-subnet"
  network_id = openstack_networking_network_v2.private_network.id
  cidr = var.private_subnet_cidr
  ip_version = 4
  dns_nameservers = [ "131.111.8.42", "131.111.12.20" ]
  enable_dhcp = true
}

# router conneting private network to the external network
resource "openstack_networking_router_v2" "private_router" {
  name = "${var.private_network}-router"
  external_network_id = data.openstack_networking_network_v2.external_network.id 

}

resource "openstack_networking_router_interface_v2" "private_router_interface" {
  router_id = openstack_networking_router_v2.private_router.id
  subnet_id = openstack_networking_subnet_v2.private_subnet.id
}

# isolated network
resource "openstack_networking_network_v2" "isolated_net" {
  name = var.isolated_network
}

resource "openstack_networking_subnet_v2" "isolated_subnet" {
  name = "${var.isolated_network}-subnet"
  network_id = openstack_networking_network_v2.isolated_net.id
  cidr = var.isolated_subnet_cidr
  ip_version = 4
  dns_nameservers = [ "131.111.8.42", "131.111.12.20" ]
  enable_dhcp = true
}


data "openstack_networking_network_v2" "external_network"{
    name = var.external_network_name
}


# create temporary router to route traffic in isolated network to install k3s etc
# router conneting private network to the external network
# resource "openstack_networking_router_v2" "isolated_router" {
#   name = "${var.isolated_network}-router"
#   external_network_id = data.openstack_networking_network_v2.external_network.id 

# }

# resource "openstack_networking_router_interface_v2" "isolated_router_interface" {
#   router_id = openstack_networking_router_v2.isolated_router.id
#   subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
# }
