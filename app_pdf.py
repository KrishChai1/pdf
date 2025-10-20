import streamlit as st
import sys
import os

def test_library_import(module_name, display_name):
    """Test importing a library and return status"""
    try:
        __import__(module_name)
        return True, f"✅ {display_name} - Working"
    except ImportError as e:
        return False, f"❌ {display_name} - Import Error: {str(e)}"
    except Exception as e:
        return False, f"❌ {display_name} - Other Error: {str(e)}"

def main():
    st.title("🔍 PDF Library Debug Tool")
    st.markdown("Let's find out exactly what's happening with your PDF libraries")
    
    # System info
    st.header("🖥️ System Information")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Python Version:** {sys.version}")
        st.write(f"**Python Executable:** {sys.executable}")
        
    with col2:
        venv = os.environ.get('VIRTUAL_ENV', 'None')
        st.write(f"**Virtual Environment:** {venv}")
        st.write(f"**Working Directory:** {os.getcwd()}")
    
    # Library tests
    st.header("📚 Library Import Tests")
    
    libraries_to_test = [
        ("fitz", "PyMuPDF"),
        ("PyPDF2", "PyPDF2"),
        ("docling.document_converter", "Docling"),
        ("pandas", "Pandas"),
        ("streamlit", "Streamlit")
    ]
    
    working_libs = []
    
    for module, name in libraries_to_test:
        is_working, message = test_library_import(module, name)
        if is_working:
            st.success(message)
            if name in ["PyMuPDF", "PyPDF2", "Docling"]:
                working_libs.append(name)
        else:
            st.error(message)
    
    # Summary
    st.header("📊 Summary")
    
    if working_libs:
        st.success(f"✅ {len(working_libs)} PDF libraries working: {', '.join(working_libs)}")
        
        # Test actual extraction
        st.subheader("🧪 PDF Upload Test")
        uploaded_file = st.file_uploader("Upload a PDF to test", type=['pdf'])
        
        if uploaded_file:
            st.write(f"File uploaded: {uploaded_file.name}")
            st.write(f"File size: {len(uploaded_file.getvalue())} bytes")
            
            # Test with each working library
            for lib in working_libs:
                with st.expander(f"Test {lib} Extraction"):
                    try:
                        if lib == "PyMuPDF":
                            test_pymupdf(uploaded_file)
                        elif lib == "PyPDF2":
                            test_pypdf2(uploaded_file)
                        elif lib == "Docling":
                            test_docling(uploaded_file)
                    except Exception as e:
                        st.error(f"❌ {lib} failed: {str(e)}")
    else:
        st.error("❌ No PDF libraries are working!")
        
        st.subheader("🔧 Installation Help")
        st.markdown("Try these installation commands:")
        
        # Installation buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.code("pip install pymupdf")
            
        with col2:
            st.code("pip install PyPDF2")
            
        with col3:
            st.code("pip install docling")
        
        st.markdown("**Manual Installation Steps:**")
        st.code(f"""
# Check your Python
{sys.executable} --version

# Install PyMuPDF (most reliable)
{sys.executable} -m pip install pymupdf

# Test it
{sys.executable} -c "import fitz; print('PyMuPDF works!')"

# If that works, restart Streamlit
        """)
    
    # Advanced debugging
    with st.expander("🔍 Advanced Debug Info"):
        st.subheader("Python Path")
        for i, path in enumerate(sys.path[:10]):  # Show first 10 paths
            st.write(f"{i}: {path}")
        
        st.subheader("Environment Variables")
        env_vars = ['PATH', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV']
        for var in env_vars:
            value = os.environ.get(var, "Not set")
            st.write(f"**{var}:** {value[:100]}...")  # Truncate long paths

def test_pymupdf(uploaded_file):
    """Test PyMuPDF extraction"""
    import fitz
    
    try:
        pdf_content = uploaded_file.getvalue()
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        
        text = ""
        for page_num in range(min(2, len(doc))):
            page = doc[page_num]
            page_text = page.get_text()
            text += f"Page {page_num + 1}:\n{page_text[:200]}...\n\n"
        
        doc.close()
        
        st.success("✅ PyMuPDF extraction successful!")
        st.write(f"Pages: {len(doc)}")
        st.text_area("Sample extracted text", text[:500])
        
    except Exception as e:
        st.error(f"❌ PyMuPDF failed: {str(e)}")

def test_pypdf2(uploaded_file):
    """Test PyPDF2 extraction"""
    import PyPDF2
    from io import BytesIO
    
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.getvalue()))
        
        text = ""
        for page_num in range(min(2, len(pdf_reader.pages))):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            text += f"Page {page_num + 1}:\n{page_text[:200]}...\n\n"
        
        st.success("✅ PyPDF2 extraction successful!")
        st.write(f"Pages: {len(pdf_reader.pages)}")
        st.text_area("Sample extracted text", text[:500])
        
    except Exception as e:
        st.error(f"❌ PyPDF2 failed: {str(e)}")

def test_docling(uploaded_file):
    """Test Docling extraction"""
    from docling.document_converter import DocumentConverter
    import tempfile
    from pathlib import Path
    
    try:
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        try:
            # Simple extraction without OCR
            converter = DocumentConverter()
            result = converter.convert(Path(tmp_file_path))
            text = result.document.export_to_text()
            
            st.success("✅ Docling extraction successful!")
            st.write(f"Text length: {len(text)} characters")
            st.text_area("Sample extracted text", text[:500])
            
        finally:
            os.unlink(tmp_file_path)
            
    except Exception as e:
        st.error(f"❌ Docling failed: {str(e)}")

if __name__ == "__main__":
    main()
