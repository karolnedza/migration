resource "azurerm_express_route_circuit" "cloudN" {
  name                  = "cloudN-ExpressRoute"
  resource_group_name   = "s5-vnet-rg-01"
  location              = "West US"
  service_provider_name = "Equinix"
  peering_location      = "Silicon Valley"
  bandwidth_in_mbps     = 50
  sku {
    tier   = "Standard"
    family = "MeteredData"
  }
  allow_classic_operations = false
}

resource "azurerm_express_route_circuit_peering" "cloudN" {
  peering_type                  = "AzurePrivatePeering"
  express_route_circuit_name    = azurerm_express_route_circuit.cloudN.name
  resource_group_name           = "s5-vnet-rg-01"
  peer_asn                      = 65000              # on prem router ASN
  primary_peer_address_prefix   = "10.255.255.20/30" # IP prefix for ER
  secondary_peer_address_prefix = "10.255.255.24/30" # IP prefix for backup ER
  vlan_id                       = 806                # ER VLAN
}

module "aviatrix-create-vng" {
  source = "./azure_vng"

  location                 = "West US"
  resource_group_name      = "s5-vnet-rg-01"
  virtual_network_name     = "s5-mt01-vnet-westus-14"
  address_prefixes         = [cidrsubnet("10.51.4.0/23", 4, 15)] # Azure recommends /27
  sku                      = "Standard"                          # "UltraPerformance" for 10G
  express_route_circuit_id = azurerm_express_route_circuit.cloudN.id

  depends_on = [azurerm_express_route_circuit_peering.cloudN]
}
