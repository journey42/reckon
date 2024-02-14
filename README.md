# Getting Started
Local Setup

Initialize the database first:

```
reflex db init
reflex db migrate
```

Azure Setup

./scripts/azure-create-vm.sh

./scripts/parameters.json
./scripts/template.json

az ssh vm --resource-group reckon-rg --vm-name reckon --subscription ba96b303-2d6d-4450-82a1-50de5bb7b50e

type -p curl >/dev/null || (sudo apt update && sudo apt install curl -y)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
&& sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
&& sudo apt update \
&& sudo apt install gh -y

gh auth login

gh repo clone journey42/reckon

sudo apt install docker.io
sudo apt install docker-compose

sudo DOMAIN=reckon.eastus.cloudapp.azure.com docker-compose build

cp ~/reckon/scripts/reckon.service /etc/systemd/system/reckon.service

sudo systemctl daemon-reload

sudo systemctl enable reckon

sudo systemctl start reckon

sudo systemctl status reckon