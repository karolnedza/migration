data "google_compute_zones" "az" {
  status = "UP"
}

resource "google_compute_network" "transit" {
  name                    = var.vpc_name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "aviatrix_public" {
  name          = "aviatrix-transit"
  ip_cidr_range = var.vpc_cidr
  region        = var.region
  network       = google_compute_network.transit.id
}

resource "aviatrix_transit_gateway" "atgw" {
  cloud_type                    = 4
  account_name                  = var.account_name
  gw_name                       = "${trimprefix(var.vpc_name, "aviatrix-")}-gw"
  vpc_id                        = google_compute_network.transit.name
  vpc_reg                       = data.google_compute_zones.az.names[0]
  ha_zone                       = data.google_compute_zones.az.names[1]
  insane_mode                   = var.hpe
  gw_size                       = var.avtx_gw_size
  ha_gw_size                    = var.avtx_gw_size
  subnet                        = google_compute_subnetwork.aviatrix_public.ip_cidr_range
  ha_subnet                     = google_compute_subnetwork.aviatrix_public.ip_cidr_range
  enable_active_mesh            = true
  connected_transit             = true
  bgp_ecmp                      = true
  enable_advertise_transit_cidr = false
  enable_transit_firenet        = var.enable_firenet
  local_as_number               = var.local_as_number
  bgp_polling_time              = var.bgp_polling_time
}

resource "aviatrix_transit_external_device_conn" "dummy" {
  vpc_id            = join("~-~",[google_compute_network.transit.name,google_compute_network.transit.project])
  connection_name   = google_compute_network.transit.name
  gw_name           = aviatrix_transit_gateway.atgw.gw_name
  connection_type   = "bgp"
  enable_ikev2      = true
  bgp_local_as_num  = var.local_as_number
  bgp_remote_as_num = "65000"
  remote_gateway_ip = "1.1.1.1"
}


