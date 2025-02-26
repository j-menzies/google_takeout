# Google Chat & Email Takeout Processor

## Overview

This Python script processes Google Chat data and emails exported using Google Takeout. 
- It extracts conversations from both direct messages (DMs) and group chats (Spaces) in Google Chat, formatting them into readable text files.
- It processes MBOX files containing emails, organizing them into threaded conversations and generating a PDF output.

## Features

**Google Chat Processing:**

- Processes chats stored in the `Google Chat/Groups` directory.
- Differentiates between Direct Messages (DMs) and Group Chats (Spaces).
- Names DM transcripts after the other participant.
- Names Group Chats using the group name, appending initials if the name is "Group Chat".
- Handles deleted messages and marks them appropriately.
- Lists attachments sent in the chat.
- Saves transcripts in a `transcripts/` directory within the Google Chat export folder.

**Email Processing:**

- Reads email data from an MBOX file.
- Organizes emails into threaded conversations based on subject and references.
- Extracts sender, recipient, subject, date, and labels for each email.
- Handles HTML content, converting it to plain text while retaining basic formatting.
- Generates a PDF file with the formatted email conversations.
- Allows specifying an ignore list to exclude emails from certain addresses.

## File Structure

**Google Chat:**

The script expects the following structure inside the exported Google Chat folder:
```
Google Chat/
│
├── Groups/
│   ├── DM_12345/   # Direct Message
│   │   ├── group_info.json
│   │   ├── messages.json
│   │   ├── attachment1.png
│   │   ├── attachment2.pdf
│   │
│   ├── Space_67890/  # Group Chat
│   │   ├── group_info.json
│   │   ├── messages.json
│   │   ├── attachment3.docx
│
├── transcripts/  # Output folder created by the script
│   ├── John Doe.txt
│   ├── Team Chat JD.txt
```

## Installation & Requirements

- Python 3.6 or higher
- `tqdm`
- `beautifulsoup4`
- `reportlab`
- `python-dotenv`

You can install these packages using pip:

```bash
pip install tqdm beautifulsoup4 reportlab python-dotenv
```

## Usage
### Google Chat Processing
Ensure your Google Takeout export has been extracted.
Run the script with the --chat_root argument, providing the path to the extracted Google Chat directory.
```bash
python process_takeout.py --chat_root "/path/to/Google Chat" 
```
**Example:**

```bash
python process_takeout.py --chat_root "~/Downloads/Takeout/Google Chat"
```
### Email Processing
  - Have your MBOX file ready.
- Run the script with the --mbox argument, providing the path to your MBOX file.
```bash
python process_takeout.py --mbox "/path/to/your_emails.mbox"
```
**Example:**

```bash
python process_takeout.py --mbox "~/Downloads/my_mailbox.mbox" 
```
**Ignoring Emails:**

- Create a file named ignore_emails.txt (or specify a different file using the --ignore argument).
- Add one email address per line to this file.
- Emails from these addresses will be excluded from the PDF output.

**Using Environment Variables**

Alternatively, you can set the following environment variables:

- ```CHAT_ROOT```: Path to the Google Chat export folder.
- ```MBOX_PATH```: Path to the MBOX file.
- ```IGNORE_EMAILS_FILE```: Path to the ignore list file.

This allows you to run the script without command-line arguments:

```bash
export CHAT_ROOT="/path/to/Google Chat"
export MBOX_PATH="/path/to/your_emails.mbox"
python process_takeout.py
```

## Output
**Google Chat:**

Each chat is saved as a `.txt` file in the `transcripts/` directory. The format is:
```
Chat: John Doe
========================================

[Thursday, 8 August 2024 at 12:04:08 UTC] John Doe: Hi Dave, You have Org Admin for our Atlassian site now
[Thursday, 8 August 2024 at 12:04:52 UTC] Dave Smith: Great, thanks John
[Wednesday, 14 August 2024 at 07:29:51 UTC] John Doe: Morning Dave, Can you try again? There was a permission I missed but it should be right now

Attachments:
----------------------------------------
- Screenshot 2024-08-20 at 10.07.49.png
```
**Email:**

- A PDF file named emails_output.pdf (by default) is generated in the same directory as the MBOX file.
- Emails are organized into threads and formatted with sender, recipient, subject, date, and body content.


## Notes
- If `group_info.json` or `messages.json` is missing, the chat is skipped.
- If a message was deleted, it is marked as:
  ```
  [Message deleted by CREATOR]
  ```
- Attachments are listed at the end of the transcript.

## License
This script is provided as-is, without warranty or guarantee. Modify and use as needed!

