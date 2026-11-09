# ------------------------------------------------------------ Network (IAC-03)
#
# A small VPC with two public subnets and no NAT gateway (saves ~$32/month). The app task gets a
# public IP for outbound calls to AWS APIs, but its security group allows no inbound traffic at all.
# Operators reach it through an SSM port-forwarding tunnel (make proxy, IAC-06).
# Production path: private subnets with VPC endpoints for Bedrock, SageMaker, S3 and OpenSearch.

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.40.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.name_prefix}-igw" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false # ECS assigns a public IP per task explicitly
  tags                    = { Name = "${var.name_prefix}-public-${count.index}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${var.name_prefix}-public" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Strip the VPC's default security group of all rules so nothing can use it by accident.
resource "aws_default_security_group" "default" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.name_prefix}-default-unused" }
}

# The app task: no inbound rules; outbound HTTPS only (AWS APIs, OpenSearch).
resource "aws_security_group" "app" {
  name        = "${var.name_prefix}-app"
  description = "DealPulse app task: no inbound, outbound HTTPS only"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${var.name_prefix}-app" }
}

resource "aws_vpc_security_group_egress_rule" "app_https" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS to AWS APIs and OpenSearch"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}
