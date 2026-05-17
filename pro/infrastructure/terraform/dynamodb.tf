# State table — single item per row.
#   pk = "state"            holds the BroadcastState JSON
#   pk = "conn#<id>"        one row per WebSocket connection
#   ttl                     epoch seconds; AWS sweeps stale rows automatically
resource "aws_dynamodb_table" "state" {
  name         = "${local.resource_prefix}-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = !var.use_localstack
  }

  tags = {
    Project = var.project_name
  }
}
