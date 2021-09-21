resource "aws_main_route_table_association" "$rname" {
  vpc_id = "$vpc_id"
  route_table_id = "$route_table_id"
  provider = $provider
}
