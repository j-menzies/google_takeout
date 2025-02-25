import os
import json
import argparse

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

if __name__ == "__main__":
    """
    Main entry point for processing Google Chat data exported via Google Takeout.

    The script takes a single argument: the path to the Google Chat export folder, 
    processes the chat folders inside it, and generates formatted text files for each chat.

    Usage:
        python script_name.py /path/to/google/chat/export
    """
    parser = argparse.ArgumentParser(description="Process Google Chat Takeout data.")
    parser.add_argument("chat_root", help="Path to the Google Chat export folder")
    args = parser.parse_args()

    process_google_chat_folder(args.chat_root)
