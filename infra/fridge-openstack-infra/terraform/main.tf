terraform {
  required_version = ">= 1.1.0"
  required_providers {
    openstack = {
        source = "terraform-provider-openstack/openstack"
        version = "~> 1.48.0"
    }
  }
}

provider "openstack" {
  cloud = var.openstack_cloud
}