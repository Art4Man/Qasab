import os
import logging
import tempfile
import requests
import time
import glob
from urllib.parse import urlparse
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters, CallbackQueryHandler
from PyPDF2 import PdfReader, PdfWriter

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
UPLOAD_PDF, GET_URL, CONFIRM_DOWNLOAD, GET_PAGE_RANGE, SELECT_LOCAL_PDF = range(5)

# Maximum file size (in bytes) - 50MB is the Telegram limit for bots
MAX_FILE_SIZE = 50 * 1024 * 1024
# Maximum file size to download from URL (in bytes) - 2GB
MAX_DOWNLOAD_SIZE = 2 * 1024 * 1024 * 1024

# Directory to store PDFs for later use
PDF_STORAGE_DIR = "stored_pdfs"
os.makedirs(PDF_STORAGE_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send welcome message when the command /start is issued."""
    keyboard = [
        [InlineKeyboardButton("Upload PDF", callback_data="upload")],
        [InlineKeyboardButton("Provide URL", callback_data="url")],
        [InlineKeyboardButton("Select from stored PDFs", callback_data="local")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Handle both direct /start command and callback_query
    if update.message:
        await update.message.reply_text(
            "Welcome to the PDF Splitter Bot! 📄✂️\n\n"
            "How would you like to provide your PDF?",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.edit_text(
            "Welcome to the PDF Splitter Bot! 📄✂️\n\n"
            "How would you like to provide your PDF?",
            reply_markup=reply_markup
        )
    return UPLOAD_PDF

async def list_local_pdfs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """List the PDFs stored in the server directory."""
    query = None
    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
    
    # Get list of PDF files
    pdf_files = glob.glob(f"{PDF_STORAGE_DIR}/*.pdf")
    
    if not pdf_files:
        # No PDFs found
        keyboard = [
            [InlineKeyboardButton("Upload PDF", callback_data="upload")],
            [InlineKeyboardButton("Provide URL", callback_data="url")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = "No PDF files are currently stored on the server.\n\nPlease choose another option:"
        
        if query:
            await query.message.edit_text(message, reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text(message, reply_markup=reply_markup)
        return UPLOAD_PDF
    
    # Create buttons for each PDF file
    keyboard = []
    for pdf_path in pdf_files[:10]:  # Limit to 10 files to avoid large keyboards
        file_name = os.path.basename(pdf_path)
        file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        keyboard.append([InlineKeyboardButton(
            f"{file_name} ({file_size_mb:.1f}MB)", 
            callback_data=f"select_pdf:{file_name}"
        )])
    
    # Add a back button
    keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = "Select a PDF file to split:"
    
    if query:
        await query.message.edit_text(message, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(message, reply_markup=reply_markup)
    
    return SELECT_LOCAL_PDF

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button presses."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "upload":
        await query.message.edit_text(
            "Please upload your PDF file.\n\n"
            f"Note: Due to Telegram limitations, I can only process files up to 50MB."
        )
        return UPLOAD_PDF
    elif query.data == "url":
        await query.message.edit_text(
            "Please send me a direct download link to your PDF file.\n\n"
            f"Note: I can download files up to 2GB. The link must be a direct download link to a PDF file."
        )
        return GET_URL
    elif query.data == "local":
        return await list_local_pdfs(update, context)
    elif query.data == "back_to_start":
        # Fix: Use update directly instead of extracting message
        return await start(update, context)
    elif query.data.startswith("select_pdf:"):
        # Extract the filename
        file_name = query.data.split(":", 1)[1]
        file_path = os.path.join(PDF_STORAGE_DIR, file_name)
        
        if not os.path.exists(file_path):
            await query.message.edit_text(
                "Sorry, the selected file no longer exists. Please try another option.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back to stored PDFs", callback_data="local")],
                    [InlineKeyboardButton("Back to start", callback_data="back_to_start")]
                ])
            )
            return UPLOAD_PDF
        
        # Store the file path
        context.user_data["pdf_path"] = file_path
        
        # Analyze the PDF
        status_message = await query.message.edit_text("Analyzing the selected PDF...")
        
        try:
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                num_pages = len(reader.pages)
                context.user_data["num_pages"] = num_pages
            
            await status_message.edit_text(
                f"Selected PDF: {file_name}\n"
                f"Number of pages: {num_pages}\n\n"
                "Please specify which pages you want to extract in the format: start-end\n"
                "For example: 1-5 (to extract pages 1 through 5)"
            )
            return GET_PAGE_RANGE
            
        except Exception as e:
            logger.error(f"Error analyzing PDF: {e}")
            await status_message.edit_text(
                "Sorry, there was an error processing this PDF. Please try another file."
            )
            return await list_local_pdfs(update, context)
    elif query.data == "confirm_download":
        # Get the download URL from user data
        url = context.user_data.get("download_url")
        if not url:
            await query.message.edit_text("Sorry, there was an issue. Please try again.")
            return ConversationHandler.END
        
        # Initialize download message
        status_message = await query.message.edit_text(f"Starting download... This might take a while for large files.")
        
        try:
            # Get filename for storing the PDF
            filename = context.user_data.get("file_name", "downloaded.pdf")
            safe_filename = os.path.basename(filename)  # Ensure we only use the filename, not a path
            pdf_path = os.path.join(PDF_STORAGE_DIR, safe_filename)
            
            # Download the file with progress updates
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            downloaded = 0
            last_update_time = 0
            start_time = time.time()
            
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress message every ~5% or at least every 10 seconds for large files
                        current_time = time.time()
                        if (total_size > 0 and 
                            ((downloaded / total_size) - (last_update_time / total_size) > 0.05 or 
                             current_time - start_time - last_update_time > 10)):
                            
                            last_update_time = downloaded
                            progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                            
                            try:
                                await status_message.edit_text(
                                    f"Downloading: {progress:.1f}% complete\n"
                                    f"({downloaded/(1024*1024):.1f}MB of {total_size/(1024*1024):.1f}MB)"
                                )
                            except Exception as e:
                                logger.warning(f"Could not update progress message: {e}")
            
            # After download completes, analyze the PDF
            await status_message.edit_text("Download complete. Analyzing PDF...")
            
            with open(pdf_path, 'rb') as file:
                reader = PdfReader(file)
                num_pages = len(reader.pages)
                context.user_data["num_pages"] = num_pages
                context.user_data["pdf_path"] = pdf_path
            
            await status_message.edit_text(
                f"PDF downloaded and processed successfully! It has {num_pages} pages.\n\n"
                "Please specify which pages you want to extract in the format: start-end\n"
                "For example: 1-5 (to extract pages 1 through 5)"
            )
            return GET_PAGE_RANGE
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            await status_message.edit_text(
                "Sorry, there was an error downloading or processing the file.\n\n"
                f"Error: {str(e)[:100]}...\n\n"
                "Please check your link and try again."
            )
            return ConversationHandler.END
    elif query.data == "cancel_download":
        await query.message.edit_text("Operation cancelled. Send /start to begin again.")
        return ConversationHandler.END
    
    return UPLOAD_PDF

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the uploaded PDF file."""
    user = update.message.from_user
    document = update.message.document
    
    # Check file size
    if document.file_size > MAX_FILE_SIZE:
        keyboard = [
            [InlineKeyboardButton("Provide URL Instead", callback_data="url")],
            [InlineKeyboardButton("Try Another File", callback_data="upload")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ This file is too large (over 50MB). Telegram bots can only process files up to 50MB.\n\n"
            "You can provide a direct download link instead, or try a smaller file.",
            reply_markup=reply_markup
        )
        return UPLOAD_PDF
    
    # Notify the user that processing is starting
    status_message = await update.message.reply_text("Downloading your PDF... Please wait.")
    
    try:
        # Download the file with a timeout
        pdf_file = await update.message.document.get_file()
        
        # Get the original filename
        file_name = document.file_name if document.file_name else f"telegram_{user.id}.pdf"
        safe_filename = os.path.basename(file_name)  # Ensure we only use the filename
        pdf_path = os.path.join(PDF_STORAGE_DIR, safe_filename)
        
        # Download to the storage directory
        await pdf_file.download_to_drive(pdf_path)
        
        # Update status message
        await status_message.edit_text("PDF downloaded. Analyzing file...")
        
        # Store path in context
        context.user_data["pdf_path"] = pdf_path
        
        # Get number of pages in the PDF
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            num_pages = len(reader.pages)
            context.user_data["num_pages"] = num_pages
        
        await status_message.edit_text(
            f"PDF received! It has {num_pages} pages.\n\n"
            "Please specify which pages you want to extract in the format: start-end\n"
            "For example: 1-5 (to extract pages 1 through 5)"
        )
        return GET_PAGE_RANGE
        
    except Exception as e:
        logger.error(f"Error handling PDF: {e}")
        await status_message.edit_text(
            "Sorry, there was an error processing your PDF. Please try again with a smaller file."
        )
        # Clean up if file was created
        if 'pdf_path' in locals() and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except:
                pass
        return UPLOAD_PDF

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the URL provided by the user."""
    url = update.message.text.strip()
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "Please provide a valid URL starting with http:// or https://"
        )
        return GET_URL
    
    # Check if URL seems to point to a PDF
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    
    # Store the URL in context
    context.user_data["download_url"] = url
    
    # Try to get headers to check file size and type
    status_message = await update.message.reply_text("Checking the URL... Please wait.")
    
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        
        # Check if response is successful
        if response.status_code != 200:
            await status_message.edit_text(
                f"⚠️ Error accessing the URL. Server returned status code: {response.status_code}\n"
                "Please check the URL and try again."
            )
            return GET_URL
        
        # Check content type if available
        content_type = response.headers.get('Content-Type', '').lower()
        if content_type and 'pdf' not in content_type and not path.endswith('.pdf'):
            await status_message.edit_text(
                "⚠️ This URL doesn't seem to point to a PDF file.\n"
                "Please provide a direct download link to a PDF file."
            )
            return GET_URL
        
        # Check file size if available
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_DOWNLOAD_SIZE:
            await status_message.edit_text(
                f"⚠️ The file is too large ({int(content_length) // (1024 * 1024)}MB).\n"
                f"I can only download files up to {MAX_DOWNLOAD_SIZE // (1024 * 1024)}MB."
            )
            return GET_URL
            
        # If we can't determine file size, warn the user
        if not content_length:
            file_size_info = "Unknown size"
        else:
            file_size_info = f"{int(content_length) // (1024 * 1024)}MB"
        
        # Extract filename from URL or Content-Disposition header
        filename = get_filename_from_url(url, response.headers.get('Content-Disposition'))
        context.user_data["file_name"] = filename
        
        # Confirm with the user
        keyboard = [
            [InlineKeyboardButton("Yes, download it", callback_data="confirm_download")],
            [InlineKeyboardButton("No, cancel", callback_data="cancel_download")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await status_message.edit_text(
            f"I found a file at this URL:\n\n"
            f"📄 Name: {filename}\n"
            f"📊 Size: {file_size_info}\n\n"
            f"Would you like me to download and process this file?",
            reply_markup=reply_markup
        )
        return CONFIRM_DOWNLOAD
        
    except requests.RequestException as e:
        logger.error(f"Error checking URL: {e}")
        await status_message.edit_text(
            "⚠️ Error accessing the URL. Please check if the link is correct and try again."
        )
        return GET_URL

def get_filename_from_url(url: str, content_disposition: str = None) -> str:
    """Extract filename from URL or Content-Disposition header."""
    # Try to get filename from Content-Disposition header
    if content_disposition:
        import re
        filename_match = re.search(r'filename="?([^"]*)"?', content_disposition)
        if filename_match:
            return filename_match.group(1)
    
    # Get filename from URL
    parsed_url = urlparse(url)
    path = parsed_url.path
    filename = os.path.basename(path)
    
    # Use a default name if we couldn't extract one
    if not filename or filename == '':
        return "document.pdf"
    
    # Ensure filename ends with .pdf
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    
    return filename

async def process_page_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the specified page range and create a new PDF."""
    user = update.message.from_user
    page_range_text = update.message.text
    
    # Notify user that processing has started
    status_message = await update.message.reply_text("Validating your request...")
    
    # Parse page range
    try:
        start_page, end_page = map(int, page_range_text.split('-'))
    except ValueError:
        await status_message.edit_text(
            "Invalid format! Please use the format: start-end (e.g., 1-5)"
        )
        return GET_PAGE_RANGE
    
    # Validate page range
    num_pages = context.user_data.get("num_pages", 0)
    if start_page < 1 or end_page > num_pages or start_page > end_page:
        await status_message.edit_text(
            f"Invalid page range! The document has {num_pages} pages. "
            f"Please specify a valid range between 1 and {num_pages}."
        )
        return GET_PAGE_RANGE
    
    # Check if the range is too large (more than 100 pages)
    if end_page - start_page + 1 > 100:
        await status_message.edit_text(
            f"⚠️ You're trying to extract {end_page - start_page + 1} pages, which is quite large.\n\n"
            f"Processing many pages can take a long time and might cause timeouts.\n"
            f"Consider extracting fewer pages (maximum of 100 recommended).\n\n"
            f"Do you want to continue anyway? Reply with 'yes' to proceed or provide a new range."
        )
        # Store the current range for potential confirmation
        context.user_data["pending_range"] = (start_page, end_page)
        return GET_PAGE_RANGE
    
    # Check if this is a confirmation for a large range
    if page_range_text.lower() == 'yes' and 'pending_range' in context.user_data:
        start_page, end_page = context.user_data["pending_range"]
        del context.user_data["pending_range"]  # Clear the pending range
    
    # Create a new PDF with the specified pages
    await status_message.edit_text("Creating your new PDF... This may take a moment.")
    
    input_pdf_path = context.user_data["pdf_path"]
    
    try:
        # Create a temporary file for output
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_output:
            output_pdf_path = temp_output.name
        
        # Create the new PDF - use optimized approach for large ranges
        pdf_writer = PdfWriter()
        
        # For large PDFs, update progress periodically
        total_pages = end_page - start_page + 1
        progress_interval = max(1, total_pages // 10)  # Update at most 10 times
        
        with open(input_pdf_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            
            # Process pages in chunks for better performance with large PDFs
            for i, page_num in enumerate(range(start_page - 1, end_page)):
                try:
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                    
                    # Update progress periodically for large ranges
                    if i % progress_interval == 0 and i > 0:
                        progress = (i / total_pages) * 100
                        try:
                            await status_message.edit_text(
                                f"Processing pages: {progress:.1f}% complete ({i}/{total_pages} pages)"
                            )
                        except Exception as e:
                            logger.warning(f"Could not update progress: {e}")
                            
                except Exception as e:
                    logger.error(f"Error adding page {page_num+1}: {e}")
                    await status_message.edit_text(f"Error processing page {page_num+1}. Please try a different range.")
                    return GET_PAGE_RANGE
            
            # Save the new PDF
            await status_message.edit_text("Finalizing your PDF...")
            with open(output_pdf_path, 'wb') as output_file:
                pdf_writer.write(output_file)
        
        # Check if the output file is within Telegram size limits
        output_size = os.path.getsize(output_pdf_path)
        if output_size > MAX_FILE_SIZE:
            await status_message.edit_text(
                f"⚠️ The resulting PDF is too large to send ({output_size // (1024 * 1024)}MB, limit is 50MB). "
                "Please try extracting fewer pages."
            )
            os.remove(output_pdf_path)
            return GET_PAGE_RANGE
        
        # Get original filename for better output filename
        original_filename = os.path.basename(input_pdf_path)
        output_filename = f"{os.path.splitext(original_filename)[0]}_pages_{start_page}_to_{end_page}.pdf"
        
        # Send the new PDF back to the user with extended timeout
        await status_message.edit_text("Sending your new PDF...")
        
        # For large files, use a more explicit approach with longer timeout
        with open(output_pdf_path, 'rb') as doc_file:
            await update.message.reply_document(
                document=doc_file,
                filename=output_filename,
                caption=f"Here's your new PDF with pages {start_page} to {end_page}.",
                read_timeout=60,
                write_timeout=60,
                connect_timeout=60,
                pool_timeout=60
            )
        
        # Clean up temporary files (but keep the original in storage)
        try:
            os.remove(output_pdf_path)
        except Exception as e:
            logger.error(f"Error cleaning up output file: {e}")
        
        # Ask if the user wants to do something else
        keyboard = [
            [InlineKeyboardButton("Split another PDF", callback_data="back_to_start")],
            [InlineKeyboardButton("Use same PDF", callback_data=f"select_pdf:{os.path.basename(input_pdf_path)}")],
            [InlineKeyboardButton("Exit", callback_data="cancel_download")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "What would you like to do next?",
            reply_markup=reply_markup
        )
        return UPLOAD_PDF
        
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        await status_message.edit_text(
            f"Sorry, an error occurred while processing your PDF: {str(e)[:100]}...\n"
            "Please try again with a different file or page range."
        )
        # Clean up temporary files
        if 'output_pdf_path' in locals() and os.path.exists(output_pdf_path):
            try:
                os.remove(output_pdf_path)
            except:
                pass
        return UPLOAD_PDF

async def list_stored_pdfs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to list all stored PDFs."""
    # Get list of PDF files
    pdf_files = glob.glob(f"{PDF_STORAGE_DIR}/*.pdf")
    
    if not pdf_files:
        await update.message.reply_text("No PDF files are currently stored on the server.")
        return
    
    # Create a message with file info
    message = "Stored PDF files:\n\n"
    for i, pdf_path in enumerate(pdf_files, 1):
        file_name = os.path.basename(pdf_path)
        file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        message += f"{i}. {file_name} ({file_size_mb:.1f}MB)\n"
    
    await update.message.reply_text(message)

async def clear_stored_pdfs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to delete all stored PDFs."""
    if not context.args or context.args[0].lower() != "confirm":
        await update.message.reply_text(
            "⚠️ This will delete ALL stored PDF files.\n"
            "To confirm, use: /clear_pdfs confirm"
        )
        return
    
    # Get list of PDF files
    pdf_files = glob.glob(f"{PDF_STORAGE_DIR}/*.pdf")
    
    if not pdf_files:
        await update.message.reply_text("No PDF files to delete.")
        return
    
    # Delete all PDF files
    deleted_count = 0
    for pdf_file in pdf_files:
        try:
            os.remove(pdf_file)
            deleted_count += 1
        except Exception as e:
            logger.error(f"Error deleting {pdf_file}: {e}")
    
    await update.message.reply_text(f"Deleted {deleted_count} PDF files from storage.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operation cancelled. Send /start to begin again."
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and inform the user."""
    logger.error(f"Error: {context.error} caused by {update}")
    
    try:
        # Extract the relevant message object regardless of update type
        if update.callback_query:
            message_obj = update.callback_query.message
        elif update.message:
            message_obj = update.message
        else:
            # No way to respond
            return
            
        if "file is too big" in str(context.error).lower():
            await message_obj.reply_text(
                "⚠️ This file is too large (over 50MB). Telegram bots can only process files up to 50MB.\n\n"
                "You can try providing a direct download link instead. Send /start to begin again."
            )
        elif "timed out" in str(context.error).lower():
            await message_obj.reply_text(
                "⚠️ The operation timed out. This might happen with large files or complex PDFs.\n\n"
                "Please try again with a smaller PDF or fewer pages. Send /start to begin again."
            )
        else:
            await message_obj.reply_text(
                f"Sorry, an error occurred: {str(context.error)[:100]}...\n"
                "Please try again or send /start to restart."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

def main() -> None:
    """Run the bot."""
    # Get token from environment variable or replace with your token
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    # Create the Application with increased timeout
    application = Application.builder().token(token) \
        .read_timeout(600) \
        .write_timeout(600) \
        .connect_timeout(60) \
        .pool_timeout(600) \
        .build()
    
    # Set up conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            UPLOAD_PDF: [
                CallbackQueryHandler(button_handler),
                MessageHandler(filters.Document.PDF, handle_pdf)
            ],
            GET_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)
            ],
            CONFIRM_DOWNLOAD: [
                CallbackQueryHandler(button_handler)
            ],
            GET_PAGE_RANGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_page_range)
            ],
            SELECT_LOCAL_PDF: [
                CallbackQueryHandler(button_handler)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_chat=False
    )
    
    application.add_handler(conv_handler)
    
    # Add handlers for storage management commands
    application.add_handler(CommandHandler("list_pdfs", list_stored_pdfs))
    application.add_handler(CommandHandler("clear_pdfs", clear_stored_pdfs))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()
