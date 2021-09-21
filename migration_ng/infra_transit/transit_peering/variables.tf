variable "transit_gateways" {
  description = "List of transit gateway names and their ASNs to create full mesh peering from"
}

variable "excluded_cidrs" {
  type    = list(string)
  default = []
}

variable "as_prepend" {
  type    = bool
  default = false
}

variable "enable_peering_over_private_network" {
  type        = bool
  description = "Enable to use a private circuit for setting up peering"
  default     = false
}
