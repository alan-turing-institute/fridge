variable "openstack_cloud" {
  type = string
  description = "openstack project name"
  default = "ai-fridge-dev"
}

variable "kube_proxy_instance_name" {
  type = string
   description = "kube proxy instance name"
   default = "kubeproxy"
}

variable "fridge_proxy_instance_name" {
  type = string
   description = "fridge proxy instance name"
   default = "fridgeproxy"
}

variable "operator_bastion_name" {
  type = string
   description = "operator bastion instance name"
   default = "operator-bastion"
}

variable "kubeapi_instance_name" {
  type = string
   description = "kubeapi instance name"
   default = "kubeapi"
}

variable "flavor_name" {
  type = string
  default = "vm.v1.xsmall"
}

variable "image_name" {
  type = string
  default = "Ubuntu-Jammy-22.04-20250318"
}

variable "private_network" {
  type = string
  description = "private network"
  default = "private-net"
}

variable "isolated_network" {
  type = string
  description = "isolated network"
  default = "isolated-net"
}

variable "private_subnet_cidr" {
  type = string
  description = "CIDR - private netwrok"
  default = "10.10.0.0/24"
}
variable "isolated_subnet_cidr" {
  type = string
  description = "CIDR - isolated network"
  default = "10.20.0.0/24"
}
variable "external_network_name" {
  type = string
  description = "External floating IP network"
  default = "CUDN-Internet"
}

variable "keypair_name" {
  type = string
  default = "bo307-mywsl1"
}

variable "ssh_private_cidr" {  # note
  description = "ssh allowed cidr"
  type = string
  default = "10.10.0.0/24"
}
variable "ssh_cidr_bastion" {
  description = "ssh allowed cidr for bastion"
  type = string
  default = "0.0.0.0/0"
}

variable "ssh_cidr_isolated" {
  description = "only allow ssh from proxies"
  type = string
  default = "10.20.0.0/24"
}