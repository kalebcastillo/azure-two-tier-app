This project was built as part of the Cloud Engineering courseware, Learn to Cloud. Visit here to learn more: https://learntocloud.guide/

This README does detail my process of building this project, but is not intended as a step by step guide and does not include every action taken.

# Intro

In this project, we've deployed an existing journal API + Database to Azure using a two-tier architecture. The primary goal of this exercise was to understand cloud architecture patterns, especially regarding networking and network security. We also delve into some Linux Systems Administration.

# Goals for this project

Let's first define our end goals for the environment. In addition to your application of course functioning as expected, we want to accomplish the following:

• The API should only accept HTTP/HTTPS traffic from the internet  
• The Database should only accept connections directly from the API server  
• SSH to the VMs should be restricted to only your own IP address. Optionally, configure a cloud native solution (Azure Bastion)  
• Regular database backups to Azure blob storage  
• API and Database automatically start upon server boots/restarts  

# Networking

First, we create a VNet with the address space of 192.168.1.0 /24. We don't need extensive space for this VNet as it's use will be limited to this project.

<img width="818" height="108" alt="image" src="https://github.com/user-attachments/assets/e83080fc-de2f-4a9f-a757-30115b5f19dd" />

# Subnets

Next, we'll define our subnets. We want to separate the app and database into different subnets. We'll need to apply different traffic rules to each tier of our application in order to follow the "principle of least priveledge"  
Optionally, include an Azure Bastion subnet. A subnet titled specifically "AzureBastion" with a minium CIDR block of /26 is required if you intend to deploy a Bastion to this project.

<img width="750" height="152" alt="image" src="https://github.com/user-attachments/assets/a930f50b-0a62-46cb-b0d8-13f07271dbeb" />

# Network Security Groups

## Database

Here's our configuration for the database subnet, apart from Azure NSG defaults. We allow inbound from the API subnet with a destination of port 5432 so that our API can communicate with our database. We also allow SSH from the API subnet. This is because our database VM, as you'll see later, cannot be accessed from the internet at all. So when we SSH into the database VM, we're actually passing through the API VM.

<img width="1480" height="132" alt="image" src="https://github.com/user-attachments/assets/31d93bf5-fcf4-423a-bac8-35d64921a9af" />

## API

The API subnet's NSG, apart from defaults. We allow inbound SSH specifically from our own public IP address. We allow HTTP from the internet for access to the API, as well as allowing the Azure Load Balancer, to forward the traffic.

<img width="1474" height="156" alt="image" src="https://github.com/user-attachments/assets/c99c0d4b-1c1f-4085-8deb-c71c745d9f17" />

# NAT Gateway

A NAT Gateway with an outbound IP address attached to both subnets handles egress for our VMs.

# Public Load Balancer

Since we don't want out API VM to have a public IP we use a Public Load Balancer to handle inbound traffic. As part of the config, we map the front end port 80 to the back end port 80.

<img width="750" height="446" alt="image" src="https://github.com/user-attachments/assets/5441a588-f587-4abb-b8c2-95711d77cefe" />

# SSH

When creating your two VMs, make sure to choose the SSH key authentication method. Upon deployment, you'll receive an option to download the a new key pair.  
Copy the files into your .ssh folder on your local machine. For me, on Windows, that was "C:\Users\<username>\.ssh"

<img width="320" height="208" alt="image" src="https://github.com/user-attachments/assets/1fe3ef70-a412-4d70-82b9-5792f0d0304c" />

Then make sure you have the VS Code extension "Remote- - SSH"

If you've set up the networking correctly, you'll be able to SSH in from VSCode now

# API VM

Create your VM and upload your app into the /opt directory. At this stage, make sure to fulfill certain prerequisities, such as installing venv tooling, creating a venv, setting your environment variables installing your requirements.txt, etc.

We want to create a systemd service to autostart our app upon VM boot.  
Create the service account:

```
sudo adduser --system --group --home /opt/journalapi journalapi
```

Ensure the service account owns the all of the application files

```
sudo mkdir -p /opt/journalapi/journal-starter
sudo chown -R journalapi:journalapi /opt/journalapi
```

Next weconfig the system unit, here's what mind ended up looking like:

Finally, enable it to start on boot

```
sudo systemctl daemon-reload
sudo systemctl enable --now journalapi
```

Because we don't want to open port 8000 to the Internet, we utilize an nginx reverse proxy, mapping port 80 to 127.0.0.1:8000  
First install nginx

```
sudo apt update && sudo apt install -y nginx
```

Our configuration for the reverse proxy lives here: /etc/nginx/sites-available/journalapi

with our file looking like this:

```
server {
    listen 80 default_server;               
    listen [::]:80 default_server;
    server_name _;                          
    
    location /health {
        proxy_pass http://127.0.0.1:8000/health;    # forward to app health
    }

    location / {
        proxy_set_header Host $host;                         # preserve Host header
        proxy_set_header X-Real-IP $remote_addr;             # client IP for logs
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; # proxy chain
        proxy_set_header X-Forwarded-Proto http;             # scheme
        proxy_pass http://127.0.0.1:8000;
    }
}
```

# DB VM

Now for our database VM. Install postgresql on your VM

Add this to our postgresql.conf file

```
listen_addresses = '*'
```

Add this to our pg_hba.conf file:

```
host    all     all     192.168.1.0/27     scram-sha-256
```

In a psql shell, create your DB role, database, and schema.

# Backups

We'll want to configure some type of backup solution for our database. I decided to backup my database to Azure blob storage, with a cronjob set up to run azcopy to it daily.

Create a data disk for your DB VM.

<img width="1048" height="206" alt="image" src="https://github.com/user-attachments/assets/6cc9e1c1-4a8b-4e4e-935d-32139f50f872" />

You'll need to attach it to the VM  
This guide can help: https://learn.microsoft.com/en-us/azure/virtual-machines/linux/attach-disk-portal

Then you can create a mount point from the current postgres data directory to the data disk  
Consult your AI chat of choice for instructions on this, as it is rather complicated. I'm still learning how to do this and relied on ChatGPT for assistance here.

Next we need to create the storage account and azure blob container

<img width="576" height="288" alt="image" src="https://github.com/user-attachments/assets/3f9bbcc8-6573-43b2-8e42-9478ea10c8b2" />

Then install azcopy: https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10?tabs=apt  
create a script that will create a pg dump and azcopy it to the blob storage

Mine looks like this:

```
#!/bin/bash

DATE=$(date +%F_%H-%M-%S)

FILE="/tmp/pgdump_$DATE.sql"

PGPASSWORD="$POSTGRES_PASSWORD"  

pg_dump -U $POSTGRES_USER $POSTGRES_DB > $FILE

# Replace <storageacct> and <SAS_TOKEN> with your actual values
azcopy copy "$FILE" "https://<storageacct>.blob.core.windows.net/pgdumps?<sas_token>"
rm "$FILE"
```

Make it executable

```
chmod +x <path to script>
```

schedule daily cron job to run the script  
Open the postgres users crontab

```
sudo -u postgres crontab -e
```

Then add this entry

```
0 5 * * * /var/lib/postgresql/scripts/pg_backup.sh
```

Run the script manually like so:

```
sudo -u postgres /var/lib/postgresql/scripts/pg_backup.sh
```

Then check that a backup was created on your Azure storage blob

<img width="1000" height="276" alt="image" src="https://github.com/user-attachments/assets/f763b11d-edf2-41ce-bf55-6ab139aec94f" />

# How to verify it works

From the API VM:

```
curl -i http://127.0.0.1/health
```

From your local PC's terminal to test internet accessibility

```
curl -i http://<LB_PUBLIC_IP>/
curl -i http://<LB_PUBLIC_IP>/health
```
<img width="450" height="116" alt="image" src="https://github.com/user-attachments/assets/7362cb47-e699-4ad1-9dc4-b1216a22055a" />

From your local browser, navigate to the docs page:

```
http://<frontend IP of load balancer>/docs
```

Create some sample entries.

Then explore your database in a psql client from your database VM terminal  
Run some queries. For example:

```
SELECT * FROM public.entries
```

You should see your entries populate

<img width="1396" height="146" alt="image" src="https://github.com/user-attachments/assets/bb79cb53-efb0-4794-9b8b-428d60b681ca" />

# How to improve this project

You'll notice all the resources are created through the portal.  
All of this can certainly be done through Azure cli  

However, even better would be to define these resources via Terraform.  
I intend to do that in the near future, as well as implement other DevOps methodologies to this project

Also, the app currently using only HTTP. Upgrading this to HTTPS/443 using Let's Encrypt would bring this project to a more production grade state.
