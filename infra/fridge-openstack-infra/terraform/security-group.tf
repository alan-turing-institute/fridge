# resource "openstack_compute_keypair_v2" "access_key" {
#   name = var.keypair_name
#   public_key = var.public_key
# }

# security group to access proxies
resource "openstack_networking_secgroup_v2" "proxy_sg" {
  name = "allow-ssh-proxy"
}

resource "openstack_networking_secgroup_rule_v2" "ssh_in_proxy" {
  security_group_id = openstack_networking_secgroup_v2.proxy_sg.id
  direction = "ingress"
  ethertype = "IPv4"
  protocol = "tcp"
  port_range_min = 22
  port_range_max = 22
  remote_ip_prefix = var.ssh_private_cidr
}

resource "openstack_networking_secgroup_rule_v2" "icmp_in_proxy" {
  security_group_id = openstack_networking_secgroup_v2.proxy_sg.id
  direction = "ingress"
  ethertype = "IPv4"
  protocol = "icmp"
  remote_ip_prefix = var.ssh_private_cidr
}

# allow internetwork - private to isolated ?
resource "openstack_networking_secgroup_rule_v2" "access_to_isolated" {
  security_group_id = openstack_networking_secgroup_v2.proxy_sg.id
  direction = "ingress"
  ethertype = "IPv4"
  protocol = "tcp"
  port_range_min = 1
  port_range_max = 65535
  remote_ip_prefix = var.isolated_subnet_cidr
}


# security group to access bastion
resource "openstack_networking_secgroup_v2" "bastion_sg" {
  name = "allow-ssh-bastion"
  description = "allow ssh to bastion"
}

resource "openstack_networking_secgroup_rule_v2" "ssh_in_bastion" {
  security_group_id = openstack_networking_secgroup_v2.bastion_sg.id
  direction = "ingress"
  ethertype = "IPv4"
  protocol = "tcp"
  port_range_min = 22
  port_range_max = 22
  remote_ip_prefix = var.ssh_cidr_bastion
}

#security group restricted to isolated network

resource "openstack_networking_secgroup_v2" "isolated_sg" {
  name = "allow-proxy-instance"
  description = "allow only proxy instances"
}

resource "openstack_networking_secgroup_rule_v2" "ssh_in_isolated" {
  security_group_id = openstack_networking_secgroup_v2.isolated_sg.id
  direction = "ingress"
  ethertype = "IPv4"
  protocol = "tcp"
  port_range_min = 22
  port_range_max = 22
  remote_ip_prefix = var.ssh_cidr_isolated
}
