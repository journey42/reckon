#!/bin/bash

# Constants with uppercase and underscores
RESOURCE_GROUP="reckon-rg"
LOCATION="eastus"
VM_NAME="reckon"
VM_SIZE="Standard_B1s"
IMAGE="Ubuntu2204"
ADMIN_USERNAME="reckon"
SSH_KEY_PATH="~/.ssh/id_rsa.pub"
DNS_LABEL_PREFIX="reckon" # This should be unique across Azure

# Create a resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create a virtual network and subnet if not already existing
VNET_NAME="reckon-vnet"
SUBNET_NAME="reckon-subnet"
az network vnet create \
  --resource-group $RESOURCE_GROUP \
  --name $VNET_NAME \
  --subnet-name $SUBNET_NAME

# Create a public IP with DNS name
PUBLIC_IP_NAME="reckon-public-ip"
az network public-ip create \
  --resource-group $RESOURCE_GROUP \
  --name $PUBLIC_IP_NAME \
  --dns-name $DNS_LABEL_PREFIX \
  --allocation-method Static

# Create a network security group and open ports 22, 80, 443
NSG_NAME="reckon-nsg"
az network nsg create \
  --resource-group $RESOURCE_GROUP \
  --name $NSG_NAME

# Create security rules

# az network nsg rule create \
#   --resource-group $RESOURCE_GROUP \
#   --nsg-name $NSG_NAME \
#   --name "CUSTOM_APP_RULE" \
#   --protocol Tcp \
#   --priority 1030 \
#   --destination-port-range 8000 \
#   --access Allow

az network nsg rule create \
  --resource-group $RESOURCE_GROUP \
  --nsg-name $NSG_NAME \
  --name "SSH_RULE" \
  --protocol Tcp \
  --priority 1000 \
  --destination-port-range 22 \
  --access Allow

az network nsg rule create \
  --resource-group $RESOURCE_GROUP \
  --nsg-name $NSG_NAME \
  --name "HTTP_RULE" \
  --protocol Tcp \
  --priority 1010 \
  --destination-port-range 80 \
  --access Allow

az network nsg rule create \
  --resource-group $RESOURCE_GROUP \
  --nsg-name $NSG_NAME \
  --name "HTTPS_RULE" \
  --protocol Tcp \
  --priority 1020 \
  --destination-port-range 443 \
  --access Allow

# Create a NIC for our VM
NIC_NAME="reckon-nic"
az network nic create \
  --resource-group $RESOURCE_GROUP \
  --name $NIC_NAME \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME \
  --network-security-group $NSG_NAME \
  --public-ip-address $PUBLIC_IP_NAME

# Create the virtual machine
az vm create \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --name $VM_NAME \
  --nics $NIC_NAME \
  --image $IMAGE \
  --size $VM_SIZE \
  --admin-username $ADMIN_USERNAME \
  --ssh-key-value @$SSH_KEY_PATH \
  --os-disk-size-gb 30 \
  --tags "env=production" \
  --verbose

echo "Script completed successfully!"
