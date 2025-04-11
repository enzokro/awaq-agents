import uuid
import time
import mimetypes
import json
from pathlib import Path
from fastcore.xtras import *
from fasthtml.common import *
from monsterui.all import * 
from database.db import *
import traceback

# manually hook in the path for now
import sys
sys.path.append("/Users/cck/projects/cck-agents/")

### AGENT 
from dotenv import load_dotenv
load_dotenv()

# Attempt to import necessary components
# from profiles.agents.example_agent.agent import profile as agent_profile
from profiles.agents.simple_pdf_rag_agent.agent import profile as agent_profile
# from profiles.agents.document_summarizer.agent import profile as summarizer_profile
from framework.agent_runner import AgentRunner


# runner = AgentRunner(
#     profile=agent_profile,
#     # use_toolloop=False,
# )

### Helpers

def generate_file_id() -> str:
    """
    Generate a unique ID for a file.
    
    Returns:
        A string containing a unique identifier
    """
    return f"{int(time.time())}_{uuid.uuid4().hex[:8]}"

def guess_mime_type(filename: str) -> str:
    """
    Guess the MIME type of a file based on its filename.
    
    Args:
        filename: The name of the file
        
    Returns:
        String with the MIME type
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'

### APP

# setup the headers
## sets the theme
theme_headers = Theme.slate.headers(mode="light")
## makes our app full-screen
full_screen_style = Link(rel="stylesheet", href="/static/styles.css")
## sets the favicon
favicon_headers = Favicon(light_icon="/static/logo.png", dark_icon="/static/logo.png")

pdf_scripts = [
    # 1. First load the core PDF.js library - must be kept as a module
    Script(src='/static/pdfjs/build/pdf.js', type="module"),
    
    # 2. Also load the worker as a module
    Script(src='/static/pdfjs/build/pdf.worker.js', type="module"),
    
    # 3. Bridge script for handling ES modules
    Script(src="/static/pdfjs-helpers/esm_bridge.js"),

    # 4. Load modular components
    Script(src='/static/pdfjs-helpers/pdf-core.js', type="module"),
    Script(src='/static/pdfjs-helpers/pdf-document.js', type="module"),
    Script(src='/static/pdfjs-helpers/pdf-viewport.js', type="module"),
    Script(src='/static/pdfjs-helpers/pdf-renderer.js', type="module"),
    Script(src='/static/pdfjs-helpers/pdf-viewer.js', type="module"),
    Script(src='/static/pdfjs-helpers/index.js', type="module"),
    # 5. Load the PDF initializer
    Script(src='/static/pdfjs-helpers/pdf-initializer.js', type="module"),
]


hdrs = [
    theme_headers, 
    full_screen_style, 
    favicon_headers,
    *pdf_scripts,
]

# create the app
app_name = os.getenv("APP_NAME", "InfraRead 2.0")

app, rt = fast_app(
    hdrs=hdrs,
)

### COMPONENTS

def nav_button(name, href, cls=ButtonT.default):
    """Helper function to create a styled navigation button."""
    return A(
        Button(name, cls=cls),
        href=href,
        cls="px-1"
    )

def get_navbar(app_name='', auth=None, request=None, sess=None):
    """
    Generate the application navbar with authentication-aware elements.
    
    Args:
        app_name: The name of the application to display in the brand area
        auth: The username of the authenticated user (None for guests)
        request: HTTP request object containing user info
        sess: Session object that may contain display name
    
    Returns:
        A NavBar component with appropriate navigation options
    """
    # Common navigation items that appear for all users
    common_items = [
        nav_button("Home", href='/', cls=ButtonT.text +" text-primary font-bold text-lg px-2"),
        nav_button("Files", href='/files', cls=ButtonT.text +" text-primary font-bold text-lg px-2 mr-4"),
    ]
    
    # Create the navbar with brand, common items, and user section
    return NavBar(
        *common_items,
        brand=DivLAligned(
            Img(src="/static/logo.png", width=45, height=45, alt="Site Logo", cls="site-logo"),
            H2(app_name, cls="font-bolder pl-1"),
            cls="flex items-center"
        ),
        cls="border-b shadow-sm p-2 rounded-lg"  # Additional styling
    )


def ChatMessageUI(role, content):
    """Creates a styled chat message bubble"""
    colors = {
        'system': {'bg': 'bg-gray-200', 'text': 'text-gray-800'},
        'user': {'bg': 'bg-blue-500', 'text': 'text-white'},
        'InfraAI': {'bg': 'bg-gray-200', 'text': 'text-gray-800'}
    }
    style = colors.get(role.lower(), colors['system'])
    
    align_cls = 'justify-end' if role.lower() == 'user' else 'justify-start'
    
    return Div(cls=f'flex {align_cls} mb-4')(
        Div(cls=f'{style["bg"]} {style["text"]} rounded-2xl p-4 max-w-[80%]')(
            Strong(role.capitalize(), cls='text-sm font-semibold tracking-wide'),
            Div(content, cls='mt-2')
        )
    )

def create_chat_messages_ui(messages: list[dict]=[]):
    """Creates a structured chat messages container with proper empty state handling"""
    
    # Determine if we're in empty state or have messages
    is_empty = not messages
    
    # Prepare message content
    message_content = (
        # Empty state content
        DivCentered(
            UkIcon('message-circle', cls='text-muted-foreground opacity-40 mb-3', height=40, width=40),
            P("Ask questions about your document", cls=TextPresets.muted_lg),
            cls="flex-col",
            id="empty-placeholder"  # Specific ID for the placeholder content
        ) if is_empty else
        # Message list content - when messages exist
        Div(
            *[ChatMessageUI(msg["role"], msg["content"]) for msg in messages],
            cls="space-y-4"
        )
    )
    
    # Return container with appropriate ID based on state
    return Div(
        message_content,
        id="message-list",  # Single container for both states
        cls=f"h-full {'' if is_empty else 'space-y-4 pb-4'}"
    )
    
def create_chat_input():
    """Creates an enhanced chat input that handles state transitions efficiently"""
    return Card(
        Form(
            DivHStacked(
                TextArea(
                    id="message", 
                    placeholder="Ask about your document...", 
                    autofocus=True,
                    hx_on_keydown="""if((event.ctrlKey || event.metaKey || event.shiftKey) && event.key === 'Enter') 
                    { event.preventDefault(); this.closest('form').requestSubmit(); }""",
                    cls="rounded-md resize-none focus:ring-2 focus:ring-primary border-none shadow-inner min-h-[60px] w-full p-3",
                ),
                DivLAligned(
                    Loading(
                        htmx_indicator=True, 
                        type=LoadingT.spinner, 
                        cls="ml-2", 
                        id="detection-loading"
                    ),
                    Button(
                        DivLAligned(
                            UkIcon('send', height=18, width=18, cls="mr-1"),
                            "Send"
                        ), 
                        id="send-button",
                        type="submit", 
                        cls=(ButtonT.primary, "rounded-md", "h-10"),
                        uk_tooltip="Ctrl+Enter to send",
                        # Prevent double submissions
                        hx_disable="true"
                    ),
                    cls="space-x-1 ml-2"
                ),
                cls="items-end w-full"
            ),
            hx_post="/send",
            hx_target="#message-list",  # Target only the message list
            hx_swap="innerHTML",  # Append to end of list
            id="chat-form",
            cls="mb-0 w-full"
        ),
        cls="mt-auto bg-background border-t-0 rounded-b-none shadow-lg sticky bottom-0 w-full",
        body_cls="p-3"
    )

def UploadSection() -> FT:
    """
    Generate a streamlined upload section UI component with improved behavior.
    
    Features:
    - Clean single-purpose interface
    - Optimized spacing and alignment
    - Clear visual cues for drag and drop
    - Properly hidden file input
    - Well-positioned progress indicator
    
    Returns:
        FastHTML FT component for the upload section
    """
    return Card(
        # The upload zone with drag and drop support
        Div(
            DivCentered(
                UkIcon('upload', cls='text-primary mb-2', height=32, width=32),
                H4('Upload Files', cls='mb-1'),
                P('Click or drag here to upload PDFs and photos', 
                cls=TextPresets.muted_sm + ' text-center max-w-xs px-3'),
                id="file-upload-section",
                cls='py-5'
            ),
            
            # Progress bar container - separate div for better positioning
            Div(
                Progress(
                    value='0',
                    max='100',
                    id='upload-progress',
                ),
                P(id='upload-status', cls=TextPresets.muted_sm + ' text-center mt-2'),
                cls='px-6 pb-6 pt-2 hidden',
                id='progress-container'
            ),
            
            # Hidden file input that will be triggered by the click
            Input(
                type='file',
                name='file',
                id='file-input',
                multiple=True,
                accept="image/*,.pdf,application/pdf",
                cls='hidden absolute'  # Using absolute positioning helps ensure it stays hidden
            ),
            
            # Improved script handling visibility states
            Script(src='/static/upload.js'),
            id='dropzone',
            cls='border-2 border-200 border-dashed rounded-md cursor-pointer transition-colors duration-200 hover:border-primary hover:bg-primary/5 relative overflow-hidden',
            # Remove trailing slashes from endpoints - this is critical to prevent mixed content issues on Railway
            data_files_endpoint='/files',
            hx_get='/files',
            hx_target='#file-list',
            hx_swap="innerHTML",
            hx_trigger='uploaded',
            # Add debugging attributes 
            hx_indicator='#file-list-loading',
            hx_ext='json-enc',
            # Add script to include auth headers in uploads
            data_include_auth="true"
        ),       
        cls='mb-3'
    )


def FileItem(file: FileModel) -> FT:
    """
    Generate a compact yet elegant UI component for a single file.
    
    Designed to work within constrained width (1/5 of screen width).
    
    Args:
        file: The file metadata to display
        
    Returns:
        A compact, well-styled file item component
    """
    # Determine file icon based on extension
    extension = file.name.split('.')[-1].lower() if '.' in file.name else ''
    icon_map = {
        'pdf': 'file-text', 'doc': 'file-text', 'txt': 'file-text',
        'xls': 'file-spreadsheet', 'xlsx': 'file-spreadsheet',
        'jpg': 'image', 'png': 'image', 'gif': 'image',
        'mp4': 'video', 'zip': 'archive'
    }
    icon = icon_map.get(extension, 'file')
    
    # Truncate filename if too long (prevent overflow)
    display_name = file.name
    if len(display_name) > 18:
        display_name = display_name[:15] + '...'
    
    return Div(
        # First row: Filename and icon
        DivLAligned(
            UkIcon(icon, cls='text-primary flex-shrink-0 mr-2', height=16, width=16),
            P(display_name, cls=TextT.medium + ' truncate', title=file.name),
            cls='mb-1'
        ),
        
        # Second row: File metadata
        DivLAligned(
            P(file.upload_time_formatted, cls=TextPresets.muted_sm),
            P("•", cls=TextPresets.muted_sm + ' mx-1'),
            P(file.size_formatted, cls=TextPresets.muted_sm),
            cls='text-xs'
        ),
        
        # Third row: Action buttons
        DivFullySpaced(
            DivLAligned(
                Button(
                    UkIcon('trash-2', height=14, width=14), 
                    cls=ButtonT.ghost + ' text-xs px-2 py-1 h-7 text-default border rounded-md',
                    hx_delete=f'/files/{file.id}',
                    hx_confirm=f'Are you sure you want to delete {file.name}?',
                    hx_target='#file-list'
                ),
                 cls='mt-2 space-x-1'
            ),
            DivRAligned(
                Button(
                    UkIcon('download', height=14, width=14), 
                    cls=ButtonT.secondary + ' text-xs px-2 py-1 h-7 border rounded-md',
                    hx_get=f'/files/{file.id}/download',
                    hx_target='_blank'
                ),
                Button(
                    'Interact', 
                    cls=ButtonT.primary + ' text-md px-2 py-1 h-7 border rounded-md' + (' text-default' if file.is_viewable else ' text-muted'),
                    hx_get=f'/files/interact/{file.id}',
                    hx_target='#file-viewer',
                    hx_swap="innerHTML",
                    disabled=not file.is_viewable,
                    # onclick="switchTab(1); setTimeout(function() { resetLayout(); }, 100);",
                ),
                cls="mt-2 space-x-2"
            ),
        ),
        
        id=f'file-{file.id}',
        cls='file-item p-3 hover:bg-secondary border border-slate-200 rounded-md mb-2',
    )

def FileListSection(auth, request=None) -> FT:
    """
    Generate a refined file list section that fits within constrained space.
    
    Features:
    - Compact but elegant design
    - Proper height constraints and overflow handling
    - Responsive to container width (1/5 of screen)
    
    Returns:
        A well-structured file list component
    """
    # Get the user object from request scope
    user = request.scope.get('user') if request else None
    if not user and auth:
        # For backward compatibility, create a simple user object with the auth value
        user = {'user_id': auth}
    
    # Query files ordered by most recent first
    all_files = get_user_files(user) if user is not None else []

    if not all_files:
        file_items = DivCentered(
            UkIcon('file-x', cls='text-muted-foreground opacity-50 mb-2', height=32, width=32),
            P("No files uploaded yet", cls=TextPresets.muted_sm),
            cls='py-8'
        )
    else:
        file_items = Div(
            *[FileItem(file) for file in all_files]
        )
    
    # Build the auth data for HTMX headers
    auth_value = auth if isinstance(auth, str) else None
    if user and isinstance(user, dict) and 'user_id' in user:
        auth_value = user['user_id']
    
    return Card(
        # File list with proper overflow handling
        Div(
            # Add a loading indicator for HTMX requests
            Loading(
                type=LoadingT.spinner,
                cls="mx-auto my-4 hidden",
                id="file-list-loading"
            ),
            
            file_items,
            id='file-list',
            cls='space-y-2'
        ),

        id='file-list-container',
        cls='overflow-y-auto max-h-[calc(100vh-250px)] w-full',

        # Header with refresh button
        header=CardHeader(
            DivFullySpaced(
                H3('Files', cls='text-2xl font-bold'),
                Button(
                    UkIcon('refresh-cw', cls='mr-1', height=16, width=16), 
                    P('Refresh', cls="text-md"), 
                    cls=ButtonT.ghost + ' rounded-md border',
                    # Remove trailing slash to prevent mixed content issues on Railway
                    hx_get='/files', 
                    hx_target='#file-list',
                    hx_swap="innerHTML",
                    hx_indicator='#file-list-loading',
                    # Add auth header to ensure authentication is passed
                    hx_headers=json.dumps({"X-Auth": auth_value}) if auth_value else None,
                ),
                cls='mt-1'
            ),
            # P(f'{len(all_files)} {"files" if all_files and len(all_files) > 1 else "file"}', cls=TextPresets.muted_sm) if all_files else "No files found",
            DividerLine(),
            cls='py-1'
        ),
    )

def ViewerToolbar(file_id: str = None) -> FT:
    """Generate a unified viewer toolbar component."""
    # Get file metadata if a file_id is provided
    file_meta = get_file(file_id) if file_id else None
    file_type = "image" if file_meta and file_meta.is_image else "pdf" if file_meta and file_meta.is_pdf else "unknown"

    # Main toolbar content
    toolbar_main = DivFullySpaced(
        H3(file_meta.name if file_meta else 'File Viewer', id='viewer-title'),

        DivHStacked(
            # Loading indicator
            Loading(
                htmx_indicator=True, 
                type=LoadingT.spinner, 
                cls="ml-2", 
                id="detection-loading"
            ),

            # Add custom annotation button
            Button(
                DivHStacked(
                    UkIcon('pencil', width=20, height=20),
                    P("Annotate"),
                ), 
                cls=ButtonT.default + ' rounded-md', 
                id='create-annotation-btn',
                disabled=not file_meta,
                title="Create Custom Annotation",
                onclick="createAnnotation()"
            ),
            cls="items-center",
        ),
        cls="w-full px-4 py-2 items-center",
    )
    
    # Create unified toolbar content
    toolbar_content = DivHStacked(
        Button(UkIcon('zoom-in'), cls=ButtonT.default + ' rounded-md', id='zoom-in',
               disabled=not file_meta,
               # Use unified document transformer via global API
               onclick="window.currentDocumentTransformer?.zoomIn()"
        ),

        Button(UkIcon('zoom-out'), cls=ButtonT.default + ' rounded-md', id='zoom-out',
               disabled=not file_meta,
               onclick="window.currentDocumentTransformer?.zoomOut()"
        ),

        Button(UkIcon('rotate-cw'), cls=ButtonT.default + ' rounded-md', id='rotate',
                disabled=not file_meta,
                onclick="window.currentDocumentTransformer?.rotate()"
        ),

        Button(UkIcon('maximize'), cls=ButtonT.default + ' rounded-md', id='fit-to-width',
                disabled=not file_meta,
                onclick="window.currentDocumentTransformer?.fitToWidth()"
        ),

        Button(UkIcon('download'), cls=ButtonT.default, id='download',
                disabled=not file_meta,
                hx_get=f'/files/{file_id}/download' if file_id else None,
                hx_target='_blank'
        ),

        # Add a divider between function groups
        Div(cls="w-px h-8 bg-muted mx-1"),

        Button(UkIcon('trash-2', width=20, height=20), cls=ButtonT.default + ' text-error rounded-md', id='delete',
                style="border-color: red",
                disabled=not file_meta,
                hx_delete=f'/files/{file_id}' if file_id else None,
                hx_confirm='Are you sure you want to delete this file?',
                hx_target='body',
                hx_push_url='/',
                hx_trigger='click'
        ),
        cls='z-100 items-center overflow-x-auto md:gap-1 md:p-1'
    )
    
    return NavBar(
        toolbar_content,
        brand=toolbar_main,
        cls="bg-secondary shadow-lg",
    )

def ViewerContent(file_id: str = None):
    """Simplified ViewerContent function with continuous scrolling only for PDF viewing."""
    # If no file is selected, show a placeholder
    if not file_id:
        res = (
            Div(
                P("Select a file to view", cls="text-center text-muted-foreground"),
            )
        )
        return CardBody(*res, id="viewer-content")
    
    # Get file metadata
    file_meta = get_file(file_id)
    if file_meta is None:
        res = (
            Div(
                P("File not found", cls="text-center text-error"),
            )
        )
        return CardBody(*res, id="viewer-content")
    

    
    # Handle different file types
    if file_meta.is_image:

        # Get the file content
        content, success = get_file_content(file_meta)
        if not success:
            return P("Error retrieving file content", cls="text-center text-error")
        
        # Encode the content as Base64
        encoded_content = base64.b64encode(content).decode('utf-8')
        
        # Get the MIME type from the metadata
        mime_type = file_meta.type or 'application/octet-stream' # Fallback MIME type

        # Construct the Data URL
        data_url = f"data:{mime_type};base64,{encoded_content}"

        # For images, create a similar structure to the PDF viewer
        res = (
            # Create a wrapper that will contain both the image viewer and annotations
            Div(
                # Simple scrollable container with relative positioning
                Div(
                    # Create a wrapper div for the image with absolute positioning
                    Div(
                        # The image element
                        Img(
                            src=f'{data_url}',
                            alt=file_meta.name,
                            id='viewer-image',
                            cls='transform-origin-top-left max-w-full h-auto',
                            # Add data attributes for the annotation manager
                            data_file_id=file_id,
                            data_natural_width=str(getattr(file_meta, 'width', 0) or 0),
                            data_natural_height=str(getattr(file_meta, 'height', 0) or 0),
                        ),
                        
                        id='image-container',
                        cls='image-with-annotations absolute top-0 left-0 p-4',
                        # Add data attribute to image container
                        data_file_id=file_id,
                        data_file_type="image",
                    ),
                    
                    id='viewer-scroll-container',
                    cls='relative h-[calc(100vh-200px)] overflow-auto',
                    data_file_id=file_id,
                    data_file_type="image",
                ),
            ),
        )

    elif file_meta.is_pdf:
        # For PDFs, we use PDF.js structure with our annotation integration
        res = (
            # Create a wrapper that will contain both the PDF viewer and annotations
            Div(
                # The PDF.js container (required ID for PDF.js)
                Div(
                    # Create a unique container to prevent duplicate rendering
                    Div(
                        id="pdf-renderer-container",
                        cls="relative",
                    ),
                    id="pdf-main-container",
                    cls="relative h-[calc(100vh-200px)] overflow-auto",
                    data_file_id=file_id,
                    data_file_type="pdf",
                    data_timestamp=str(int(time.time())),
                    
                ),
                
                
                # Loading indicator for PDF
                Div(
                    DivCentered(
                        Progress(cls="w-64"),
                        P("Loading PDF...", cls=TextPresets.muted_sm + " mt-2"),
                        cls="py-4"
                    ),
                    id="pdf-loader",
                    cls="absolute inset-0 flex items-center justify-center bg-black/10 z-40"
                ),
                
                # Initialize annotation system when container is loaded
                # Use event handler instead of inline script
                # Script(f"document.addEventListener('DOMContentLoaded', function() {{ initializeAnnotationSystem({{fileId: '{file_id}', fileType: 'pdf'}}); }});"),
                
                cls="relative h-[calc(100vh-200px)]"
            ),
        )
    else:
        # For unsupported file types
        res = (
            Div(
                P(f"Cannot display this file type: {file_meta.type}",
                  cls="text-center text-warning"),
                P("Download the file to view it.",
                  cls="text-center text-muted-foreground mt-2"),
                cls='flex flex-col items-center justify-center h-[calc(100vh-200px)]'
            ),
        )

    return CardBody(*res, id="viewer-content")

def FileViewerSection(file_id=None):
    """File viewer section that can display various file types."""
    return Div(
        ViewerToolbar(file_id),
        ViewerContent(file_id),
        id='file-viewer',
        cls='flex-1 overflow-hidden rounded-lg h-full',
    )


### ROUTES

@rt('/files')
def get(auth=None, request=None):
    """Return just the file list content for HTMX refreshes"""

    # Check for auth in HTMX headers first (for refresh requests)
    if request and request.headers.get('X-Auth'):
        htmx_auth = request.headers.get('X-Auth')
        if htmx_auth and not auth:
            auth = htmx_auth

    # if not auth:
    #     print(f"❌ Authentication missing for file list")
    #     return Div(
    #         P("Not authorized to access files", cls="text-center text-error"),
    #         id="error",
    #     )
    
    # Get the user object from request scope
    user = request.scope.get('user') if request else None
    user = "cck"
    
    # If no user in scope but we have auth, create a simple user object
    if not user and auth:
        user = {'user_id': auth}
    
    if not user:
        print(f"❌ User object missing from request scope")
        return Div(
            P("User data not found", cls="text-center text-error"),
            id="error",
        )
    
    all_files = get_user_files(user)
    
    if not all_files:
        return DivCentered(
            UkIcon('file-x', cls='text-muted-foreground opacity-50 mb-2', height=32, width=32),
            P("No files uploaded yet", cls=TextPresets.muted_sm),
            cls='py-8'
        )
    else:
        return Div(*[FileItem(file) for file in all_files], cls='space-y-2')

@rt('/files/upload')
async def post(auth=None, file: List[UploadFile] = None, request=None):
    """
    Route handler for file uploads.
    
    This handler supports both single and multiple file uploads.
    It processes the files, stores them in the database or on disk based on size,
    and returns the updated file list items.
    
    Args:
        auth: The auth parameter which now contains the display name
        file: The uploaded file(s)
        request: The request object to access user data
        
    Returns:
        HTML components for the uploaded files
    """
    # Check for auth in X-Auth header (for refresh requests)
    if request and request.headers.get('X-Auth'):
        htmx_auth = request.headers.get('X-Auth')
        if htmx_auth and not auth:
            auth = htmx_auth

    # FOR AUTH
    auth = "cck"
    
    # Make sure we have files
    if not file:
        return P("No files uploaded", cls="text-center text-error")
    
    # Get the user ID from the request scope if available, otherwise fall back to auth
    user_id = None
    if request and request.scope.get('user') and request.scope['user'].get('user_id'):
        user_id = request.scope['user'].get('user_id')
    elif request and request.scope.get('user') and request.scope['user'].get('id'):
        user_id = request.scope['user'].get('id')
    else:
        # Fallback to auth which might be the user ID in older code
        user_id = auth
    
    # Process each file
    responses = []
    for f in file:
        # Generate a unique ID for the file
        file_id = generate_file_id()
        
        # Read the file content
        content = await f.read()
        
        # Get or guess the content type
        content_type = f.content_type or guess_mime_type(f.filename)
        
        # Only allow images and PDFs
        if not (content_type.startswith('image/') or content_type == 'application/pdf'):
            continue
        
        # Create basic metadata
        file_data = {
            'id': file_id,
            'name': f.filename,
            'size': len(content),
            'type': content_type,
            'upload_time': time.time(),
            'data': None,
            'path': None,
            'username': user_id,  # Use the user ID, not display name
        }
        
        # Determine storage strategy based on file size
        if len(content) < MAX_DB_SIZE:
            # Small file - store directly in the database
            file_data['data'] = content
        else:
            # Large file - store on disk and reference path in database
            file_path = str(UPLOAD_DIR / file_id)
            Path(file_path).write_bytes(content)
            file_data['path'] = file_path
        
        # Insert into database
        try:
            # Use FastLite's insert method
            file_meta = files.insert(file_data)
            
            # Add to responses
            responses.append(FileItem(file_meta))
        except Exception as e:
            # Log the error for debugging
            print(f"Error inserting file into database: {e}")

    
    # Return the file item components
    # return responses
    return responses

chat = AgentRunner(
    profile=agent_profile,
    use_toolloop=True,
)

# summarizer = AgentRunner(
#     profile=summarizer_profile,
#     use_toolloop=True,
# )

@rt('/send', methods=['POST'])
def send_message(message: str, auth=None, session=None):
    if not message.strip():
        return Div()
    
    auth = "cck"

    # manually create a chat here
    chat_id = generate_file_id()
    session['chat_id'] = chat_id

    if 'auth' not in session:
        session['auth'] = auth
    if 'chat_id' not in session:
        chat_id = generate_file_id()
        session['chat_id'] = chat_id

    else:
        chat_id = session['chat_id']
        chat.session_id = chat_id
    
    try:
        response = chat.run_turn(user_input=message)
        
        # add the user message to the chat
        inp = ChatMessage(
            chat_id=chat_id,
            role="user",
            content=message,
            created_at=time.time(),
        )

        res = ChatMessage(
            chat_id=chat_id,
            role="assistant",
            content=response,
            created_at=time.time(),
        )

        add_message(inp)
        add_message(res)

        user_msg = ChatMessageUI(inp.role, inp.content)
        ai_msg = ChatMessageUI(res.role, res.content)

        # Get all messages for this chat
        all_messages = get_chat_messages(chat_id)
        
        # Create the updated message list content
        updated_messages = Div(
            *[ChatMessageUI(msg.role, msg.content) for msg in all_messages],
            cls="space-y-4",
            id="message-list-content"
        )
        
        # Add scroll script
        scroll_script = Script("""
            setTimeout(function() {
                const container = document.getElementById('chat-container');
                container.scrollTop = container.scrollHeight;
            }, 100);
        """)
        
        # Return the updated message list
        return Div(
            updated_messages,
            scroll_script,
            id="message-list",  # Match the target ID
            cls="space-y-4 pb-4"
        )
        
    
    except Exception as e:
        print(traceback.format_exc())
        return Alert(f"Error: {str(e)}", cls=AlertT.error)

@rt('/files/interact/{file_id}')
def get(file_id: str):
    """
    Route handler for viewing a file.
    
    Returns just the ViewerContent, not the entire FileViewerSection
    """
    # Find the file metadata
    file_meta = get_file(file_id)
    if not file_meta:
        return Div(
            P("File not found", cls="text-center text-error"),
            cls='flex h-[calc(100vh-200px)]'
        )
    return FileViewerSection(file_id)

@rt('/files/load/{file_id}')
def get(file_id: str):
    """
    Route handler for serving files.
    
    This handler serves the file content for download or direct viewing.
    It retrieves the file from either the database or disk based on where it's stored.
    
    Args:
        file_id: The ID of the file to serve
        
    Returns:
        The file content as a response
    """
    # Find the file metadata
    file_meta = get_file(file_id)
    if not file_meta:
        return P("File not found", cls="text-center text-error")
    
    # Get the file content
    content, success = get_file_content(file_meta)
    if not success:
        return P("Error retrieving file content", cls="text-center text-error")
    
    # Encode the content as Base64
    encoded_content = base64.b64encode(content).decode('utf-8')
    
    # Get the MIME type from the metadata
    mime_type = file_meta.type or 'application/octet-stream' # Fallback MIME type

    # Construct the Data URL
    data_url = f"data:{mime_type};base64,{encoded_content}"
    # Serve the file
    # Instead of using FileResponse which requires a path, we create a Response with the content
    if file_meta.is_image:
        Img(src=data_url, alt=file_meta.name, cls="max-w-full h-auto")
    else:
            # Serve the file
        # Instead of using FileResponse which requires a path, we create a Response with the content
        return Response(
            content=content,
            media_type=file_meta.type,
            headers={
                'Content-Disposition': f'inline; filename="{file_meta.name}"'
            }
        )
    
@rt('/')
def home(auth=None, request=None, sess=None):
    """
    Creates the main page for the Intelligent PDF agent. 6tdf
    """
    auth = "cck"
    return Title(app_name), Div(
        Div(get_navbar(app_name=app_name), id="navbar"),
        Grid(
            Div(
                UploadSection(),
                FileListSection(auth, request),
                cls='col-span-1 tab-panel block md:block',
            ),
            Div(
                FileViewerSection(),
                cls='col-span-3 tab-panel hidden md:block',
            ),
            Div(
                # 1. Proper header with enhanced visual presence
                Div(
                    H3("Interactions", cls="text-2xl font-bold"), 
                    cls="p-3 border-b bg-secondary sticky top-0 z-20"
                ),
                
                # 2. Flexbox layout for proper space allocation
                Div(
                    # 3. Messages container with explicit height calculation
                    Div(
                        create_chat_messages_ui([]), 
                        id="chat-container", 
                        cls="overflow-y-auto p-3 h-[calc(100vh-210px)]"
                    ),
                    
                    # 4. Input area positioned at bottom
                    create_chat_input(),
                    
                    cls="flex flex-col h-[calc(100vh-60px)]"
                ),
                cls='col-span-1 tab-panel hidden md:block mx-1 flex flex-col border shadow-md rounded-md z-10',
            ),
            # Grid configuration
            cols_xl=5,
            cols_lg=5,
            cols_md=1,
            cols_sm=1,
            # gap=4,
            cls="h-screen",
        ),
    )


serve(
    reload=True,
)
