# output "kubeproxy_floating_ip" {
#   value = openstack_networking_floatingip_v2.kubeproxy_fip.address
# }

# output "fridgeproxy_floating_ip" {
#   value = openstack_networking_floatingip_v2.fridgeproxy_fip.address
# }

output "kubeproxy_isolated_ip" {
  value = openstack_networking_port_v2.kubeproxy_isolated_port.fixed_ip[0].ip_address
}

output "fridgeproxy_isolated_ip" {
  value = openstack_networking_port_v2.fridgeproxy_isolated_port.fixed_ip[0].ip_address
}
output "private_subnet_cidr" {
  value = openstack_networking_subnet_v2.private_subnet.cidr
}

output "isolated_subnet_cidr" {
  value = openstack_networking_subnet_v2.isolated_subnet.cidr
}

output "kubeapi_isolated_ip" {
  value = openstack_compute_instance_v2.kubeapi.access_ip_v4
}