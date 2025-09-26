This project was built as part of the Cloud Engineering courseware, Learn to Cloud. Visit here to learn more: https://learntocloud.guide/

This README details my process of building this project, but is not intended as a step by step guide and does not include every action taken.



# Architecture Diagram

In this project, we've deployed an existing journal API + Database to Azure using a two-tier architecture. The primary goal of this exercise was to understand cloud architecture patterns, especially regarding networking. We also delve into some Linux Systems Administration.

<img width="1872" height="1828" alt="KalebPhase3_DarkMode" src="https://github.com/user-attachments/assets/6b707e4a-8b9f-49c2-a6ce-fbe743f9b9be" />


# Goals for this project

Let's first define our end goals for the environment. In addition to your application of course functioning as expected, we want to accomplish the following:

- SSH to the VMs should be restricted to only your own IP address. Optionally, configure a cloud native solution (Azure Bastion)
- The API should only accept HTTP/HTTPS traffic from the internet  
- The Database should only accept connections directly from the API server  
- Regular database backups to Azure blob storage 
- API and Database automatically start upon server boots/restarts 

# Networking

First, we create a VNet with the address space of 192.168.1.0 /24. We don't need extensive space for this VNet as its use will be limited to this project.

<img width="818" height="108" alt="image" src="https://github.com/user-attachments/assets/e83080fc-de2f-4a9f-a757-30115b5f19dd" />


# Subnets

Next, we'll define our subnets. We want to separate the app and database into different subnets. We'll need to apply different traffic rules to each tier of our application in order to follow the "principle of least privilege".  
Optionally, include an Azure Bastion subnet. A subnet titled specifically "AzureBastion" with a minimum CIDR block of /26 is required if you intend to deploy a Bastion to this project.

<img width="750" height="152" alt="image" src="https://github.com/user-attachments/assets/a930f50b-0a62-46cb-b0d8-13f07271dbeb" />


# Network Security Groups

## Database

Here's our configuration for the database subnet. Apart from Azure NSG defaults, we allow inbound from the API subnet with a destination of port 5432 so that our API can communicate with our database.
<img width="1480" height="132" alt="image" src="https://github.com/user-attachments/assets/31d93bf5-fcf4-423a-bac8-35d64921a9af" />


## API

The API subnet's NSG. Apart from defaults, we allow inbound SSH specifically from our own public IP address. Inbound HTTP to the API VM is allowed from the Internet on port 80. We also allow the AzureLoadBalancer service tag for the LB health probe.
Because the API VM has no public IP, traffic only reaches it via the Load Balancer.

<img width="1474" height="156" alt="image" src="https://github.com/user-attachments/assets/9e1a3c7e-24b4-4b50-90a1-0e7804000938" />


# NAT Gateway

A NAT Gateway with an outbound IP address attached to both subnets handles egress for our VMs.

<img width="897" height="512" alt="image" src="https://github.com/user-attachments/assets/1323931d-356c-497b-b3e0-006e879203f9" />


# Public Load Balancer

Since we don't want our API VM to have a public IP we use a Public Load Balancer to handle inbound traffic. As part of the config, we map the front end port 80 to the back end port 80.
It also uses an HTTP health probe on /health mapped to port 80 to help determine availability.
I’m using a Public Load Balancer here for simplicity. In a production setup you’ll want to front the app with Application Gateway or Azure Front Door.

<img width="750" height="446" alt="image" src="https://github.com/user-attachments/assets/5441a588-f587-4abb-b8c2-95711d77cefe" />


# SSH

When creating your two VMs, make sure to choose the SSH key authentication method. Upon deployment, you'll receive an option to download a new key pair.  
Copy the files into your .ssh folder on your local machine. For me, on Windows, that was "C:\Users\<username>\.ssh".

<img width="320" height="208" alt="image" src="https://github.com/user-attachments/assets/1fe3ef70-a412-4d70-82b9-5792f0d0304c" />

Then, edit your C:\Users\<username>\.ssh\config file to allow for the connection. In my setup, we wanted to ensure the database VM has no public IP attached at all. So we use ProxyJump from the API VM to facilitate SSH over to the database VM.
Make sure your Load Balancer includes an inbound NAT rule to target the API VM's port 22.

```ssh
# API VM access through LB Public IP
Host JournalAPI
  HostName <LB Public IP>
  User <username>        
  IdentityFile ~/.ssh/JournalAPI_key.pem
  IdentitiesOnly yes
  Port 22
  ServerAliveInterval 60

# DB VM accessible only through API VM
Host JournalDB
  HostName <JournalDB private IP>     
  User <username>
  IdentityFile ~/.ssh/JournalDB_key.pem
  IdentitiesOnly yes
  Port 22
  ProxyJump JournalAPI    #ProxyJump to handle SSH to this VM
  ServerAliveInterval 60
```

Then make sure you have the VS Code extension "Remote- - SSH".

If you've set up the networking correctly, you'll now be able to SSH in from VSCode using the extension.

# API VM

Create your VM and upload your app into the /opt directory. 
At this stage, make sure to fulfill certain prerequisites, such as installing venv tooling, creating a venv, setting your environment variables, installing your requirements.txt, etc.
Make sure to configure the DATABASE_URL environment variable. As the API and DB VM live in the same VNet, traffic stays internal. Nothing external can hit the database. The app will connect to the database via this URL.

We want to create a systemd service to autostart our app upon VM boot.  
Create the service account:

```bash
sudo adduser --system --group --home /opt/journalapi journalapi
```

Ensure the service account owns the all of the application files.

```bash
sudo mkdir -p /opt/journalapi/journal-starter
sudo chown -R journalapi:journalapi /opt/journalapi
```

Next we configure the system unit, here's what mine ended up looking like:
```
[Unit]
Description=Journal API (Uvicorn)
Wants=network-online.target                 
After=network-online.target

[Service]
Environment=PYTHONPATH=/opt/journalapi/journal-starter:/opt/journalapi/journal-starter/api

User=journalapi
Group=journalapi
WorkingDirectory=/opt/journalapi/journal-starter
EnvironmentFile=/opt/journalapi/.env

ExecStart=/opt/journalapi/venv/bin/uvicorn \
  --app-dir /opt/journalapi/journal-starter \
  api.main:app \
  --host 127.0.0.1 \
  --port 8000

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Finally, enable it.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now journalapi
```

Because we don't want to open port 8000 to the Internet, we utilize an Nginx reverse proxy, mapping port 80 to 127.0.0.1:8000  
First install Nginx.

```bash
sudo apt update && sudo apt install -y nginx
```

Our configuration for the reverse proxy lives here: /etc/nginx/sites-available/journalapi

My file looks like this:

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

You'll then need to enable the site. Use this command to create a symlink to enable your site.

```bash
sudo ln -s /etc/nginx/sites-available/<appfolder> /etc/nginx/sites-enabled/<appfolder>
sudo systemctl reload nginx

```

# DB VM

Now for our database VM. Install postgresql on your VM.

Add this to our postgresql.conf file

```
listen_addresses = '*'

```

Add this to our pg_hba.conf file:

```
host    all     all     192.168.1.0/27     scram-sha-256

```

In a psql shell, create your DB role, database, and schema.

```sql

CREATE ROLE <user_here> WITH LOGIN PASSWORD <passwordhere> NOSUPERUSER

CREATE DATABASE career_journal OWNER <user_here>;

\c career_journal

CREATE TABLE IF NOT EXISTS entries (
    id VARCHAR PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

```

# Backups

We'll want to configure some type of backup solution for our database. I decided to backup my database to Azure blob storage, with a cronjob set up to run azcopy to it daily.

Create a data disk for your DB VM.

<img width="1048" height="206" alt="image" src="https://github.com/user-attachments/assets/6cc9e1c1-4a8b-4e4e-935d-32139f50f872" />


You'll need to attach it to the VM. This guide can help:
https://learn.microsoft.com/en-us/azure/virtual-machines/linux/attach-disk-portal

Then you can create a mount point from the current postgres data directory to the data disk.  
Consult your AI chat of choice for instructions on this, as it is somewhat complicated. I'm still learning how to do this and relied on ChatGPT for assistance here.

Next we need to create the storage account and azure blob container.

<img width="576" height="288" alt="image" src="https://github.com/user-attachments/assets/3f9bbcc8-6573-43b2-8e42-9478ea10c8b2" />


Then install azcopy: https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10?tabs=apt  
Create a script that will create a pg dump and azcopy it to the blob storage.

Mine looks like this:

```
#!/bin/bash

DATE=$(date +%F_%H-%M-%S)

FILE="/tmp/pgdump_$DATE.sql"

PGPASSWORD="$POSTGRES_PASSWORD"  

pg_dump -U $POSTGRES_USER $POSTGRES_DB > $FILE

# Replace <storageacct> and <SAS_TOKEN> with your actual values
azcopy copy "$FILE" "https://<storageacct>.blob.core.windows.net/pgdumps?<sas_token>"

#Delete the local file afterwards to save space
rm "$FILE"

```

Make it executable:

```bash
chmod +x <path to script>

```

Schedule a daily cron job to run the script:  

Open the postgres users crontab

```bash
sudo -u postgres crontab -e

```

Then add this entry

```bash
0 5 * * * /var/lib/postgresql/scripts/pg_backup.sh

```

Run the script manually like so:

```bash
sudo -u postgres /var/lib/postgresql/scripts/pg_backup.sh

```

Then check that a backup was created on your Azure storage blob

<img width="1000" height="276" alt="image" src="https://github.com/user-attachments/assets/f763b11d-edf2-41ce-bf55-6ab139aec94f" />

One quick note: In a real, much larger database, you'll want to compress the dumps for faster transfer times and to keep storage costs down. Research "gzip" for this.

# How to verify everything works

From the API VM:

```
curl -i http://127.0.0.1/health
```

From your local PC's terminal to test internet accessibility:

```
curl -i http://<LB_PUBLIC_IP>/
curl -i http://<LB_PUBLIC_IP>/health
```
<img width="450" height="116" alt="image" src="https://github.com/user-attachments/assets/7362cb47-e699-4ad1-9dc4-b1216a22055a" />


From your local browser, navigate to the docs page:

```
http://<frontend IP of load balancer>/docs
```

Create some sample entries from this page.
Then, explore your database in a psql client from your database VM terminal.  
Run a query. For example:

```sql
SELECT * FROM public.entries

```

You should see your entries populate:

<img width="1459" height="140" alt="image" src="https://github.com/user-attachments/assets/a3165aab-f6e1-4bc9-bcde-a48c2d90bdc1" />


# How to improve this project

The app currently uses only HTTP. Upgrading this to HTTPS/443 using Let's Encrypt would bring this project to a production grade state.

You'll notice all the resources are created through the portal.  
All of this can certainly be done through Azure CLI 

However, even better would be to define these resources via Terraform.  
I intend to do that in the near future, as well as implement other DevOps methodologies to this project.

If you notice any other ways this project can be improved, please let me know! I'm actively working on learning more regarding best practices.
