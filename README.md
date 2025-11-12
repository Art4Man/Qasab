# QasaB/قصاب
A Telegram bot that allows users to split PDF files by selecting specific page ranges. The bot can handle PDFs uploaded directly, downloaded from URLs, or selected from previously processed files.

## Features
- Upload PDFs (up to 50MB due to Telegram limitations)
- Provide a URL to download larger PDFs (up to 2GB)
- Select from previously processed PDFs
- Extract specific page ranges
- Handle large documents efficiently
- Download links for extracted PDFs larger than 50MB

## Requirements
- Python 3.8 or higher
- Required packages in `requirements.txt`

## Setup

### Local Installation
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/qasab.git
   cd qasab
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set your Telegram bot token and public URL:
   ```
   export TELEGRAM_BOT_TOKEN="your_token_here"
   export PUBLIC_URL="http://your-domain-or-ip:8000"
   ```

4. Create required directories:
   ```
   mkdir -p stored_pdfs web_serve
   ```

5. Run the bot:
   ```
   python app.py
   ```

### Docker Installation

#### Using Pre-built Image from DockerHub

1. Pull and run the container directly:
   ```
   docker run -d --name qasab \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -e PUBLIC_URL="http://your-domain-or-ip:8000" \
     -v $(pwd)/stored_pdfs:/app/stored_pdfs \
     -v $(pwd)/web_serve:/app/web_serve \
     -p 8000:8000 \
     your-dockerhub-username/qasab:latest
   ```

#### Building from Source

1. Build the Docker image:
   ```
   docker build -t qasab .
   ```

2. Run the container:
   ```
   docker run -d --name qasab \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -e PUBLIC_URL="http://your-domain-or-ip:8000" \
     -v $(pwd)/stored_pdfs:/app/stored_pdfs \
     -v $(pwd)/web_serve:/app/web_serve \
     -p 8000:8000 \
     qasab
   ```

Alternatively, use Docker Compose:
```
docker-compose up -d
```

## Usage

1. Start a chat with the bot using `/start`
2. Choose to upload a PDF, provide a URL, or select from stored PDFs
3. Specify the page range to extract (e.g., "1-5" or just "7" for a single page)
4. Receive the extracted PDF:
   - If the resulting PDF is under 50MB, you'll receive it directly in Telegram
   - If the resulting PDF is over 50MB, you'll receive a download link that's valid for 24 hours

## Commands

- `/start` - Begin using the bot
- `/list_pdfs` - List stored PDFs
- `/clear_pdfs confirm` - Delete all stored PDFs
- `/cancel` - Cancel the current operation

## Deployment

### Deploying to a VPS or Dedicated Server

1. SSH into your server
2. Clone the repository:
   ```
   git clone https://github.com/yourusername/qasab.git
   cd qasab
   ```
3. Install Docker if not already installed:
   ```
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```
4. Configure and start the bot:
   ```
   # Build the Docker image
   docker build -t qasab .
   
   # Run the container
   docker run -d --name qasab \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -e PUBLIC_URL="http://your-domain-or-ip:8000" \
     -v $(pwd)/stored_pdfs:/app/stored_pdfs \
     -v $(pwd)/web_serve:/app/web_serve \
     -p 8000:8000 \
     --restart unless-stopped \
     qasab
   ```

5. Configure your server's firewall to allow traffic on port 8000:
   ```
   # For UFW (Ubuntu)
   sudo ufw allow 8000/tcp
   
   # For iptables
   sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
   ```

### Setting Up Domain and SSL (Recommended)

For improved security, it's recommended to set up a domain with SSL:

1. Register a domain and point it to your server's IP address

2. Install Certbot and Nginx:
   ```
   sudo apt update
   sudo apt install nginx certbot python3-certbot-nginx
   ```

3. Configure Nginx as a reverse proxy:
   ```
   sudo nano /etc/nginx/sites-available/qasab
   ```

4. Add the following configuration:
   ```
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

5. Enable the site and get an SSL certificate:
   ```
   sudo ln -s /etc/nginx/sites-available/qasab /etc/nginx/sites-enabled/
   sudo certbot --nginx -d your-domain.com
   sudo systemctl restart nginx
   ```

6. Update your PUBLIC_URL environment variable:
   ```
   export PUBLIC_URL="https://your-domain.com"
   ```

7. Restart your Docker container:
   ```
   docker restart qasab
   ```

### Maintaining the Bot

1. Monitoring logs:
   ```
   docker logs -f qasab
   ```

2. Restarting the bot:
   ```
   docker restart qasab
   ```

3. Updating the bot:
   ```
   # Pull latest code
   git pull
   
   # Stop and remove old container
   docker stop qasab
   docker rm qasab
   
   # Rebuild and run
   docker build -t qasab .
   docker run -d --name qasab \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -e PUBLIC_URL="http://your-domain-or-ip:8000" \
     -v $(pwd)/stored_pdfs:/app/stored_pdfs \
     -v $(pwd)/web_serve:/app/web_serve \
     -p 8000:8000 \
     --restart unless-stopped \
     qasab
   ```

## Notes on Large Files

- The bot can process PDFs up to 2GB when downloaded from a URL
- For very large PDFs, processing might take several minutes
- Extracted PDFs larger than 50MB will be served through a web link instead of directly through Telegram
- Download links are valid for 24 hours before they expire

## Troubleshooting

- **Bot not responding**: Check the logs using `docker logs qasab`
- **File size errors**: Remember Telegram's 50MB limit for bot file transfers. Larger files will be served via download link.
- **Timeout errors**: Try extracting fewer pages at once
- **PDF processing errors**: Ensure the PDF is not corrupted or password-protected
- **Download link not working**: Ensure your PUBLIC_URL is correctly set and accessible from the internet
- **Port 8000 not accessible**: Check your firewall settings and router port forwarding (if applicable)

## Acknowledgments

- Built with Python and python-telegram-bot library
- Uses PyPDF2 for PDF manipulation
- Uses Flask for serving large files