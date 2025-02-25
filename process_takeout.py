import os
import json
import argparse
import mailbox
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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

    print(f"Processed chat: {chat_name}")


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

    for folder in os.listdir(groups_folder):
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
                break
    else:
        body = message.get_payload(decode=True).decode(
            message.get_content_charset(), errors="ignore"
        )
    return body or "[No content]"

def process_mbox_to_pdf(mbox_file, output_pdf):
    """Extracts emails from an mbox file, groups them by thread, and writes to a PDF."""
    mbox = mailbox.mbox(mbox_file)

    # Step 1: Organize emails into threads
    threads = defaultdict(list)
    messages_by_id = {}

    for message in mbox:
        msg_id = message["Message-ID"]
        in_reply_to = message["In-Reply-To"]
        references = message["References"]

        messages_by_id[msg_id] = message

        # Determine thread grouping
        thread_id = in_reply_to or references or msg_id
        threads[thread_id].append(message)

    # Step 2: Sort emails within each thread by date
    for thread_id in threads:
        threads[thread_id].sort(key=lambda msg: msg["date"])

    # Step 3: Generate the PDF
    c = canvas.Canvas(output_pdf, pagesize=letter)
    width, height = letter
    y_position = height - 40  # Start near top of the page

    def write_email(msg, indent=0):
        """Writes an email message to the PDF with indentation for threads."""
        nonlocal y_position

        sender = msg["from"] or "Unknown Sender"
        date = msg["date"] or "Unknown Date"
        subject = msg["subject"] or "No Subject"
        body = extract_email_body(msg)

        # Indent replies for readability
        x_offset = 40 + (indent * 20)

        # Ensure space for new content
        if y_position < 100:
            c.showPage()
            y_position = height - 40

        c.setFont("Helvetica-Bold", 12)
        c.drawString(x_offset, y_position, f"From: {sender}")
        y_position -= 20
        c.drawString(x_offset, y_position, f"Date: {date}")
        y_position -= 20
        c.drawString(x_offset, y_position, f"Subject: {subject}")
        y_position -= 20
        c.setFont("Helvetica", 10)
        c.drawString(x_offset, y_position, "-" * 60)
        y_position -= 20

        # Write body with line wrapping
        for line in body.split("\n"):
            c.drawString(x_offset, y_position, line)
            y_position -= 15
            if y_position < 100:
                c.showPage()
                y_position = height - 40

        y_position -= 30  # Space between messages

    # Step 4: Write emails to PDF
    for thread_id, messages in threads.items():
        for index, msg in enumerate(messages):
            write_email(msg, indent=index)  # Indent replies deeper

    c.save()
    print(f"Processed {mbox_file} -> {output_pdf}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Google Chat Takeout data and MBOX emails.")
    parser.add_argument("--chat_root", help="Path to the Google Chat export folder")
    parser.add_argument("--mbox", help="Path to the MBOX file for email processing")
    parser.add_argument("--ignore", help="Path to a file containing email addresses to ignore", default="ignore_emails.txt")
    args = parser.parse_args()

    ignore_list = load_ignore_list(args.ignore)
    
    if args.chat_root:
        process_google_chat_folder(args.chat_root)
    if args.mbox:
        process_mbox_to_pdf(args.mbox, "emails_output.pdf", ignore_list)
