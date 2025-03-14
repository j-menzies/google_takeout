import os
import json
import argparse
import mailbox
import email.utils
import openpyxl
import re

from tqdm import tqdm
from bs4 import BeautifulSoup
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from dotenv import load_dotenv
from ics import Calendar
from email import policy
from email.utils import parseaddr
from email.utils import parsedate_tz, mktime_tz
from datetime import datetime

# Load environment variables from the .env file
load_dotenv()

OUTPUT_ICS_ATTACHMENTS = os.getenv("OUTPUT_ICS_ATTACHMENTS", "false").strip().lower() in ("true", "1", "t", "y", "yes")

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
        out_file.write(f"Participants: {', '.join(member.get('name',member.get('email','')) for member in group_info.get('members', []))}\n")
        out_file.write(f"Messages: {len(messages)}\n")
        out_file.write(f"Attachments: {len(attachments)}\n")
        out_file.write(f"Message Path: {messages_path}\n")
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

            # Handle if there is a URL only in the message
            elif msg.get('annotations', [{}])[0].get('url_metadata', {}).get('image_url', None):
                text = msg.get('annotations', [{}])[0].get('url_metadata', {}).get('image_url')
            
            # Handle if there is a Meeting URL in the message
            elif msg.get('annotations', [{}])[0].get('video_call_metadata', {}).get('meeting_space', {}).get('meeting_url',None):
                text = msg.get('annotations', [{}])[0].get('video_call_metadata', {}).get('meeting_space', {}).get('meeting_url')

            # Handle if there is Call Data in the message
            elif msg.get('annotations', [{}])[0].get('gsuite_integration_metadata', {}).get('call_data', None):
                call_data = msg.get('annotations', [{}])[0].get('gsuite_integration_metadata', {}).get('call_data', {})
                text = f"Call Data: {call_data}"

            # Handle if there is a Google Doc in the message
            elif msg.get('annotations', [{}])[0].get('drive_metadata', None):
                drive_document = msg.get('annotations', [{}])[0].get('drive_metadata', {})
                text = f"Drive Document: {drive_document}"
            
            # Handle if there are Annotations that I haven't catered for specifically
            elif 'annotations' in msg:
                text = f"Annotations: {msg['annotations']}"
            
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


def load_ignore_list(ignore_file):
    """Load email addresses to ignore from a file."""
    ignore_list = set()
    if os.path.exists(ignore_file):
        with open(ignore_file, "r", encoding="utf-8") as file:
            ignore_list = {line.strip() for line in file if line.strip()}
    return ignore_list

def clean_style_attributes(style):
    """Clean unsupported style attributes and convert them to supported ones."""
    # Define a mapping of unsupported attributes to their supported equivalents (if any)
    attribute_mapping = {
        'textTransform': 'textCase',  # Convert 'textTransform' to 'textCase'
        'textColor': 'textColor',     # 'textColor' is supported
        'fontWeight': 'bold',         # Convert 'fontWeight' to 'bold'
        'fontStyle': 'italic',       # Convert 'fontStyle' to 'italic'
        'textDecoration': 'underline',  # Convert 'textDecoration' to 'underline'
        'fontFamily': 'fontName',     # Convert 'fontFamily' to 'fontName'
        'fontSize': 'fontSize',       # 'fontSize' is supported
        'backgroundColor': 'backColor',  # Convert 'backgroundColor' to 'backColor'
    }
    
    # Define supported attributes
    supported_attributes = {
        'fontName', 'fontSize', 'leading', 'textColor', 'alignment', 'backColor',
        'spaceBefore', 'spaceAfter', 'bold', 'italic', 'underline', 'strike',
        'firstLineIndent', 'leftIndent', 'rightIndent', 'bulletText', 'bulletFontName',
        'bulletFontSize', 'textCase', 'listStyle', 'listMarker'
    }

    # Remove unsupported attributes and convert them if applicable
    cleaned_style = {}
    for attr, value in style.items():
        if attr in supported_attributes:
            cleaned_style[attr] = value
        elif attr in attribute_mapping:
            # Convert unsupported attribute to supported attribute
            cleaned_style[attribute_mapping[attr]] = value

    return cleaned_style

def parse_style(style_string):
    """Parse the inline 'style' attribute into a dictionary."""
    style_dict = {}
    for rule in style_string.split(';'):
        if rule.strip():
            key, value = rule.split(':', 1)
            style_dict[key.strip()] = value.strip()
    return style_dict

def format_style(style_dict):
    """Convert a style dictionary back into a 'style' string."""
    return '; '.join(f'{key}: {value}' for key, value in style_dict.items())

def clean_html(html):
    """Sanitize HTML for ReportLab's Paragraph while keeping basic formatting."""
    soup = BeautifulSoup(html, "html.parser")

    # List of supported HTML tags
    supported_html_tags = [
        'b', 'strong',  # Bold text
        'i', 'em',      # Italic text
        'u',              # Underlined text
        'strike',         # Strikethrough text
        'sub',            # Subscript text
        'sup',            # Superscript text
        'font',           # Font face, size, and color (deprecated)
        'p',              # Paragraph tag
        'br',             # Line break
        'ul',             # Unordered list
        'ol',             # Ordered list
        'li',             # List item
        'a',              # Hyperlink
        'center',         # Center-align text (deprecated)
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6'  # Header tags
    ]

    # Iterate through all tags in the HTML
    for tag in soup.find_all(True):  # True means find all tags
        if tag.name not in supported_html_tags:
            tag.unwrap()  # Remove the tag but keep its contents
        else:
            # Clean attributes of the supported tags
            tag.attrs = {key: value for key, value in tag.attrs.items() if key in ["href", "name", "target"]}

            # If the tag has a 'style' attribute, clean it
            if 'style' in tag.attrs:
                style = tag.attrs['style']
                cleaned_style = clean_style_attributes(parse_style(style))
                tag.attrs['style'] = format_style(cleaned_style)  # Reassign cleaned style

    # Remove complex structures (tables, divs, spans) but keep content
    for tag in soup(["table", "tr", "td", "th", "tbody", "tfoot", "thead", "div", "span"]):
        tag.unwrap()  # Keep content but remove tag

    # Convert <br> to <br/> for proper line breaks
    for br in soup.find_all("br"):
        br.replace_with("<br/>")

    # Strip attributes that ReportLab doesn't support
    for tag in soup.find_all(True):
        tag.attrs = {key: value for key, value in tag.attrs.items() if key in ["href", "name", "target"]}

    return str(soup)



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

def process_body_part(part):
    content_type = part.get_content_type()
    body = part.get_payload(decode=True).decode(errors="ignore")
    if not body:
        return ""

    if content_type == "text/plain":
        return body.replace("\n", "<br/>")  # Ensure line breaks work in ReportLab
    elif content_type == "text/html":
        return clean_html(body)  # Ensure proper HTML formatting

def extract_email_body(message):
    """Extracts and combines email body parts while ensuring correct formatting."""
    body_parts = []
    html_part = None

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()

            # Skip multipart containers (e.g., multipart/alternative, multipart/mixed)
            if content_type.startswith("multipart/"):
                continue

            if content_type == "message/delivery-status":
                body_parts.append("Delivery Status Message - Not extracting content")
                # Skip delivery status notifications
                continue

            # Handle message/rfc822 (nested email)
            if content_type == "message/rfc822":
                # Recursively extract the body of the embedded email
                nested_html_body, nested_text_body = extract_email_body(part.get_payload(0))
                for text_body in nested_text_body:
                    body_parts.append(text_body)
                if nested_html_body:
                    html_part = nested_html_body
                continue

            processed_part = process_body_part(part)
            if processed_part:
                if content_type == "text/html":
                    html_part = processed_part  # Prefer HTML if available
                else:
                    body_parts.append(processed_part)  # Keep text/plain content

        return html_part, "<br/>".join(body_parts)  # Use HTML if available, otherwise join plain text
    else:
        return process_body_part(message),""  # Handle non-multipart emails


def sanitize_filename(filename):
    """Sanitize the filename by replacing special characters with underscores."""
    # List of characters to replace
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']
    
    for char in unsafe_chars:
        filename = filename.replace(char, "_")
    
    return filename

def save_attachment(message, output_folder):
    """Extracts and saves attachments from an email."""
    attachments = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                filename = sanitize_filename(part.get_filename())
                if filename == "invite.ics" and not OUTPUT_ICS_ATTACHMENTS:
                    # We don't wan't these
                    continue
                os.makedirs(output_folder, exist_ok=True)
                
                if filename:
                    filepath = os.path.join(output_folder, filename)
                    with open(filepath, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    attachments.append(filename)
    return attachments

def process_mbox_to_pdfs(mbox_path, ignore_list):
    """Processes an MBOX file and creates a separate PDF for each email."""

    # Extract the folder where the MBOX file is located
    output_folder = os.path.join(os.path.dirname(os.path.abspath(mbox_path)),"emails_output")

    os.makedirs(output_folder, exist_ok=True)
    mbox = mailbox.mbox(mbox_path, factory=lambda f: email.message_from_binary_file(f, policy=policy.default))
    styles = getSampleStyleSheet()
    total_messages = len(mbox)
    ignore_count = 0
    processed_count = 0
    
    with tqdm(total=total_messages, desc="Processing Emails", unit=" email") as pbar:
        for i, message in enumerate(mbox):
            sender_name, sender_email = parseaddr(message["From"])
            if sender_email in ignore_list:
                ignore_count += 1
                pbar.update(1)
                continue
            
            subject = message["Subject"] if message["Subject"] else "No Subject"
            date = message["Date"] if message["Date"] else "No Date"
            recipient = message["To"] if message["To"] else "No Recipient"

            parsed_date = parsedate_tz(date)
            if parsed_date:
                email_date = datetime.fromtimestamp(mktime_tz(parsed_date)).strftime("%Y%m%d")
            else:
                email_date = "NoDate"

            # Generate file-safe subject
            safe_subject = "_".join(subject.split()).replace("/", "_").replace("\\", "_")
            max_length = 100  # You can adjust this length as needed
            safe_subject = safe_subject[:max_length]  # Truncate if necessary
            pdf_filename = f"{i+1:04d}_{email_date}_{safe_subject}.pdf"
            pdf_path = os.path.join(output_folder, pdf_filename)
            
            # Extract email body
            html_body, text_body = extract_email_body(message)
            
            # Save attachments
            email_folder = os.path.join(output_folder, f"email_{i+1:04d}")
            attachments = save_attachment(message, email_folder)
            
            # Create PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            elements = [
                Paragraph(f"From: {sender_name} ({sender_email})", styles["Normal"]),
                Paragraph(f"To: {recipient}", styles["Normal"]),
                Paragraph(f"Date: {date}", styles["Normal"]),
                Paragraph(f"Subject: {subject}", styles["Normal"]),
                Spacer(1, 0.2 * inch)
                # Paragraph(body if body else "(No content)", styles["Normal"]),
                
            ]
            try:
                if text_body and len(text_body) > 0:
                    body_paragraph = Paragraph(text_body, styles["Normal"])
                else:
                    body_paragraph = Paragraph(html_body, styles["Normal"])
            except Exception as e:
                print(f"Error: Unable to extract text body from email sender: {sender_email} subject: {subject} on {date}")
                print("Will use Text Body instead")
                try:
                    body_paragraph = Paragraph(text_body, styles["Normal"])
                except Exception as e:
                    print("Error: Unable to extract text body from email, putting in a default message")
                    body_paragraph = Paragraph("Unable to extrack any content, Sorry", styles["Normal"])
            
            elements.append(body_paragraph)
            elements.append(Spacer(1, 0.5 * inch))

            if attachments:
                elements.append(Paragraph("Attachments:", styles["Normal"]))
                for attachment in attachments:
                    elements.append(Paragraph(attachment, styles["Italic"]))
            
            doc.build(elements)
            processed_count += 1
            pbar.update(1)
    print(f"Processed {processed_count}/{total_messages} emails into PDFs in {output_folder}. Ignored {ignore_count} emails.")

def parse_ics(ics_file):
    with open(ics_file, "r", encoding="utf-8") as file:
        print("Reading Calendar...")
        calendar = Calendar(file.read())
    
    events = []
    enclosing_pattern = r"-::~:~::~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~:~::~:~::-"
    meet_pattern = r"https://meet\.google\.com/([a-z]+-[a-z]+-[a-z]+)"
    total_events = len(calendar.events)
    
    with tqdm(total=total_events, desc="Processing Events", unit=" event") as pbar:
        for event in calendar.events:
            attendees = []
            if hasattr(event, "attendees") and event.attendees:
                for attendee in event.attendees:
                    if hasattr(attendee, "partstat"):
                        status = attendee.partstat  # Extract participation status
                        attendees.append(f"{attendee.common_name} ({status})")

            description = event.description if event.description else ""
            meet_code = ""

            meet_match = re.search(meet_pattern, description)
            if meet_match:
                meet_code = meet_match.group(1)

            # Remove enclosed content
            description = re.sub(f"{enclosing_pattern}.*?{enclosing_pattern}", "", description, flags=re.DOTALL).strip()

            events.append([
                event.name,
                event.begin.to('local').format("YYYY-MM-DD HH:mm"),
                event.end.to('local').format("YYYY-MM-DD HH:mm") if event.end else "",
                event.location if event.location else "",
                description,
                "; ".join(attendees) if attendees else "No attendees recorded",
                meet_code
            ])
            pbar.update(1)

    return events

def write_to_excel(events, output_file):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Calendar Events"
    
    headers = ["Event Name", "Start Time", "End Time", "Location", "Description", "Accepted Attendees", "Meet Code"]
    ws.append(headers)
    
    for event in events:
        ws.append(event)
    
    wb.save(output_file)


def process_calendar(ics_file):
    
    print(f"Processing Calendar... {ics_file}")
    # Extract the folder where the ics file is located
    ics_path = os.path.dirname(os.path.abspath(ics_file))
    ics_file_name = ics_file_name = os.path.splitext(os.path.basename(ics_file))[0]
    output_file = os.path.join(ics_path, f"{ics_file_name}.xlsx")
    
    if not os.path.exists(ics_file):
        print("Error: ICS file not found.")
        return
    
    events = parse_ics(ics_file)
    write_to_excel(events, output_file)
    print(f"Spreadsheet saved as {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Google Chat Takeout data and MBOX emails.")
    parser.add_argument("--chat_root", help="Path to the Google Chat export folder")
    parser.add_argument("--mbox", help="Path to the MBOX file for email processing")
    parser.add_argument("--split", action="store_true", help="Split the MBOX file into individual files")
    parser.add_argument("--ics", help="Path to the Calendar file for processing")
    parser.add_argument("--ignore", help="Path to a file containing email addresses to ignore", default="ignore_emails.txt")
    
    # Parse command-line arguments
    args = parser.parse_args()
    
    # Use the helper function to get the required arguments
    chat_root = get_arg_or_env('chat_root', 'CHAT_ROOT', required=False)
    mbox = get_arg_or_env('mbox', 'MBOX_PATH', required=False)
    ignore_list = load_ignore_list(get_arg_or_env('ignore', 'IGNORE_EMAILS_FILE', required=False))
    ics_file = get_arg_or_env('ics', 'ICS_FILE', required=False)

    if not chat_root and not mbox and not ics_file:
        parser.print_help()
        exit(1)

    # Process the provided or environment-loaded arguments
    if chat_root:
        process_google_chat_folder(chat_root)
    if mbox:
        if args.split:
            process_mbox_to_pdfs(mbox,ignore_list)  # Split MBOX into individual files
        else:
            process_mbox_to_pdf(mbox, "emails_output.pdf", ignore_list)
    if ics_file:
        process_calendar(ics_file)
