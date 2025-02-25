# Google Chat Takeout Processor

## Overview
This Python script processes Google Chat data exported using Google Takeout. It extracts conversations from both direct messages (DMs) and group chats (Spaces), formatting them into readable text files.

## Features
- Processes chats stored in the `Google Chat/Groups` directory.
- Differentiates between Direct Messages (DMs) and Group Chats (Spaces).
- Names DM transcripts after the other participant.
- Names Group Chats using the group name, appending initials if the name is "Group Chat".
- Handles deleted messages and marks them appropriately.
- Lists attachments sent in the chat.
- Saves transcripts in a `transcripts/` directory within the Google Chat export folder.

## File Structure
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
This script requires Python 3. No additional dependencies are needed.

## Usage
1. Ensure your Google Takeout export has been extracted.
2. Run the script, providing the path to the extracted `Google Chat` directory.

```sh
python process_takeout.py "/path/to/Google Chat"
```

### Example
If your extracted data is in `~/Downloads/Takeout/Google Chat`, run:
```sh
python process_takeout.py "~/Downloads/Takeout/Google Chat"
```

## Output
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

## Notes
- If `group_info.json` or `messages.json` is missing, the chat is skipped.
- If a message was deleted, it is marked as:
  ```
  [Message deleted by CREATOR]
  ```
- Attachments are listed at the end of the transcript.

## License
This script is provided as-is, without warranty or guarantee. Modify and use as needed!

