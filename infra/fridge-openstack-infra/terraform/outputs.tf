output "bastion_fip_floating_ip" {
  value = openstack_networking_floatingip_v2.bastion_fip.address
}

# output "controller_isolated_ip" {
#   value = openstack_networking_port_v2.controller_isolated_port.fixed_ip[0].ip_address
# }

# output "worker1_isolated_ip" {
#   value = openstack_networking_port_v2.worker1_isolated_port.fixed_ip[0].ip_address
# }
output "private_subnet_cidr" {
  value = openstack_networking_subnet_v2.private_subnet.cidr
}

output "isolated_subnet_cidr" {
  value = openstack_networking_subnet_v2.isolated_subnet.cidr
}

# output "kubeapi_isolated_ip" {
#   value = openstack_compute_instance_v2.kubeapi.access_ip_v4
# }