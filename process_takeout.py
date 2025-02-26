import os
import json
import argparse
import mailbox
import email.utils
from tqdm import tqdm
from bs4 import BeautifulSoup
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

def get_arg_or_env(arg_name, env_name, required=False):
    """Helper function to get argument from command line or from environment variable."""
    # Check for command-line argument first
    if args.__dict__.get(arg_name):
        return getattr(args, arg_name)
    
    # If not found in command line, check environment variables
    env_value = os.getenv(env_name)
    if env_value:
        return env_value
    
    # If neither command line nor environment variable is found and required, show error
    if required:
        parser.print_help()
        raise ValueError(f"Error: '{arg_name}' is required, but not provided.")
    
    # If it's not required, return None instead of raising an error
    return None

def process_chat_folder(chat_folder, output_folder):
    """
    Process a single chat folder and generate a formatted text file.

    Parameters:
        chat_folder (str): The path to the folder containing the chat data (including group_info.json and messages.json).
        output_folder (str): The path where the formatted text file will be saved.

    The function reads the `group_info.json` and `messages.json` files, formats the data, 
    and writes the conversation into a text file in the output folder.
    """
    group_info_path = os.path.join(chat_folder, "group_info.json")
    messages_path = os.path.join(chat_folder, "messages.json")

    # Ensure group_info.json exists
    if not os.path.exists(group_info_path):
        print(f"Skipping {chat_folder}: group_info.json not found.")
        return
    
    # Read group_info.json
    with open(group_info_path, "r", encoding="utf-8") as file:
        group_info = json.load(file)

    # Determine chat name
    chat_name = None
    folder_name = os.path.basename(chat_folder)
    
    if folder_name.startswith("DM"):
        # Direct message (use other participant's name)
        members = group_info.get("members", [])
        other_member = members[1] if len(members) > 1 else members[0]
        chat_name = other_member.get("name", None)
    elif folder_name.startswith("Space"):
        # Group chat (use group name)
        chat_name = group_info.get("name", folder_name)

        # If the name is "Group Chat", append member initials
        if chat_name == "Group Chat":
            member_initials = [
                "".join([part[0] for part in member["name"].split() if part])  # Extract initials
                for member in group_info.get("members", [])
            ]
            chat_name += " " + "".join(member_initials)  # Append initials to the name

    if not chat_name:
        chat_name = folder_name  # Fallback to folder name if needed

    # Ensure transcripts directory exists
    transcripts_dir = os.path.join(output_folder, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)  # Create if it doesn't exist

    # Set output path inside transcripts folder
    output_path = os.path.join(transcripts_dir, f"{chat_name}.txt")


    # Read messages.json
    if not os.path.exists(messages_path):
        print(f"Skipping {chat_name}: messages.json not found.")
        return

    with open(messages_path, "r", encoding="utf-8") as file:
        messages_data = json.load(file)

    messages = messages_data.get("messages", [])
    
    # Collect list of attachments
    attachments = [f for f in os.listdir(chat_folder) if f not in ("group_info.json", "messages.json")]

    # Write conversation to text file
    with open(output_path, "w", encoding="utf-8") as out_file:
        out_file.write(f"Chat: {chat_name}\n")
        out_file.write("=" * 40 + "\n\n")

        for msg in messages:
            creator = msg["creator"]["name"] if "creator" in msg else "Unknown"
            timestamp = msg["created_date"] if "created_date" in msg else "Unknown time"

            # Handle deleted messages
            if msg.get("message_state") == "DELETED":
                deletion_type = msg.get("deletion_metadata", {}).get("deletion_type", "Unknown reason")
                text = f"[Message deleted by {deletion_type}]"

            # Handle regular messages with text
            elif "text" in msg and msg["text"].strip():
                text = msg["text"]

            # Handle attachment messages
            elif "attached_files" in msg:
                attachments = msg["attached_files"]
                filenames = [
                    file.get("export_name", file.get("original_name", "Unknown File"))
                    for file in attachments
                ]
                text = "Attachment: " + ", ".join(filenames)

            # Fallback case (shouldn't normally happen)
            else:
                text = "[No text]"

            out_file.write(f"[{timestamp}] {creator}: {text}\n")


        # List attachments if any
        if attachments:
            out_file.write("\nAttachments:\n")
            out_file.write("-" * 40 + "\n")
            for attachment in attachments:
                out_file.write(f"- {attachment}\n")


def process_google_chat_folder(chat_root):
    """
    Process all chat folders inside the Groups subdirectory of the Google Chat directory.

    Parameters:
        chat_root (str): The root directory of the Google Chat export, where the 'Groups' folder is located.

    The function processes each folder inside the 'Groups' directory, calling `process_chat_folder`
    for each chat folder to generate formatted text files.
    """
    groups_folder = os.path.join(chat_root, "Groups")
    
    if not os.path.exists(groups_folder):
        print(f"Error: 'Groups' folder not found in {chat_root}")
        return
    
    output_folder = chat_root  # Store output in the root Google Chat folder
    chat_list = os.listdir(groups_folder)
    total_messages = len(chat_list)

    with tqdm(total=total_messages, desc="Processing Chats", unit=" chat") as pbar:
        for folder in chat_list:
            pbar.update(1)
            folder_path = os.path.join(groups_folder, folder)
            if os.path.isdir(folder_path):  # Process only directories
                process_chat_folder(folder_path, output_folder)

def extract_email_body(message):
    """Extract plain text body from an email message."""
    body = None
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(
                    part.get_content_charset(), errors="ignore"
                )
                if body.strip():  # Ensure it's not empty before breaking
                    break
    else:
        body = message.get_payload(decode=True).decode(
            message.get_content_charset(), errors="ignore"
        )
    
    return body if body and body.strip() else "[No content]"


def load_ignore_list(ignore_file):
    """Load email addresses to ignore from a file."""
    ignore_list = set()
    if os.path.exists(ignore_file):
        with open(ignore_file, "r", encoding="utf-8") as file:
            ignore_list = {line.strip() for line in file if line.strip()}
    return ignore_list

def clean_html(html):
    """Remove HTML tags and return plain text, but retain basic formatting tags."""
    allowed_tags = ['b', 'i', 'u', 'strong', 'em', 'br']
    soup = BeautifulSoup(html, "html.parser")
    
    # Strip unwanted tags
    for tag in soup.find_all(True):  # True will match all tags
        if tag.name not in allowed_tags:
            tag.unwrap()  # Remove the tag but keep its content
    
    return soup.get_text(separator="\n")


def process_mbox_to_pdf(mbox_path, output_pdf, ignore_list):
    """Process an MBOX file and generate a formatted PDF with email threading."""
    styles = getSampleStyleSheet()

    # Extract the folder where the MBOX file is located
    mbox_folder = os.path.dirname(os.path.abspath(mbox_path))

    # Check if the provided output_pdf already contains a folder path
    if os.path.isabs(output_pdf) or os.path.dirname(output_pdf):
        output_pdf_path = output_pdf  # Respect the full path provided
    else:
        # Otherwise, create the output PDF path in the same folder as the MBOX file
        output_pdf_path = os.path.join(mbox_folder, output_pdf)

    doc = SimpleDocTemplate(output_pdf_path, pagesize=letter)
    elements = []

    mbox = mailbox.mbox(mbox_path)
    total_messages = len(mbox)
    threads = defaultdict(list)
    messages_by_id = {}

    with tqdm(total=total_messages, desc="Processing Emails", unit=" email") as pbar:
        for message in mbox:
            msg_id = message["Message-ID"]
            in_reply_to = message["In-Reply-To"]
            references = message["References"]
            sender = message['From']
            # subject = message['Subject'] if message['Subject'] else "(No Subject)"
            # date = message['Date'] if message['Date'] else "(No Date)"

            # Parse sender to extract both name and email
            sender_name, sender_email = email.utils.parseaddr(sender)

            if sender_email in ignore_list:
                # print(f"Ignoring email from {sender_email} on {date} - Subject: {subject}")
                pbar.update(1)
                continue  # Skip ignored email addresses

            thread_id = in_reply_to or references or msg_id
            messages_by_id[msg_id] = message
            threads[thread_id].append(message)
            pbar.update(1)

    total_threads = len(threads)
    with tqdm(total=total_threads, desc="Organising Threads", unit=" thread") as pbar:
        for thread_id in threads:
            threads[thread_id].sort(key=lambda msg: msg["Date"] or "")
            pbar.update(1)

    with tqdm(total=total_threads, desc="Rendering PDF", unit=" thread") as pbar:
        for thread_id, messages in threads.items():
            for index, msg in enumerate(messages):
                sender = msg['From']
                # Parse sender to extract both name and email
                sender_name, sender_email = email.utils.parseaddr(sender)
                sender_display = f"{sender_name} ({sender_email})"

                recipient = msg['To']
                # Split the recipients and parse each one
                recipients = recipient.split(",") if recipient else []
                recipient_displays = []

                for recipient in recipients:
                    recipient_name, recipient_email = email.utils.parseaddr(recipient)
                    recipient_display = f"{recipient_name} ({recipient_email})" if recipient_name else recipient_email
                    recipient_displays.append(recipient_display)

                # Join the recipient display names with commas
                recipient_display = ", ".join(recipient_displays)

                subject = msg['Subject'] if msg['Subject'] else "(No Subject)"
                date = msg['Date'] if msg['Date'] else "(No Date)"
                labels = msg['X-Gmail-Labels'] if msg['X-Gmail-Labels'] else "(No Labels)"

                indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * index  # Indent replies
                email_header = [
                    Paragraph(f"{indent}From: {sender_display}", styles['Normal']),
                    Paragraph(f"{indent}To: {recipient_display}", styles['Normal']),
                    Paragraph(f"{indent}Date: {date}", styles['Normal']),
                    Paragraph(f"{indent}Subject: {subject}", styles['Normal']),
                    Paragraph(f"{indent}Labels: {labels}", styles['Normal']),
                    Spacer(1, 0.2 * inch),
                ]
                elements.extend(email_header)

                body = extract_email_body(msg)
                if body:
                    body_text = clean_html(body).replace("\n", "<br />")
                    elements.append(Paragraph(body_text, styles['Normal']))
                else:
                    elements.append(Paragraph("(No content)", styles['Italic']))
                
                elements.append(Spacer(1, 0.5 * inch))
                pbar.update(1)

    print("Creating PDF File...")
    doc.build(elements)
    print(f"Processed {mbox_path} into {output_pdf_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Google Chat Takeout data and MBOX emails.")
    parser.add_argument("--chat_root", help="Path to the Google Chat export folder")
    parser.add_argument("--mbox", help="Path to the MBOX file for email processing")
    parser.add_argument("--ignore", help="Path to a file containing email addresses to ignore", default="ignore_emails.txt")
    
    # Parse command-line arguments
    args = parser.parse_args()
    
    # Use the helper function to get the required arguments
    chat_root = get_arg_or_env('chat_root', 'CHAT_ROOT', required=False)
    mbox = get_arg_or_env('mbox', 'MBOX_PATH', required=False)
    ignore_list = load_ignore_list(get_arg_or_env('ignore', 'IGNORE_EMAILS_FILE', required=False))

    if not chat_root and not mbox:
        parser.print_help()
        exit(1)


    # Process the provided or environment-loaded arguments
    if chat_root:
        process_google_chat_folder(chat_root)
    if mbox:
        process_mbox_to_pdf(mbox, "emails_output.pdf", ignore_list)
