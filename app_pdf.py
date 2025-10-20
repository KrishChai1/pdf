import streamlit as st
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict

# Import Docling components with version compatibility
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
    
    # Try to import optional components
    try:
        from docling.datamodel.base_models import InputFormat
        DOCLING_INPUTFORMAT = True
    except ImportError:
        DOCLING_INPUTFORMAT = False
    
    try:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        DOCLING_PIPELINE = True
    except ImportError:
        DOCLING_PIPELINE = False
    
    try:
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        DOCLING_BACKEND = True
    except ImportError:
        DOCLING_BACKEND = False
        
except ImportError:
    DOCLING_AVAILABLE = False
    DOCLING_INPUTFORMAT = False
    DOCLING_PIPELINE = False
    DOCLING_BACKEND = False

# Fallback PDF extraction
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

@dataclass
class ExtractedField:
    item_number: str
    label: str
    field_type: str = "text"
    is_parent: bool = False
    is_subfield: bool = False
    parent_number: Optional[str] = None
    page_number: int = 1
    coordinates: Optional[Dict] = None
    value: Optional[str] = None
    options: Optional[List[str]] = None

class USCISFormExtractor:
    def __init__(self):
        self.fields = []
        self.field_hierarchy = {}
        self.debug_info = []
        
        # USCIS form patterns for field detection
        self.field_patterns = {
            'name_fields': [
                r'(?:your\s+)?(?:full\s+)?(?:legal\s+)?name',
                r'family\s+name|last\s+name',
                r'given\s+name|first\s+name',
                r'middle\s+name'
            ],
            'address_fields': [
                r'(?:current\s+)?(?:physical\s+)?address',
                r'mailing\s+address',
                r'street\s+(?:number\s+and\s+)?name',
                r'apt\.?\s+ste\.?\s+flr\.?\s+number',
                r'city\s+or\s+town',
                r'state|province',
                r'zip\s+code|postal\s+code',
                r'country'
            ],
            'date_fields': [
                r'date\s+of\s+birth',
                r'date\s+of\s+arrival',
                r'expiration\s+date',
                r'date\s+of\s+entry'
            ],
            'number_fields': [
                r'alien\s+(?:registration\s+)?number',
                r'receipt\s+number',
                r'social\s+security\s+number',
                r'passport\s+number',
                r'uscis\s+(?:online\s+)?account\s+number'
            ],
            'contact_fields': [
                r'(?:daytime\s+)?(?:telephone\s+)?(?:phone\s+)?number',
                r'mobile\s+(?:telephone\s+)?number',
                r'email\s+address'
            ]
        }
        
        # Subfield patterns for automatic splitting
        self.subfield_patterns = {
            'name': ['Family Name (Last Name)', 'Given Name (First Name)', 'Middle Name'],
            'address': ['Street Number and Name', 'Apt. Ste. Flr. Number', 'City or Town', 'State', 'ZIP Code'],
            'mailing_same': ['Same as current physical address'],
            'phone': ['Daytime Telephone Number', 'Mobile Telephone Number']
        }

    def extract_with_docling(self, pdf_file) -> Dict[str, Any]:
        """Extract content using Docling library"""
        if not DOCLING_AVAILABLE:
            return {"error": "Docling not available"}
        
        try:
            import tempfile
            import os
            from pathlib import Path
            
            # Create a temporary file to save the uploaded content
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                # Write the uploaded file content to temporary file
                tmp_file.write(pdf_file.getvalue())
                tmp_file_path = tmp_file.name
            
            try:
                # Try different Docling initialization approaches
                self.debug_info.append("Attempting Docling extraction...")
                
                try:
                    # Method 1: Simple DocumentConverter without OCR (most compatible)
                    converter = DocumentConverter()
                    result = converter.convert(Path(tmp_file_path))
                    self.debug_info.append("✅ Simple DocumentConverter worked")
                    
                except Exception as simple_error:
                    self.debug_info.append(f"Simple converter failed: {str(simple_error)}")
                    
                    # Method 2: Try with minimal pipeline options
                    try:
                        if DOCLING_PIPELINE:
                            pipeline_options = PdfPipelineOptions()
                            # Disable OCR to avoid the warning
                            if hasattr(pipeline_options, 'do_ocr'):
                                pipeline_options.do_ocr = False
                            if hasattr(pipeline_options, 'do_table_structure'):
                                pipeline_options.do_table_structure = False
                            
                            if DOCLING_INPUTFORMAT:
                                converter = DocumentConverter(
                                    format_options={
                                        InputFormat.PDF: pipeline_options,
                                    }
                                )
                            else:
                                converter = DocumentConverter()
                            
                            result = converter.convert(Path(tmp_file_path))
                            self.debug_info.append("✅ Pipeline converter worked")
                        else:
                            raise Exception("Pipeline options not available")
                        
                    except Exception as pipeline_error:
                        self.debug_info.append(f"Pipeline converter failed: {str(pipeline_error)}")
                        
                        # Method 3: Fallback to basic converter
                        try:
                            # Import warnings to suppress OCR warnings
                            import warnings
                            with warnings.catch_warnings():
                                warnings.filterwarnings("ignore", message=".*OCR engine.*")
                                converter = DocumentConverter()
                                result = converter.convert(Path(tmp_file_path))
                                self.debug_info.append("✅ Basic converter with warnings suppressed worked")
                                
                        except Exception as basic_error:
                            self.debug_info.append(f"Basic converter failed: {str(basic_error)}")
                            raise basic_error
                
                # Extract structured content
                content = {
                    "text": "",
                    "markdown": "",
                    "tables": [],
                    "fields": []
                }
                
                # Safely extract text
                try:
                    if hasattr(result.document, 'export_to_text'):
                        content["text"] = result.document.export_to_text()
                        self.debug_info.append("✅ Text extraction successful")
                    else:
                        content["text"] = str(result.document)
                        self.debug_info.append("⚠️ Used fallback text extraction")
                except Exception as e:
                    self.debug_info.append(f"Text extraction failed: {str(e)}")
                    content["text"] = "Text extraction failed"
                
                # Safely extract markdown
                try:
                    if hasattr(result.document, 'export_to_markdown'):
                        content["markdown"] = result.document.export_to_markdown()
                        self.debug_info.append("✅ Markdown extraction successful")
                    else:
                        content["markdown"] = content["text"]
                        self.debug_info.append("⚠️ Used text as markdown fallback")
                except Exception as e:
                    self.debug_info.append(f"Markdown extraction failed: {str(e)}")
                    content["markdown"] = content["text"]
                
                # Safely extract tables (skip if OCR issues)
                try:
                    if hasattr(result.document, 'tables') and result.document.tables:
                        for i, table in enumerate(result.document.tables):
                            try:
                                table_data = {}
                                
                                # Try different table extraction methods
                                if hasattr(table, 'export_to_dataframe'):
                                    df = table.export_to_dataframe()
                                    table_data["data"] = df.to_dict()
                                elif hasattr(table, 'data'):
                                    table_data["data"] = table.data
                                else:
                                    table_data["data"] = {"note": "Table structure detected but data extraction not available"}
                                
                                # Add bounding box if available
                                if hasattr(table, 'bbox'):
                                    table_data["bbox"] = table.bbox
                                
                                content["tables"].append(table_data)
                                self.debug_info.append(f"✅ Extracted table {i+1}")
                                
                            except Exception as table_error:
                                self.debug_info.append(f"Table {i} extraction failed: {str(table_error)}")
                    else:
                        self.debug_info.append("ℹ️ No tables found or tables not accessible")
                        
                except Exception as tables_error:
                    self.debug_info.append(f"Tables extraction failed: {str(tables_error)}")
                
                self.debug_info.append(f"✅ Docling extraction completed. Text length: {len(content['text'])}")
                return content
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_file_path)
                except Exception:
                    pass  # Ignore cleanup errors
            
        except Exception as e:
            error_msg = f"Error extracting with Docling: {str(e)}"
            self.debug_info.append(error_msg)
            return {"error": error_msg}

    def detect_form_type(self, text: str) -> str:
        """Detect USCIS form type from extracted text"""
        form_patterns = {
            'I-485': r'I-485|Application\s+to\s+Register\s+Permanent\s+Residence',
            'I-539': r'I-539|Application\s+to\s+Extend/Change\s+Nonimmigrant\s+Status',
            'I-765': r'I-765|Application\s+for\s+Employment\s+Authorization',
            'I-130': r'I-130|Petition\s+for\s+Alien\s+Relative',
            'I-129': r'I-129|Petition\s+for\s+Nonimmigrant\s+Worker',
            'N-400': r'N-400|Application\s+for\s+Naturalization'
        }
        
        for form_type, pattern in form_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return form_type
        
        return "Unknown"

    def extract_parts_and_fields(self, text: str) -> List[ExtractedField]:
        """Extract form parts and fields with proper numbering"""
        extracted_fields = []
        
        # Split text into lines for processing
        lines = text.split('\n')
        current_part = None
        item_counter = 1
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Detect part headers
            part_match = re.search(r'Part\s+(\d+)\.\s*(.+)', line, re.IGNORECASE)
            if part_match:
                current_part = f"Part {part_match.group(1)}"
                self.debug_info.append(f"Found {current_part}: {part_match.group(2)}")
                continue
            
            # Detect numbered items (1., 2., etc.)
            item_match = re.search(r'^(\d+)\.\s*(.+)', line)
            if item_match:
                item_num = item_match.group(1)
                label = item_match.group(2).strip()
                
                # Check if this should be a parent field with subfields
                if self.should_create_subfields(label):
                    # Create parent field
                    parent_field = ExtractedField(
                        item_number=item_num,
                        label=label,
                        is_parent=True,
                        field_type="parent"
                    )
                    extracted_fields.append(parent_field)
                    
                    # Create subfields
                    subfields = self.create_subfields(item_num, label)
                    extracted_fields.extend(subfields)
                    
                    # Store hierarchy
                    self.field_hierarchy[item_num] = {
                        "label": label,
                        "subfields": [sf.label for sf in subfields]
                    }
                else:
                    # Regular field
                    field = ExtractedField(
                        item_number=item_num,
                        label=label,
                        field_type=self.detect_field_type(label)
                    )
                    extracted_fields.append(field)
                
                item_counter += 1
                self.debug_info.append(f"Extracted item {item_num}: {label}")
        
    def extract_with_fallback(self, pdf_file) -> Dict[str, Any]:
        """Fallback PDF extraction using PyPDF2 or PyMuPDF"""
        try:
            pdf_content = pdf_file.getvalue()
            
            # Try PyMuPDF first (better for complex PDFs)
            if PYMUPDF_AVAILABLE:
                try:
                    doc = fitz.open(stream=pdf_content, filetype="pdf")
                    text = ""
                    for page in doc:
                        text += page.get_text() + "\n"
                    doc.close()
                    
                    return {
                        "text": text,
                        "markdown": text,  # Simple conversion
                        "tables": [],
                        "fields": []
                    }
                except Exception as e:
                    self.debug_info.append(f"PyMuPDF failed: {str(e)}")
            
            # Try PyPDF2 as backup
            if PYPDF2_AVAILABLE:
                try:
                    from io import BytesIO
                    pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    
                    return {
                        "text": text,
                        "markdown": text,
                        "tables": [],
                        "fields": []
                    }
                except Exception as e:
                    self.debug_info.append(f"PyPDF2 failed: {str(e)}")
            
            return {"error": "No PDF extraction library available"}
            
        except Exception as e:
            return {"error": f"Fallback extraction failed: {str(e)}"}

    def extract_pdf_content(self, pdf_file) -> Dict[str, Any]:
        """Main extraction method with fallback options"""
        # Try Docling first (best quality)
        if DOCLING_AVAILABLE:
            self.debug_info.append("Attempting extraction with Docling...")
            result = self.extract_with_docling(pdf_file)
            if "error" not in result:
                return result
            else:
                self.debug_info.append(f"Docling failed: {result['error']}")
        
        # Fallback to other methods
        self.debug_info.append("Falling back to alternative PDF extraction...")
        return self.extract_with_fallback(pdf_file)

    def should_create_subfields(self, label: str) -> bool:
        """Determine if a field should have subfields"""
        label_lower = label.lower()
        
        subfield_triggers = [
            'full legal name',
            'legal name',
            'your name',
            'current physical address',
            'physical address',
            'mailing address',
            'home address',
            'telephone number',
            'phone number'
        ]
        
        return any(trigger in label_lower for trigger in subfield_triggers)

    def create_subfields(self, parent_num: str, parent_label: str) -> List[ExtractedField]:
        """Create subfields based on parent field type"""
        subfields = []
        label_lower = parent_label.lower()
        
        if 'name' in label_lower:
            subfield_labels = self.subfield_patterns['name']
        elif 'address' in label_lower and 'mailing' not in label_lower:
            subfield_labels = self.subfield_patterns['address']
        elif 'mailing' in label_lower:
            subfield_labels = self.subfield_patterns['mailing_same'] + self.subfield_patterns['address']
        elif 'phone' in label_lower or 'telephone' in label_lower:
            subfield_labels = self.subfield_patterns['phone']
        else:
            # Default to 3 subfields
            subfield_labels = ['Field A', 'Field B', 'Field C']
        
        for i, sublabel in enumerate(subfield_labels):
            subfield_num = f"{parent_num}.{chr(97 + i)}"  # 1.a, 1.b, 1.c
            subfield = ExtractedField(
                item_number=subfield_num,
                label=sublabel,
                is_subfield=True,
                parent_number=parent_num,
                field_type=self.detect_field_type(sublabel)
            )
            subfields.append(subfield)
        
        return subfields

    def detect_field_type(self, label: str) -> str:
        """Detect field type based on label"""
        label_lower = label.lower()
        
        if any(pattern in label_lower for pattern in ['date', 'birth', 'expiry']):
            return "date"
        elif any(pattern in label_lower for pattern in ['phone', 'telephone', 'mobile']):
            return "tel"
        elif 'email' in label_lower:
            return "email"
        elif any(pattern in label_lower for pattern in ['number', 'zip', 'code']):
            return "number"
        elif any(pattern in label_lower for pattern in ['yes', 'no', 'check']):
            return "radio"
        else:
            return "text"

def main():
    st.set_page_config(
        page_title="USCIS PDF Extractor with Docling",
        page_icon="📄",
        layout="wide"
    )
    
    st.title("🏛️ USCIS PDF Form Extractor with Docling")
    st.markdown("Extract and analyze USCIS forms with advanced PDF processing")
    
    # Check available libraries
    libs_status = []
    if DOCLING_AVAILABLE:
        docling_features = []
        if DOCLING_PIPELINE:
            docling_features.append("Pipeline")
        if DOCLING_INPUTFORMAT:
            docling_features.append("InputFormat")
        if DOCLING_BACKEND:
            docling_features.append("Backend")
        
        feature_str = f" ({', '.join(docling_features)})" if docling_features else " (basic)"
        libs_status.append(f"✅ Docling (Primary){feature_str}")
    else:
        libs_status.append("❌ Docling (install: pip install docling)")
    
    if PYMUPDF_AVAILABLE:
        libs_status.append("✅ PyMuPDF (Fallback)")
    else:
        libs_status.append("❌ PyMuPDF (install: pip install pymupdf)")
    
    if PYPDF2_AVAILABLE:
        libs_status.append("✅ PyPDF2 (Fallback)")
    else:
        libs_status.append("❌ PyPDF2 (install: pip install PyPDF2)")
    
    with st.expander("📚 Library Status"):
        for status in libs_status:
            st.markdown(status)
    
    if not any([DOCLING_AVAILABLE, PYMUPDF_AVAILABLE, PYPDF2_AVAILABLE]):
        st.error("⚠️ No PDF extraction libraries found. Please install at least one:")
        st.code("pip install docling  # Recommended\n# OR\npip install pymupdf\n# OR\npip install PyPDF2")
        return
    
    # Initialize extractor
    extractor = USCISFormExtractor()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # OCR settings
        enable_ocr = st.checkbox("Enable OCR", value=True, help="Extract text from scanned PDFs")
        extract_tables = st.checkbox("Extract Tables", value=True, help="Detect and extract table structures")
        
        # Debug options
        show_debug = st.checkbox("Show Debug Info", value=False, help="Display extraction debug information")
        show_raw_text = st.checkbox("Show Raw Text", value=False, help="Display extracted raw text")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload USCIS PDF Form",
        type=['pdf'],
        help="Upload any USCIS form (I-485, I-539, I-765, etc.)"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ Uploaded: {uploaded_file.name}")
        
        # Process the PDF
        with st.spinner("🔄 Processing PDF with Docling..."):
            content = extractor.extract_pdf_content(uploaded_file)
        
        if "error" in content:
            st.error(f"❌ Error processing PDF: {content['error']}")
            return
        
        # Detect form type
        form_type = extractor.detect_form_type(content["text"])
        st.info(f"📋 Detected Form Type: **{form_type}**")
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📝 Extracted Fields", "🔍 Debug Info", "📊 Tables", "💾 Export"])
        
        with tab1:
            st.header("Extracted Form Fields")
            
            # Extract fields
            fields = extractor.extract_parts_and_fields(content["text"])
            
            if fields:
                # Display fields in a structured way
                for field in fields:
                    if field.is_parent:
                        st.markdown(f"### 📁 {field.item_number}. {field.label}")
                        st.markdown("*Parent field - contains subfields below*")
                    elif field.is_subfield:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{field.item_number}** {field.label}")
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            value = st.text_input(
                                f"Value for {field.item_number}",
                                key=f"field_{field.item_number}",
                                placeholder=f"Enter {field.label.lower()}"
                            )
                        with col2:
                            st.markdown(f"*Type: {field.field_type}*")
                    else:
                        st.markdown(f"**{field.item_number}.** {field.label}")
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            value = st.text_input(
                                f"Value for {field.item_number}",
                                key=f"field_{field.item_number}",
                                placeholder=f"Enter {field.label.lower()}"
                            )
                        with col2:
                            st.markdown(f"*Type: {field.field_type}*")
            else:
                st.warning("⚠️ No fields extracted. The PDF might not be a standard USCIS form.")
        
        with tab2:
            st.header("Debug Information")
            
            if show_debug and extractor.debug_info:
                st.subheader("🐛 Extraction Debug Log")
                for debug_item in extractor.debug_info:
                    st.text(debug_item)
            
            if show_raw_text:
                st.subheader("📄 Raw Extracted Text")
                st.text_area("Raw Text", content["text"], height=300)
            
            # Field statistics
            if fields:
                st.subheader("📊 Field Statistics")
                col1, col2, col3, col4 = st.columns(4)
                
                parent_fields = [f for f in fields if f.is_parent]
                subfields = [f for f in fields if f.is_subfield]
                regular_fields = [f for f in fields if not f.is_parent and not f.is_subfield]
                
                col1.metric("Total Fields", len(fields))
                col2.metric("Parent Fields", len(parent_fields))
                col3.metric("Subfields", len(subfields))
                col4.metric("Regular Fields", len(regular_fields))
        
        with tab3:
            st.header("Extracted Tables")
            
            if content.get("tables"):
                for i, table in enumerate(content["tables"]):
                    st.subheader(f"Table {i+1}")
                    df = pd.DataFrame(table["data"])
                    st.dataframe(df)
            else:
                st.info("No tables found in the document")
        
        with tab4:
            st.header("Export Options")
            
            if fields:
                # Create export data
                export_data = {
                    "form_type": form_type,
                    "extraction_date": datetime.now().isoformat(),
                    "field_hierarchy": extractor.field_hierarchy,
                    "fields": [
                        {
                            "item_number": f.item_number,
                            "label": f.label,
                            "field_type": f.field_type,
                            "is_parent": f.is_parent,
                            "is_subfield": f.is_subfield,
                            "parent_number": f.parent_number
                        }
                        for f in fields
                    ]
                }
                
                # JSON export
                st.subheader("📄 JSON Export")
                json_str = json.dumps(export_data, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=json_str,
                    file_name=f"{form_type}_extracted_fields.json",
                    mime="application/json"
                )
                
                # CSV export
                st.subheader("📊 CSV Export")
                df = pd.DataFrame([
                    {
                        "Item Number": f.item_number,
                        "Label": f.label,
                        "Field Type": f.field_type,
                        "Is Parent": f.is_parent,
                        "Is Subfield": f.is_subfield,
                        "Parent Number": f.parent_number or ""
                    }
                    for f in fields
                ])
                
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"{form_type}_extracted_fields.csv",
                    mime="text/csv"
                )
                
                # Preview export data
                with st.expander("🔍 Preview Export Data"):
                    st.json(export_data)

if __name__ == "__main__":
    main()
