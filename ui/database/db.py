from fasthtml.common import *
from monsterui.all import *
from fasthtml.svg import *
from dataclasses import dataclass
from pathlib import Path
import os
import json
from datetime import datetime
from typing import List, Optional, Union, Tuple
import apsw
import time

# Define folder for storing large files that don't fit in the database
DB_PATH = os.getenv("DB_PATH", "database")
UPLOAD_DIR = Path(DB_PATH, "uploads")
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)  # Added parents=True to create parent directories

# File size threshold for deciding whether to store in DB or on disk (1MB)
MAX_DB_SIZE = 1_000_000


# === Chat Data Model ===
from dataclasses import field

# Chat Message Data Model
@dataclass
class ChatMessage:
    id: str = None
    chat_id: str = None
    role: str = "user"
    content: str = ""
    created_at: float = 0
    username: str = ""

    def from_dict(cls, data: dict) -> 'ChatMessage':
        return cls(
            role=data['role'],
            content=data['content'],
            created_at=data['created_at']
        )
    
    def to_dict(self) -> dict:
        return {
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at
        }
    
    @classmethod
    def to_string(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_string(self, string: str):
        return self.from_dict(json.loads(string))
    


# @dataclass
# class ChatModel:
#     id: str = None
#     chat_id: str = None
#     message: str = ""
#     # messages: List[str] = field(default_factory=list)
#     created_at: float = 0
#     updated_at: float = 0
#     username: str = ""


# === File Data Model ===

@dataclass
class FileModel:
    """
    Data model for storing file metadata and content in FastLite database.
    
    This model supports a hybrid storage approach:
    - Small files (like images) can be stored directly in the database as bytes
    - Larger files (like PDFs) can be stored on disk with their paths referenced
    """
    id: str = None          # Unique file identifier
    name: str = ""          # Original filename
    size: int = 0           # File size in bytes
    type: str = ""          # MIME type
    upload_time: float = 0  # Timestamp when file was uploaded
    data: str = None      # File content for small files (stored in DB) - CORRECTED TYPE
    path: str = None        # File path for large files (stored on disk)
    status: str = "uploaded"  # File processing status: uploaded, processing, complete, error
    username: str = ""      # User who uploaded the file

    @property
    def size_formatted(self) -> str:
        """Format the file size in a human-readable format."""
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    @property
    def upload_time_formatted(self) -> str:
        """Format the upload time in a human-readable format."""
        return datetime.fromtimestamp(self.upload_time).strftime("%Y-%m-%d")
    
    @property
    def extension(self) -> str:
        """Get the file extension."""
        return os.path.splitext(self.name)[1].lower()
    
    @property
    def is_image(self) -> bool:
        """Check if the file is an image."""
        return self.type.startswith('image/')
    
    @property
    def is_pdf(self) -> bool:
        """Check if the file is a PDF."""
        return self.type == 'application/pdf'
    
    @property 
    def is_viewable(self) -> bool:
        """Check if the file can be viewed in the browser."""
        return self.is_image or self.is_pdf
    
    @property
    def stored_in_db(self) -> bool:
        """Check if the file content is stored in the database."""
        return self.data is not None
    
    @property
    def stored_on_disk(self) -> bool:
        """Check if the file content is stored on disk."""
        return self.path is not None and Path(self.path).exists()


# === Database Setup ===

# Create or open the database file
files_db = database(Path(DB_PATH, "files.db"))
chat_db = database(Path(DB_PATH, "chat.db"))

# Create the files table based on the FileModel 
if 'files' not in files_db.t:
    print("Creating files table...")
    files = files_db.create(
        FileModel, 
        name="files",  # Explicit table name
        pk="id", 
        if_not_exists=True,
        not_null=["name", "size", "type", "upload_time", "username"],  # Required fields
        defaults={"upload_time": time.time()}  # Default upload time to now
    )
    
    print(f"Created file_model table: {files}")
else:
    print("Table 'files' already exists")
    files = files_db.t.files

# Create the files table based on the FileModel 
if 'chats' not in chat_db.t:
    print("Creating files table...")
    chats = chat_db.create(
        ChatMessage, 
        name="chats",  # Explicit table name
        pk="id", 
        if_not_exists=True,
        not_null=["content", "created_at", "username"],  # Required fields
        defaults={"created_at": time.time(), "content": ""}  # Default upload time to now
    )
    
    print(f"Created chat_model table: {chats}")
else:
    print("Table 'chats' already exists")
    chats = chat_db.t.chats

# Create a view for recent files
try:
    files_db.create_view(
        "RecentFiles", 
        "SELECT * FROM files ORDER BY upload_time DESC LIMIT 10",
    )
    print("Created RecentFiles view")
except apsw.SQLError:
    print("View exists")

# Store the model dataclass with the table
files.cls = FileModel
chats.cls = ChatMessage

# Make sure tables can be queried
try:
    count = len(files())
    print(f"File table contains {count} files")
except Exception as e:
    print(f"Error querying files table: {e}")
    import traceback
    print(traceback.format_exc())


# === Chat Functions ===

def get_chat(chat_id: str) -> Optional[ChatMessage]:
    """Get a chat from the database by ID."""
    return chats[chat_id]


def get_chat_messages(chat_id: str) -> Union[List[ChatMessage], List]:
    """Get all messages for a specific chat."""
    return chats(f"chat_id = ?", [chat_id], order_by='created_at ASC')

def get_user_chats(username) -> Union[List[ChatMessage], List]:
    """Get all chats for a specific user."""
    return chats(f"username = ?", [username], order_by='created_at DESC')

def create_chat(chat: ChatMessage) -> None:
    """Add a chat to the database."""
    chat = chats.insert(chat)
    return chat

def add_message(message: ChatMessage) -> None:
    """Add a message to a chat."""
    chats.insert(message)

# === File Functions ===

def get_file(file_id: str) -> Optional[FileModel]:
    """
    Get a file from the database by ID.
    
    Args:
        file_id: The ID of the file to retrieve
        
    Returns:
        FileModel object if found, None otherwise
    """
    try:
        # Use FastLite's indexing to get the file by primary key
        return files[file_id]
    except:
        return None

def get_files() -> Union[List[FileModel], List]:
    """Get all files from the database."""
    return files(order_by='upload_time DESC')

def get_user_files(username) -> Union[List[FileModel], List]:
    """
    Get files for a specific user.
    
    Args:
        username: Can be either:
                 - A simple username string
                 - A user object with 'user_id' attribute for actual database lookups
                 - A user object with 'id' attribute
                
    Returns:
        List of FileModel objects belonging to the user
    """
    # If username is actually a user object with user_id (from our auth changes)
    if isinstance(username, dict) and 'user_id' in username:
        user_id = username['user_id']
        return files(f"username = ?", [user_id], order_by='upload_time DESC')
    
    # If username is a user object with id
    elif isinstance(username, dict) and 'id' in username:
        user_id = username['id']
        return files(f"username = ?", [user_id], order_by='upload_time DESC')
    
    # For backward compatibility, use username as is
    return files(f"username = ?", [username], order_by='upload_time DESC')

def get_file_content(file: FileModel) -> Tuple[bytes, bool]:
    """
    Get the content of a file, whether stored in DB or on disk.
    
    Args:
        file: The FileModel object
        
    Returns:
        Tuple of (file_content, success)
    """
    if file.stored_in_db:
        return file.data, True
    elif file.stored_on_disk:
        try:
            return Path(file.path).read_bytes(), True
        except:
            return b"", False
    else:
        return b"", False

def format_size(size_in_bytes: int) -> str:
    """
    Format file size in a human-readable format.
    
    Args:
        size_in_bytes: The size in bytes
        
    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.1f} TB" 