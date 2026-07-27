import os
import mimetypes
import io
import zipfile
import PyPDF2
import fitz  # PyMuPDF
import uuid
import json
from google.genai import types
from fastapi import Response, Form
from pydantic import BaseModel
from typing import List
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google import genai

# --- Configuration ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6IZOita0-V6iAgoHDIVqgLYrfOXdprS1EkMxtml5po2VA")

if os.environ.get("GEMINI_API_KEY") is None:
    client = genai.Client(api_key=GEMINI_KEY)
else:
    client = genai.Client()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# SYSTEM PROMPT FOR AI APP CONTROL
# ==========================================
APP_CONTROL_PROMPT = """You are an AI assistant built directly into a mobile app called 'PDF Toolkit'. You have the ability to navigate the app and control settings for the user.

You MUST ALWAYS respond with a valid JSON object. Do not wrap it in markdown block quotes (no ```json).

If the user asks a normal question or needs a PDF summary, respond with JSON like this:
{"reply": "Your normal conversational response here."}

HOWEVER, if the user asks you to navigate the app, change a setting, or open a tool, you must also include the 'action' and 'target' fields in the JSON. 

Exact commands you can use:
- To go to the Profile screen: {"reply": "Opening your profile now.", "action": "NAVIGATE", "target": "3"}
- To go to the Search screen: {"reply": "Opening the search tab.", "action": "NAVIGATE", "target": "1"}
- To go to the Home/Dashboard screen: {"reply": "Going to the dashboard.", "action": "NAVIGATE", "target": "0"}
- To turn on/off Dark Mode: {"reply": "Toggling dark mode for you.", "action": "TOGGLE_DARK_MODE"}
- To clear the chat history: {"reply": "Wiping chat history.", "action": "CLEAR_CHAT"}
- To open a specific tool (e.g., 'Merge PDFs', 'PDF to JPG', 'Add Watermark'): {"reply": "Opening tool.", "action": "OPEN_TOOL", "target": "Exact Tool Name"}
"""

@app.get("/")
def read_root():
    return {"message": "PDF Toolkit Backend is running!"}

# ==========================================
# ENDPOINT: AI PDF SUMMARY (Single File)
# ==========================================
@app.post("/api/summarize")
async def summarize_pdf(file: UploadFile = File(...)):
    try:
        text = ""
        pdf_reader = PyPDF2.PdfReader(file.file)
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        
        if not text.strip():
            return {"status": "error", "message": "Could not extract any text from this PDF."}

        prompt = f"Provide a clear, well-structured summary of this document using bullet points:\n\n{text}"
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        return {"status": "success", "result": response.text}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# ENDPOINT: ADD PASSWORD TO PDF (Single File)
# ==========================================
@app.post("/api/lock")
async def lock_pdf(file: UploadFile = File(...), password: str = Form(...)):
    try:
        reader = PyPDF2.PdfReader(file.file)
        writer = PyPDF2.PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
            
        writer.encrypt(password)
        
        memory_file = io.BytesIO()
        writer.write(memory_file)
        memory_file.seek(0)
            
        return StreamingResponse(
            memory_file, 
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="locked_{file.filename}"'}
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# ENDPOINT: PDF TO JPG (Single File -> ZIP output)
# ==========================================
@app.post("/api/tojpg")
async def pdf_to_jpg(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        if len(doc) == 0:
            return {"status": "error", "message": "The uploaded PDF is completely empty."}
            
        memory_zip = io.BytesIO()
        with zipfile.ZipFile(memory_zip, "w") as zf:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("jpg")
                zf.writestr(f"page_{page_num + 1}.jpg", img_bytes)
        
        memory_zip.seek(0)
        
        return StreamingResponse(
            memory_zip, 
            media_type='application/zip',
            headers={'Content-Disposition': f'attachment; filename="converted_{file.filename}.zip"'}
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# NEW ENDPOINT: MERGE PDFs (Multiple Files)
# ==========================================
@app.post("/api/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    """Receives multiple PDFs and combines them into one."""
    try:
        print(f"📑 Merging {len(files)} PDFs...")
        merger = PyPDF2.PdfMerger()
        
        for file in files:
            file_bytes = await file.read()
            merger.append(io.BytesIO(file_bytes))
            
        memory_file = io.BytesIO()
        merger.write(memory_file)
        memory_file.seek(0)
        
        print("✅ Merge successful! Sending back to app...")
        return StreamingResponse(
            memory_file, 
            media_type='application/pdf',
            headers={'Content-Disposition': 'attachment; filename="merged_document.pdf"'}
        )
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return {"status": "error", "message": str(e)}

# ==========================================
# NEW ENDPOINT: JPG TO PDF (Multiple Files)
# ==========================================
@app.post("/api/topdf")
async def jpg_to_pdf(files: List[UploadFile] = File(...)):
    """Receives multiple images and packs them into a single PDF."""
    try:
        print(f"🖼️ Packing {len(files)} images into PDF...")
        doc = fitz.open() # Create a blank PDF document
        
        for file in files:
            img_bytes = await file.read()
            
            # Determine extension based on file name (jpg, png, etc.)
            ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'jpg'
            
            # Open the image with PyMuPDF and convert directly to PDF bytes
            img_doc = fitz.open(stream=img_bytes, filetype=ext)
            pdf_bytes = img_doc.convert_to_pdf()
            img_doc.close()
            
            # Insert the newly converted page into the main document
            temp_pdf = fitz.open("pdf", pdf_bytes)
            doc.insert_pdf(temp_pdf)
            temp_pdf.close()
            
        memory_file = io.BytesIO()
        doc.save(memory_file)
        memory_file.seek(0)
        
        print("✅ Conversion successful! Sending back to app...")
        return StreamingResponse(
            memory_file, 
            media_type='application/pdf',
            headers={'Content-Disposition': 'attachment; filename="converted_images.pdf"'}
        )
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return {"status": "error", "message": str(e)}
    
# ==========================================
# ENDPOINT: REMOVE PASSWORD FROM PDF
# ==========================================
@app.post("/api/unlock")
async def unlock_pdf(file: UploadFile = File(...), password: str = Form(...)):
    """Receives an encrypted PDF and a password, decrypts it, and returns the unlocked file."""
    try:
        print(f"🔓 Decrypting file: {file.filename}")
        
        reader = PyPDF2.PdfReader(file.file)
        
        # 1. Check if the file is actually encrypted
        if not reader.is_encrypted:
            return {"status": "error", "message": "This PDF is already unlocked!"}
            
        # 2. Attempt to decrypt with the provided password
        success = reader.decrypt(password)
        
        # In PyPDF2, decrypt returns 0 if it fails (wrong password)
        if success == 0:
            return {"status": "error", "message": "Incorrect password. Please try again."}
            
        # 3. If successful, copy the decrypted pages to a new writer
        writer = PyPDF2.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
            
        # 4. Save to memory and send back
        memory_file = io.BytesIO()
        writer.write(memory_file)
        memory_file.seek(0)
        
        print("✅ PDF Decrypted successfully! Sending back to app...")
        return StreamingResponse(
            memory_file, 
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="unlocked_{file.filename}"'}
        )
        
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return {"status": "error", "message": str(e)}

class ChatRequest(BaseModel):
    message: str

# ==========================================
# ENDPOINT: AI CHAT (APP CONTROL INTEGRATED)
# ==========================================
@app.post("/api/chat")
async def chat_with_ai(request: ChatRequest):
    try:
        my_api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=my_api_key)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=request.message,
            config=types.GenerateContentConfig(
                system_instruction=APP_CONTROL_PROMPT,
                response_mime_type="application/json",
            )
        )
        
        # Parse the JSON response from Gemini
        ai_data = json.loads(response.text)
        
        # Return the parsed data back to Flutter
        return {
            "status": "success", 
            "reply": ai_data.get("reply", "I am not sure how to respond to that."),
            "action": ai_data.get("action"),
            "target": ai_data.get("target")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# ENDPOINT: AI CHAT (FILE ATTACHED)
# ==========================================
@app.post("/api/chat/file")
async def chat_with_file(file: UploadFile = File(...), message: str = Form("Please summarize this document in detail.")):
    try:
        my_api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=my_api_key)
        
        # 1. Extract text from the uploaded PDF
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = ""
        for page in doc:
            extracted_text += page.get_text()
            
        # 2. Combine the user's prompt with the document text
        full_prompt = f"{message}\n\n--- Document Content ---\n{extracted_text}"
        
        # 3. Send to Gemini forcing JSON response
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=APP_CONTROL_PROMPT,
                response_mime_type="application/json",
            )
        )
        
        ai_data = json.loads(response.text)
        
        return {
            "status": "success", 
            "reply": ai_data.get("reply", "I have processed the document."),
            "action": ai_data.get("action"),
            "target": ai_data.get("target")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 1. PDF METADATA INSPECTOR
# ==========================================
@app.post("/api/metadata")
async def extract_metadata(file: UploadFile = File(...)):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        metadata = doc.metadata
        
        # Format the metadata into a clean readable string
        result_text = "--- PDF Metadata ---\n"
        for key, value in metadata.items():
            if value:  # Only show fields that have data
                result_text += f"{key.capitalize()}: {value}\n"
        
        if result_text == "--- PDF Metadata ---\n":
            result_text = "No metadata found in this document."
            
        return {"status": "success", "result": result_text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 2. DOCUMENT WATERMARKING
# ==========================================
@app.post("/api/watermark")
async def add_watermark(
    file: UploadFile = File(...), 
    password: str = Form("CONFIDENTIAL") 
):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        for page in doc:
            rect = page.rect
            # Adjusted the point to center the text better horizontally
            point = fitz.Point(rect.width * 0.15, rect.height * 0.50)
            page.insert_text(
                point, 
                password, 
                fontsize=60, 
                color=(0.7, 0.7, 0.7) 
                # Removed the rotate=45 parameter to prevent the crash
            )
            
        out_bytes = doc.write()
        return Response(content=out_bytes, media_type="application/pdf")
    except Exception as e:
        return {"status": "error", "message": str(e)}
        
# ==========================================
# 3. AI OPTICAL CHARACTER RECOGNITION (OCR)
# ==========================================
@app.post("/api/imagetotext")
async def image_to_text(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        my_api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=my_api_key)
        
        # 1. Guess the correct MIME type based on the file extension
        mime_type, _ = mimetypes.guess_type(file.filename)
        
        # 2. Provide a safe fallback if it still reads as a generic stream
        if not mime_type or mime_type == "application/octet-stream":
            if file.filename.lower().endswith('.png'):
                mime_type = "image/png"
            else:
                mime_type = "image/jpeg"
        
        # 3. Package the image using the corrected MIME type
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type,
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                image_part,
                "Extract all the text from this image exactly as it appears. Do not add any extra commentary."
            ]
        )
        return {"status": "success", "result": response.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}
