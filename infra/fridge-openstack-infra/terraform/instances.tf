# create a port

resource "openstack_networking_port_v2" "kubeproxy_isolated_port" {
  name = "kubeproxy-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}

resource "openstack_networking_port_v2" "fridgeproxy_isolated_port" {
  name = "fridgeproxy-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}

resource "openstack_networking_port_v2" "kubeproxy_private_port" {
  name = "kubeproxy-access-port"
  network_id = openstack_networking_network_v2.private_network.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.private_subnet.id
  }
}

resource "openstack_networking_port_v2" "fridgeproxy_private_port" {
  name = "fridgeproxy-access-port"
  network_id = openstack_networking_network_v2.private_network.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.private_subnet.id
  }
}

# instances
resource "openstack_compute_instance_v2" "kubeproxy" {
  name = "kubeproxy"
  image_name = var.image_name
  flavor_name = var.flavor_name
#   key_pair = openstack_compute_keypair_v2.access_key.name 
  key_pair = var.keypair_name
  security_groups = [ openstack_networking_secgroup_v2.proxy_sg.name ]
  network {
    port = openstack_networking_port_v2.kubeproxy_private_port.id 
  }
  network {
    port = openstack_networking_port_v2.kubeproxy_isolated_port.id
  }
}

resource "openstack_compute_instance_v2" "fridgeproxy" {
  name = "fridgeproxy"
  image_name = var.image_name
  flavor_name = var.flavor_name
#   key_pair = openstack_compute_keypair_v2.access_key.name 
  key_pair = var.keypair_name
  security_groups = [ openstack_networking_secgroup_v2.proxy_sg.name ]
  network {
    port = openstack_networking_port_v2.fridgeproxy_private_port.id 
  }
  network {
    port = openstack_networking_port_v2.fridgeproxy_isolated_port.id
  }
}

# # floating ip 
# resource "openstack_networking_floatingip_v2" "kubeproxy_fip" {
#   pool = var.external_network_name
# #   port = openstack_networking_port_v2.kubeproxy_private_port.id
#   port_id = openstack_networking_port_v2.kubeproxy_private_port.id
# }

# resource "openstack_networking_floatingip_v2" "fridgeproxy_fip" {
#   pool = var.external_network_name
# #   port = openstack_networking_port_v2.kubeproxy_private_port.id
#   port_id = openstack_networking_port_v2.fridgeproxy_private_port.id
# }

# create port for bastion
resource "openstack_networking_port_v2" "bastion_private_port" {
  name = "bastion-access-port"
  network_id = openstack_networking_network_v2.private_network.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.private_subnet.id
  }
}

# create port for kubeapi
resource "openstack_networking_port_v2" "kubeapi_isolated_port" {
  name = "kubeapi-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id 
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}

# instances - bastion 

resource "openstack_compute_instance_v2" "bastion" {
  name = "operator-bastion"
  image_name = var.image_name
  flavor_name = var.flavor_name
#   key_pair = openstack_compute_keypair_v2.access_key.name 
  key_pair = var.keypair_name
  security_groups = [ openstack_networking_secgroup_v2.bastion_sg.name ]
  network {
    port = openstack_networking_port_v2.bastion_private_port.id
  }

}

# allocate floating ip
resource "openstack_networking_floatingip_v2" "bastion_fip" {
  pool = var.external_network_name
}

#associate floating ip

resource "openstack_compute_floatingip_associate_v2" "bastion_fip_assoc" {
  floating_ip = openstack_networking_floatingip_v2.bastion_fip.address
  instance_id = openstack_compute_instance_v2.bastion.id
}

# instance kube API VM in isolated network

resource "openstack_compute_instance_v2" "kubeapi" {
  name = "kubeapi"
  image_name = var.image_name
  flavor_name = var.flavor_name
  key_pair = var.keypair_name 
  security_groups = [ openstack_networking_secgroup_v2.isolated_sg.name ]
  network {
     port = openstack_networking_port_v2.kubeapi_isolated_port.id
  }
}