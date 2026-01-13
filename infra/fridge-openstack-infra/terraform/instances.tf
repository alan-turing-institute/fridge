# create a port

resource "openstack_networking_port_v2" "controller_isolated_port" {
  name = "controller-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}


resource "openstack_networking_port_v2" "worker1_isolated_port" {
  name = "worker1-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}

# worker 2 port
resource "openstack_networking_port_v2" "worker2_isolated_port" {
  name = "worker2-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}


# Create port for private network

resource "openstack_networking_port_v2" "controller_private_port" {
  name = "controller-access-port"
  network_id = openstack_networking_network_v2.private_network.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.private_subnet.id
  }
}


resource "openstack_networking_port_v2" "worker1_private_port" {
  name = "worker1-access-port"
  network_id = openstack_networking_network_v2.private_network.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.private_subnet.id
  }
}

resource "openstack_networking_port_v2" "worker2_private_port" {
  name = "worker2-access-port"
  network_id = openstack_networking_network_v2.private_network.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.private_subnet.id
  }
}


# instances

resource "openstack_compute_instance_v2" "controller" {
  name = "controller"
  image_name = var.image_name
  flavor_name = var.flavor_name_small
  key_pair = var.keypair_name
  security_groups = [ openstack_networking_secgroup_v2.proxy_sg.name ]
  network {
    port = openstack_networking_port_v2.controller_private_port.id #kubeproxy_private_port.id 
  }
  network {
    port = openstack_networking_port_v2.controller_isolated_port.id # kubeproxy_isolated_port.id
  }
}


#worker1

resource "openstack_compute_instance_v2" "worker1" {
  name = "worker1"
  image_name = var.image_name
  flavor_name = var.flavor_name_small
  key_pair = var.keypair_name
  security_groups = [ openstack_networking_secgroup_v2.proxy_sg.name ]
  network {
    port = openstack_networking_port_v2.worker1_private_port.id 
  }
  network {
    port = openstack_networking_port_v2.worker1_isolated_port.id 
  }
}



#worker2 instance
resource "openstack_compute_instance_v2" "worker2" {
  name = "worker2"
  image_name = var.image_name
  flavor_name = var.flavor_name_small
  key_pair = var.keypair_name
  security_groups = [ openstack_networking_secgroup_v2.proxy_sg.name ]
  network {
    port = openstack_networking_port_v2.worker2_private_port.id
  }
  network {
    port = openstack_networking_port_v2.worker2_isolated_port.id
  }
}


# create port for bastion
resource "openstack_networking_port_v2" "bastion_private_port" {
  name = "bastion-access-port"
  network_id = openstack_networking_network_v2.private_network.id
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.private_subnet.id
  }
}



# instances - bastion 

resource "openstack_compute_instance_v2" "bastion" {
  name = "operator-bastion"
  image_name = var.image_name
  flavor_name = var.flavor_name_xsmall
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

# create port for kubeapi
resource "openstack_networking_port_v2" "kubeapi_controller_isolated_port" {
  name = "kubeapi_controller-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id 
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}


resource "openstack_compute_instance_v2" "kubeapi_controller" {
  name = "kubeapi_controller"
  image_name = var.image_name
  flavor_name = var.flavor_name_small
  key_pair = var.keypair_name 
  security_groups = [ openstack_networking_secgroup_v2.isolated_sg.name ]
  network {
     port = openstack_networking_port_v2.kubeapi_controller_isolated_port.id
  }
}

resource "openstack_networking_port_v2" "kubeapi_worker1_isolated_port" {
  name = "kubeapi_worker1-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id 
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}

resource "openstack_compute_instance_v2" "kubeapi_worker1" {
  name = "kubeapi_worker1"
  image_name = var.image_name
  flavor_name = var.flavor_name_small
  key_pair = var.keypair_name 
  security_groups = [ openstack_networking_secgroup_v2.isolated_sg.name ]
  network {
     port = openstack_networking_port_v2.kubeapi_worker1_isolated_port.id
  }
}

resource "openstack_networking_port_v2" "kubeapi_worker2_isolated_port" {
  name = "kubeapi_worker2-isolated-port"
  network_id = openstack_networking_network_v2.isolated_net.id 
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.isolated_subnet.id
  }
}

resource "openstack_compute_instance_v2" "kubeapi_worker2" {
  name = "kubeapi_worker2"
  image_name = var.image_name
  flavor_name = var.flavor_name_small
  key_pair = var.keypair_name 
  security_groups = [ openstack_networking_secgroup_v2.isolated_sg.name ]
  network {
     port = openstack_networking_port_v2.kubeapi_worker2_isolated_port.id
  }
}

