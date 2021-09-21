data "google_compute_zones" "az" {
  status = "UP"
}

resource "google_compute_network" "spoke" {
  name                    = var.vpc_name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "aviatrix_public" {
  name          = "aviatrix-spoke-gw"
  ip_cidr_range = var.aviatrix_cidr
  region        = var.region
  network       = google_compute_network.spoke.id
}

resource "aviatrix_spoke_gateway" "gw" {
  cloud_type         = 4
  account_name       = var.account_name
  gw_name            = "gcp-${var.vpc_name}-gw"
  vpc_id             = google_compute_network.spoke.name
  vpc_reg            = data.google_compute_zones.az.names[0]
  ha_zone            = data.google_compute_zones.az.names[1]
  insane_mode        = var.hpe
  gw_size            = var.avtx_gw_size
  ha_gw_size         = var.avtx_gw_size
  subnet             = google_compute_subnetwork.aviatrix_public.ip_cidr_range
  ha_subnet          = google_compute_subnetwork.aviatrix_public.ip_cidr_range
  manage_transit_gateway_attachment = false
  enable_active_mesh                = true
}

resource "aviatrix_spoke_transit_attachment" "attachment" {
  count           = var.hpe && var.detach_gw ? 0 : 1
  spoke_gw_name   = aviatrix_spoke_gateway.gw.gw_name
  transit_gw_name = "gcp-${var.region}-transit-gw"
}
