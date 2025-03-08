# QasaB/غصاب
A Telegram bot that allows users to split PDF files by selecting specific page ranges. The bot can handle PDFs uploaded directly, downloaded from URLs, or selected from previously processed files.

## Features
- Upload PDFs (up to 50MB due to Telegram limitations)
- Provide a URL to download larger PDFs (up to 2GB)
- Select from previously processed PDFs
- Extract specific page ranges
- Handle large documents efficiently

## Requirements
- Python 3.8 or higher
- Required packages in `requirements.txt`

## Setup

### Local Installation
1. Clone the repository:
   ```
   git clone https://github.com/yourusername/pdf-splitter-bot.git
   cd qasab
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set your Telegram bot token:
   ```
   export TELEGRAM_BOT_TOKEN="your_token_here"
   ```

4. Run the bot:
   ```
   python app.py
   ```

### Docker Installation

1. Build the Docker image:
   ```
   docker build -t pdf-splitter-bot .
   ```

2. Run the container:
   ```
   docker run -d --name qasab \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -v $(pwd)/stored_pdfs:/app/stored_pdfs \
     pdf-splitter-bot
   ```

Alternatively, use Docker Compose:
```
docker-compose up -d
```

## Usage

1. Start a chat with the bot using `/start`
2. Choose to upload a PDF, provide a URL, or select from stored PDFs
3. Specify the page range to extract (e.g., "1-5")
4. Receive the extracted PDF

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
   git clone https://github.com/yourusername/pdf-splitter-bot.git
   cd pdf-splitter-bot
   ```
3. Install Docker if not already installed:
   ```
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```
4. Configure and start the bot:
   ```
   # Build the Docker image
   docker build -t pdf-splitter-bot .
   
   # Run the container
   docker run -d --name pdf-splitter-bot \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -v $(pwd)/stored_pdfs:/app/stored_pdfs \
     --restart unless-stopped \
     pdf-splitter-bot
   ```

### Maintaining the Bot

1. Monitoring logs:
   ```
   docker logs -f pdf-splitter-bot
   ```

2. Restarting the bot:
   ```
   docker restart pdf-splitter-bot
   ```

3. Updating the bot:
   ```
   # Pull latest code
   git pull
   
   # Stop and remove old container
   docker stop pdf-splitter-bot
   docker rm pdf-splitter-bot
   
   # Rebuild and run
   docker build -t pdf-splitter-bot .
   docker run -d --name pdf-splitter-bot \
     -e TELEGRAM_BOT_TOKEN="your_token_here" \
     -v $(pwd)/stored_pdfs:/app/stored_pdfs \
     --restart unless-stopped \
     pdf-splitter-bot
   ```

## Notes on Large Files

- The bot can process PDFs up to 2GB when downloaded from a URL
- For very large PDFs, processing might take several minutes
- Extracted PDFs must be under 50MB to be sent back via Telegram
- Consider extracting fewer pages at once for very large source PDFs

## Troubleshooting

- **Bot not responding**: Check the logs using `docker logs pdf-splitter-bot`
- **File size errors**: Remember Telegram's 50MB limit for bot file transfers
- **Timeout errors**: Try extracting fewer pages at once
- **PDF processing errors**: Ensure the PDF is not corrupted or password-protected

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Python and python-telegram-bot library
- Uses PyPDF2 for PDF manipulation
