import uuid
import time
import mimetypes
import asyncio
import json
from io import BytesIO
from pathlib import Path
from fastcore.xtras import *
from fasthtml.common import *
from monsterui.all import * 
from database.db import *
import traceback
from docling.datamodel.base_models import DocumentStream

# manually hook in the path for now
import sys
sys.path.append("/Users/cck/projects/cck-agents/")

ARTIFACTS_DIR = Path("/Users/cck/projects/cck-agents/artifacts")

### AGENT 
from dotenv import load_dotenv
load_dotenv()

# Attempt to import necessary components
# from profiles.agents.example_agent.agent import profile as agent_profile
from profiles.agents.simple_pdf_rag_agent.agent import profile as agent_profile
# from profiles.agents.document_summarizer.agent import profile as summarizer_profile
# from framework.agent_runner import AgentRunner
from framework.gaspard_runner import GaspardRunner

chat = GaspardRunner(
    profile=agent_profile,
    use_toolloop=True,
)

# summarizer = AgentRunner(
#     profile=summarizer_profile,
#     use_toolloop=True,
# )

### /AGENT

### EMBEDDINGS
from framework.embeddings import embed_docling_json, RAGEmbeds
from framework.documents import parse_document_bytes, convert

### /EMBEDDINGS
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


# sse to emit transformed images
sse_script = Script(src="https://unpkg.com/htmx-ext-sse@2.2.1/sse.js")

hdrs = [
    theme_headers, 
    full_screen_style, 
    favicon_headers,
    *pdf_scripts,
    sse_script,
]

# create the app
app_name = os.getenv("APP_NAME", "InfraRead 2.0")

app, rt = fast_app(
    hdrs=hdrs,
)

# queue for user requests
msg_queue = asyncio.Queue()

# shutdown event
shutdown_event = signal_shutdown()

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
        'infraai': {'bg': 'bg-gray-200', 'text': 'text-gray-800'}
    }
    if role.lower() == 'assistant':
        role = 'InfraAI'
    style = colors.get(role.lower(), colors['system'])
    
    align_cls = 'justify-end' if role.lower() == 'user' else 'justify-start'
    
    return Div(cls=f'flex {align_cls} mb-4')(
        Div(cls=f'{style["bg"]} {style["text"]} rounded-2xl p-4 max-w-[80%]')(
            Strong(role, cls='text-sm font-semibold tracking-wide'),
            Div(content, cls='mt-2')
        )
    )

def create_chat_messages_ui(file_id: str = None, chat_id: str = None):
    """Creates a structured chat messages container with proper empty state handling"""
    
    # Determine if we're in empty state or have messages
    messages = get_messages(file_id, chat_id)
    is_empty = not messages
    
    
    if is_empty:
        # For empty state, create a placeholder that will be removed by the "empty" event
        contents = [
            DivCentered(
                UkIcon('message-circle', cls='text-muted-foreground opacity-40 mb-3', height=40, width=40),
                P("Interact with your document", cls=TextPresets.muted_lg),
                cls="flex-col",
                id="empty-placeholder",
                sse_swap="empty",  # This will receive the empty event
                hx_swap="outerHTML",
            ),
            # Auto-scroll script
            Script("""
                setTimeout(function() {
                    const container = document.getElementById('chat-container');
                    container.scrollTop = container.scrollHeight;
                }, 100);
            """),
            # Add an empty message container that will receive new messages
            Div(
                id="messages-container",
                sse_swap="message",  # This will receive message events
                hx_swap="beforeend",
                cls="h-full space-y-4",
            ),
        ]
    else:
        # If we already have messages, just create a container with existing messages
        contents = Div(
                # Auto-scroll script
                Script("""
                    setTimeout(function() {
                        const container = document.getElementById('chat-container');
                        container.scrollTop = container.scrollHeight;
                    }, 100);
                """),
                *[ChatMessageUI(msg.role, msg.content) for msg in messages],
                id="messages-container",
                sse_swap="message",  # This will receive message events
                hx_swap="beforeend",
                cls="h-full space-y-4",
            )
    
    # Create the container that will hold all messages
    container = Div(
        *contents,
        id="message-list",  # Main container ID
        hx_ext="sse",
        sse_connect="/messages",
        cls=f"{'' if is_empty else 'space-y-4 pb-4'}"
    )
    return container

    
def create_chat_input(file_id: str = None):
    """Creates an enhanced chat input that handles state transitions efficiently"""
    return Card(
        Form(
            DivHStacked(
                Input(
                    type="hidden",
                    name="file_id",
                    id="file-id",
                    value=file_id,
                ),
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
                        # htmx_indicator=True, 
                        type=LoadingT.spinner, 
                        cls="ml-2", 
                        id="message-loading",
                        style="display: none;",  # Initially hidden
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
            hx_swap="none",  # Append to end of list
            hx_indicator="#message-loading",
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
            hx_trigger='uploaded from:body',
            hx_swap_oob='true',
            # # Add debugging attributes 
            hx_indicator='#file-list-loading',
            # hx_ext='json-enc',
            # Add script to include auth headers in uploads
            data_include_auth="true"
        ),       
        cls='mb-3'
    )


def FileItem(file: FileModel) -> FT:
    """
    Generate an elegant card-based UI component for a single file.
    
    Redesigned to better utilize space and emphasize primary actions.
    
    Args:
        file: The file metadata to display
        
    Returns:
        A well-styled file item card component
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
    
    # Add processing indicator
    is_processing = getattr(file, 'status', None) == 'processing'
    
    # Create status badge similar to Ticket example's StatusBadge
    status_badge = None
    if is_processing:
        status_badge = Alert(
            DivLAligned(UkIcon('loader-2', cls='animate-spin mr-1'), "Processing..."),
            cls=(AlertT.warning, "shadow-sm", "py-1", "px-2", "w-auto")
        )
    
    return Card(
        # Card body with file details
        Div(
            # File metadata row - inspired by TeamMembers card style (lines 132-139)
            DivFullySpaced(
                DivLAligned(
                    UkIcon('calendar', height=14, width=14, cls='text-muted-foreground'),
                    P(file.upload_time_formatted, cls=TextPresets.muted_sm),
                    P("•", cls=TextPresets.muted_sm + ' mx-1'),
                    UkIcon('hard-drive', height=14, width=14, cls='text-muted-foreground mr-1'),
                    P(file.size_formatted, cls=TextPresets.muted_sm),
                    cls='text-xs'
                ),
                # Processing status on right - similar to StatusBadge in Ticket example
                status_badge if is_processing else None,
            ),
            
            # Clear separation like ShareDocument card line 153
            DividerLine(),
            
            # Action buttons - similar to footer styling in CookieSettings card
            DivFullySpaced(
                Button(
                    UkIcon('trash-2', height=16, width=16, cls='mr-1'), 
                    "Delete",
                    cls=ButtonT.ghost + ' text-xs px-3 py-1 h-8 text-default border rounded-md',
                    hx_delete=f'/files/{file.id}' if not is_processing else None,
                    hx_confirm=f'Are you sure you want to delete {file.name}?',
                    hx_target='#file-list',
                    disabled=is_processing,
                ),
                DivLAligned(
                    Button(
                        UkIcon('download', height=16, width=16, cls='mr-1'), 
                        "Download",
                        cls=ButtonT.secondary + ' text-xs px-3 py-1 h-8 border rounded-md',
                        hx_get=f'/files/{file.id}/download' if not is_processing else None,
                        hx_target='_blank',
                        disabled=is_processing,
                    ),
                    cls='mr-2'
                ),
            ),
            cls='p-2'
        ),
        
        # Header with file icon and name - based on Ticket Example's card header pattern
        header=CardHeader(
            DivLAligned(
                UkIcon(icon, cls='text-primary flex-shrink-0 mr-2', height=24, width=24),
                P(file.name, cls=TextT.medium + ' truncate font-semibold', title=file.name),
            ),
            cls='pb-2'
        ),
        
        # Footer with prominent interact button - inspired by CookieSettings card footer (line 136)
        footer=CardFooter(
            Button(
                UkIcon('microscope', height=18, width=18, cls='mr-2' if not is_processing else 'hidden'),
                Loading(cls=LoadingT.spinner + " mr-2") if is_processing else None,
                "Interact", 
                cls=ButtonT.primary + ' w-full py-2',
                hx_get=f'/files/interact/{file.id}' if not is_processing else None,
                hx_target='#main-content',
                hx_swap="innerHTML",
                hx_push_url='true',
                disabled=is_processing,
            ),
            cls='pt-0'
        ),
        
        # Preserve original ID and add hover effect
        id=f'file-{file.id}',
        cls=CardT.hover + ' file-item mb-4',
        
        # Preserve HTMX polling for processing status
        hx_get=f'/files/{file.id}/status' if is_processing else None,
        hx_trigger="every 4s" if is_processing else None,
        hx_swap="outerHTML",
    )
    
@patch
def __ft__(self:FileModel):
    """Render FileModel as FT component for HTMX updates"""
    return FileItem(self)

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

    # Build the auth data for HTMX headers
    auth_value = auth if isinstance(auth, str) else None
    if user and isinstance(user, dict) and 'user_id' in user:
        auth_value = user['user_id']

    file_items = [
        # Loading indicator styled similarly to Ticket Example
        Loading(
            type=LoadingT.spinner,
            cls="mx-auto my-6 hidden",
            id="file-list-loading"
        ),
        
    ]

    # Create file items content with loading indicator
    if not all_files:
        file_items += [
            # Empty state inspired by Card Example empty states
            DivCentered(
                UkIcon('file-x', cls='text-muted-foreground opacity-50 mb-4', height=48, width=48),
                H4("No files uploaded yet", cls='mb-2'),
                P("Upload files to get started with your analysis", cls=TextPresets.muted_sm),
                cls='py-12'
            ),
        ]
    else:
        file_items += [
            # Loading indicator
            Loading(
                type=LoadingT.spinner,
                cls="mx-auto my-6 hidden",
                id="file-list-loading"
            ),
            
            # Grid layout inspired by Card Example (line 190)
            Grid(
                *[FileItem(file) for file in all_files],
                cols_md=1, cols_lg=2, cols_xl=3,
                gap=4
            ),
        ]
    
    file_items = Div(
        *file_items,
        id='file-list',
        cls='space-y-4'
    )
    
    # Preserve the Card container structure from original
    return Card(
        file_items,

        # Preserve all HTMX attributes
        hx_get='/files',
        hx_trigger="fileUploaded from:body",
        hx_swap="innerHTML",
        hx_indicator='#file-list-loading',

        id='file-list-container',
        cls='overflow-y-auto max-h-[calc(100vh-250px)] w-full',

        # Enhanced header inspired by Ticket Example's heading pattern
        header=CardHeader(
            DivFullySpaced(
                H3('Files', cls='text-2xl font-bold'),
                Button(
                    UkIcon('refresh-cw', cls='mr-2', height=16, width=16), 
                    "Refresh", 
                    cls=ButtonT.ghost + ' rounded-md border px-3 py-1',
                    hx_get='/files', 
                    hx_target='#file-list',
                    hx_swap="innerHTML",
                    hx_indicator='#file-list-loading',
                    hx_headers=json.dumps({"X-Auth": auth_value}) if auth_value else None,
                ),
                cls='mt-1'
            ),
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
        Button(
            DivHStacked(
                UkIcon('arrow-big-left', height=20, width=20, cls=""), 
                "Back to Files",
            ),
            cls=ButtonT.secondary + "border-2 border-primary rounded-md px-2",
            hx_get='/',
            hx_target='body',
            hx_push_url='true'
        ),

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
                cls=ButtonT.default + ' border-2 border-primary rounded-md', 
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

def InteractionPanel(file_id, chat_id):
    """
    Enhanced interaction panel with chat and history tabs.
    Preserves existing container structure and height calculations.
    """
    return Div(
        # Header with tabs integration
        DivFullySpaced(
            TabContainer(
                Li(
                    A("Current Chat",
                      href="#current-chat",
                      cls="rounded-md"),
                cls="uk-active"
                ),
                Li(
                    A("Chat History", 
                     href="#chat-history", 
                     cls="rounded-md",
                     hx_get=f"/files/{file_id}/chat-history",
                     hx_target="#chat-history",
                     hx_swap="innerHTML",
                     )
                ),
                uk_switcher="connect: #tab-content",
            ),
            DivRAligned(
                Button("New Chat", 
                    cls=ButtonT.primary + " rounded-md",
                    hx_get=f"/files/{file_id}/new-chat",
                    hx_target="#current-chat",
                    hx_swap="innerHTML",
                ),
            ),
            cls="p-3 border-b bg-secondary sticky top-0 z-20"
        ),
        
        # Content area with switcher container
        Div(
            Div(id="tab-content", cls="uk-switcher h-full")(
                # Tab 1: Current chat - preserve existing structure and IDs
                Div(
                    # Messages container with explicit height calculation
                    Div(
                        create_chat_messages_ui(file_id, chat_id), 
                        id="chat-container", 
                        cls="overflow-y-auto p-3 h-[calc(100vh-200px)]"
                    ),
                    
                    # Input area positioned at bottom - preserved from original
                    create_chat_input(file_id),
                    
                    cls="flex flex-col h-[calc(100vh-60px)]",
                    id="current-chat",
                ),
                
                # Tab 2: Chat history
                Div(
                    DivCentered(
                        UkIcon('history', cls='text-muted-foreground opacity-40 mb-3', height=32, width=32),
                        P("Select a previous conversation", cls=TextPresets.muted_lg),
                        cls="h-[calc(100vh-210px)] flex-col"
                    ),
                    cls="flex flex-col h-[calc(100vh-60px)]",
                    id="chat-history",
                )
            ),
            cls="flex flex-col h-[calc(100vh-60px)]"
        ),
        cls='col-span-1 flex flex-col border shadow-md rounded-md z-10 bg-background',
    )

def FileViewerSection(file_id=None, chat_id=None):
    """File viewer section that can display various file types."""
    return Title(app_name), Div(
        ViewerToolbar(file_id),  # Reused with back button
        Grid(
            Div(ViewerContent(file_id), cls="col-span-3"),
            Div(InteractionPanel(file_id, chat_id), cls="col-span-2"),
            cols_xl=5, cols_lg=5, cols_md=5, cols_sm=1,
            cls="h-[calc(100vh-64px)]"
        )
    )

### ROUTES

@rt('/files')
def get(auth=None, request=None):
    """Return just the file list content for HTMX refreshes"""
    print(f"GOT FILES REQUEST! REQUEST: {request.url, request.headers, request.client}")

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
    
    # Return a structure that includes the loading indicator
    if not all_files:
        return Div(
            # Include loading indicator
            Loading(
                type=LoadingT.spinner,
                cls="mx-auto my-4 hidden",
                id="file-list-loading"
            ),
            
            DivCentered(
                UkIcon('file-x', cls='text-muted-foreground opacity-50 mb-2', height=32, width=32),
                P("No files uploaded yet", cls=TextPresets.muted_sm),
                cls='py-8'
            ),
            cls='space-y-2'
        )
    else:
        return Div(
            # Include loading indicator
            Loading(
                type=LoadingT.spinner,
                cls="mx-auto my-4 hidden",
                id="file-list-loading"
            ),
            
            *[FileItem(file) for file in all_files],
            cls='space-y-2'
        )

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
        
        # set the output path
        output_path = ARTIFACTS_DIR / file_id
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create basic metadata
        file_data = {
            'id': file_id,
            'name': f.filename,
            'size': len(content),
            'type': content_type,
            'upload_time': time.time(),
            'data': content or None,
            'path': str(output_path),
            'username': user_id,  # Use the user ID, not display name
            'status': 'processing',
        }
        
        
        # Insert into database
        try:
            # Use FastLite's insert method
            file_meta = files.insert(file_data)
            # Add to responses
            responses.append(FileItem(file_meta))

            # Start processing asynchronously
            process_task = asyncio.create_task(process_document(content, file_id, output_path, file_meta))
            process_task
      
        except Exception as e:
            # Log the error for debugging
            print(f"Error inserting file into database: {e}")

    
    # Return the file item components
    return responses

async def process_document(content, file_id, output_path, file_meta):
    """Extracts the text and figures from a PDF, then embeds the text for now with late chunking."""
    try:
        # Use loop.run_in_executor for CPU-intensive operations
        loop = asyncio.get_event_loop()
        
        # Create a BytesIO object from the bytes
        buf = BytesIO(content)
        doc = DocumentStream(name="document.pdf", stream=buf)
        
        # Run the CPU-intensive operations in a thread pool
        document = await loop.run_in_executor(
            None,  # Use default executor
            lambda: parse_document_bytes(doc, file_id, output_path)
        )
        print(f"Document parsed for file {file_id}")
        
        # Continue with more CPU-intensive operations in a thread pool
        await loop.run_in_executor(
            None,
            lambda: embed_docling_json(document, output_path / "embeddings")
        )
        print(f"Embeddings saved for file {file_id}")
        
        # Update file status
        file_meta.status = 'ready'
        files.update(file_meta)
    except Exception as e:
        print(f"Error processing document: {traceback.format_exc()}")
        file_meta.status = 'error'
        files.update(file_meta)


@rt('/files/{file_id}/status')
def get(file_id: str):
    file_meta = get_file(file_id)
    if not file_meta:
        return Div(P("File not found", cls="text-error"), id=f'file-{file_id}')
    return FileItem(file_meta)
    

@rt('/send', methods=['POST'])
async def send_message(message: str, file_id: str = None, auth=None, session=None):
    if not message.strip():
        return Div()
    
    auth = "cck"    

    if 'auth' not in session:
        session['auth'] = auth

    if 'chat_id' not in session:
        chat_id = generate_file_id()
        session['chat_id'] = chat_id
    else:
        chat_id = session['chat_id']

    print(f"Sending message: {message}, chat_id: {chat_id}, file_id: {file_id}")
    await msg_queue.put((message, chat_id, file_id))
    print(f"Message sent: {message}, chat_id: {chat_id}, file_id: {file_id}")

# sends the generated images in an sse stream
async def handle_messages():
    """Generates SSE events with chat message responses."""
    first_message = True
    while not shutdown_event.is_set():
        # pop from the queue
        message, chat_id, file_id = await msg_queue.get()

        # create a new client for this interaction if needed
        chat.create_chat(chat_id=chat_id)
        
        try:
            # For first message, send an empty div to replace the placeholder
            if first_message:
                # Empty Div to replace the placeholder
                yield sse_message(Div(), event="empty")
                first_message = False
                # Add a small delay to ensure browser processes this
                await asyncio.sleep(0.1)
            
            # Add the user message to the chat
            inp = ChatMessage(
                chat_id=chat_id,
                file_id=file_id,
                role="User",
                content=message,
                created_at=time.time(),
            )
            add_message(inp)
            user_msg = ChatMessageUI(inp.role, inp.content)
            yield sse_message(user_msg, event="message")

            # Show the loading indicator via JavaScript
            yield sse_message(
                Script("""
                    // Show loading indicator
                    document.getElementById('message-loading').style.display = 'inline-block';
                """), 
                event="message"
            )
            
            # Add a small delay to ensure browser processes this
            await asyncio.sleep(0.1)

            # Get response from the chat system
            response = chat.run_turn(
                user_input=message,
                chat_id=chat_id,
            )

            # Hide loading indicator before sending the response
            yield sse_message(
                Script("""
                    // Hide loading indicator
                    document.getElementById('message-loading').style.display = 'none';
                """), 
                event="message"
            )

            # Add the assistant message to the chat
            res = ChatMessage(
                chat_id=chat_id,
                file_id=file_id,
                role="InfraAI",
                content=response,
                created_at=time.time(),
            )
            add_message(res)
            ai_msg = ChatMessageUI(res.role, res.content)
            yield sse_message(ai_msg, event="message")

        except Exception as e:
            print(f"Error processing message: {traceback.format_exc()}")
            yield sse_message(Alert(f"Error: {str(e)}", cls=AlertT.error), event="message")


# SSE endpoint
@rt("/messages")
async def messages():
    return EventStream(handle_messages())

    
@rt('/files/{file_id}/new-chat')
def get(file_id: str, session=None):
    """
    Route handler for creating a new chat.
    """
    chat_id = generate_file_id()
    session['chat_id'] = chat_id

    # Messages container with explicit height calculation
    return Div(
        create_chat_messages_ui(file_id, chat_id), 
        id="chat-container", 
        cls="overflow-y-auto p-3 h-[calc(100vh-200px)]"
    ), create_chat_input(file_id)

@rt('/files/{file_id}/chat/{chat_id}')
def get(file_id: str, chat_id: str, session=None):
    """
    Route handler for creating a new chat.
    """
    session['chat_id'] = chat_id
    print(f"chat_id: {chat_id}")
    print(f"file_id: {file_id}")

    # Messages container with explicit height calculation
    return (
        # Messages container with explicit height calculation
        Div(
            create_chat_messages_ui(file_id, chat_id), 
            id="chat-container", 
            cls="overflow-y-auto p-3 h-[calc(100vh-200px)]"
        ),
        
        # Input area positioned at bottom - preserved from original
        create_chat_input(file_id),
    )


@rt('/files/{file_id}/chat-history')
def get_chat_history(file_id: str, auth=None, request=None):
    """
    Retrieve and display chat history for a specific file.
    
    This endpoint supports the history tab in the interaction panel, providing
    a list of previous conversations associated with the current document.
    
    Args:
        file_id: The document identifier
        auth: Authentication context
        request: HTTP request object
        
    Returns:
        HTMX-compatible content for the history tab panel
    """
    # Group messages by chat_id to create distinct conversation sessions
    def get_file_chat_sessions(file_id: str):
        """
        Get all distinct chat sessions for a specific file with metadata.
        Returns sessions sorted by most recent first.
        """
        # Get all messages for this file
        all_messages = chats(f"file_id = ?", [file_id], order_by='created_at ASC')
        
        # Group messages by chat_id to identify distinct sessions
        sessions = {}
        for msg in all_messages:
            if msg.chat_id not in sessions:
                sessions[msg.chat_id] = {
                    'id': msg.chat_id,
                    'file_id': file_id,
                    'messages': [],
                    'first_message_time': msg.created_at,
                    'last_message_time': msg.created_at,
                    'message_count': 0
                }
            
            # Add message to session
            sessions[msg.chat_id]['messages'].append(msg)
            sessions[msg.chat_id]['message_count'] += 1
            
            # Track conversation timespan
            sessions[msg.chat_id]['first_message_time'] = min(
                sessions[msg.chat_id]['first_message_time'], 
                msg.created_at
            )
            sessions[msg.chat_id]['last_message_time'] = max(
                sessions[msg.chat_id]['last_message_time'], 
                msg.created_at
            )
        
        # Convert to list and sort by most recent activity
        session_list = list(sessions.values())
        session_list.sort(key=lambda x: x['last_message_time'], reverse=True)
        
        return session_list
    
    # Component for displaying a conversation preview
    def ChatSessionItem(session):
        """Generate a preview card for a chat session with key information."""
        # Format timestamps for display
        from datetime import datetime
        start_time = datetime.fromtimestamp(session['first_message_time'])
        formatted_date = start_time.strftime("%b %d, %Y")
        formatted_time = start_time.strftime("%I:%M %p")
        
        # Extract message previews for display
        user_message = next((msg.content for msg in session['messages'] if msg.role == 'user'), None)
        assistant_message = next((msg.content for msg in session['messages'] if msg.role == 'assistant'), None)
        
        # Truncate previews to reasonable length
        if user_message and len(user_message) > 80:
            user_message = user_message[:77] + "..."
        if assistant_message and len(assistant_message) > 80:
            assistant_message = assistant_message[:77] + "..."
        
        # Create the session preview card
        return Card(
            # Session metadata in header
            CardHeader(
                DivFullySpaced(
                    H4(f"Conversation on {formatted_date}"),
                    P(formatted_time, cls=TextPresets.muted_sm),
                    cls="mb-1"
                ),
                P(f"{session['message_count']} messages", cls=TextPresets.muted_sm),
                cls="pb-2"
            ),
            # Content preview
            Div(
                P(f"Q: {user_message}", cls=TextT.sm + " mb-1"),
                P(f"A: {assistant_message}", cls=TextT.sm + " text-muted"),
                cls="px-4 py-2 bg-secondary rounded-md"
            ),
            # Load conversation action
            Button(
                DivLAligned(UkIcon('message-circle', cls="mr-1"), "View Conversation"),
                cls=ButtonT.primary + " mt-3",
                hx_get=f"/files/{session['file_id']}/chat/{session['id']}",
                hx_target="#current-chat",
                hx_swap="innerHTML",
                # swap the tab back to #current-chat to display the new chat
                # Execute a more comprehensive tab switching sequence
                    # Add onclick handler to switch tabs after HTMX completes
                onclick="""setTimeout(function() { 

                    // manually click on the first tab
                    const firstTab = document.querySelector('ul.uk-tab > li:first-child > a');

                    if (firstTab) {
                        firstTab.click();
                    
                        // Focus the textarea after tab switch animation
                        setTimeout(() => {
                            const textarea = document.querySelector('#current-chat textarea#message');
                            if (textarea) textarea.focus();
                        }, 150);
                    }; 

                    // manually show the first tab
                    UIkit.tab(document.querySelector('[uk-switcher]')).show(0); 
                }, 100);"""
            ),
            cls="mb-3 hover:shadow-md transition-shadow"
        )
    
    # Get all chat sessions for this file
    chat_sessions = get_file_chat_sessions(file_id)
    
    # Handle empty state
    if not chat_sessions:
        return DivCentered(
            UkIcon('history', cls='text-muted-foreground opacity-40 mb-3', height=32, width=32),
            P("No previous conversations found", cls=TextPresets.muted_lg),
            P("Start chatting with your document to create history", cls=TextPresets.muted_sm),
            cls="h-[calc(100vh-210px)] flex-col p-4"
        )
    
    # Create history list with consistent height calculations
    return Div(
        Div(
            *[ChatSessionItem(session) for session in chat_sessions],
            cls="overflow-y-auto p-4 space-y-4"
        ),
        cls="h-[calc(100vh-210px)] overflow-y-auto",
        id="chat-history",
    )


@rt('/files/interact/{file_id}')
def get(file_id: str, session=None):
    """
    Route handler for viewing a file.
    
    Returns just the ViewerContent, not the entire FileViewerSection
    """
    if 'chat_id' in session:
        chat_id = session['chat_id']
    else:
        chat_id = generate_file_id()
        session['chat_id'] = chat_id

    # Find the file metadata
    file_meta = get_file(file_id)

    # load the embeddings for this file
    print(f"Loading embeddings for file {file_id}...")
    RAGEmbeds.set_file_id(file_id)
    RAGEmbeds.load()
    print(f"Embeddings loaded for file {file_id}")

    if not file_meta:
        return Div(
            P("File not found", cls="text-center text-error"),
            cls='flex h-[calc(100vh-200px)]'
        )
    return FileViewerSection(file_id, chat_id)

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
    if 'chat_id' in sess:
        sess.pop('chat_id')

    return Title(app_name), Div(
        Div(get_navbar(app_name=app_name), id="navbar"),
            Div(
                UploadSection(),
                FileListSection(auth, request),
                cls='col-span-1 tab-panel block md:block',
                id='main-content',
            ),    
        cls="h-screen",        
        )


# run the app
serve(
    reload=True,
)
