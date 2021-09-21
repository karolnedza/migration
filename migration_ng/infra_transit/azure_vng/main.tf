resource "azurerm_subnet" "vng_gateway" {
  name                 = "GatewaySubnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = var.virtual_network_name
  address_prefixes     = var.address_prefixes
}

resource "azurerm_public_ip" "vng" {
  name                = "vng"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Dynamic"
}

resource "azurerm_virtual_network_gateway" "vng" {
  name                = "cloudN-vng"
  location            = var.location
  resource_group_name = var.resource_group_name

  type     = "ExpressRoute"
  vpn_type = "RouteBased"
  sku      = var.sku

  ip_configuration {
    public_ip_address_id          = azurerm_public_ip.vng.id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.vng_gateway.id
  }
}

resource "azurerm_virtual_network_gateway_connection" "vng_connection" {
  name                       = "cloudN-1"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  type                       = "ExpressRoute"
  virtual_network_gateway_id = azurerm_virtual_network_gateway.vng.id
  express_route_circuit_id   = var.express_route_circuit_id
}
