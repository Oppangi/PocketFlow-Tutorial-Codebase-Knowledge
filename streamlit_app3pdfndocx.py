import streamlit as st
import os
import tempfile
import zipfile
import shutil
from pathlib import Path
import subprocess
import sys
from io import StringIO
import contextlib
from dotenv import load_dotenv
import fnmatch
import glob
import time
from datetime import datetime, timedelta

# PDF and DOCX parsing libraries
import PyPDF2
import docx
from docx import Document

# Load environment variables
load_dotenv()

# Import your existing modules
try:
    from utils.call_llm import (
        test_llm_connection,
        generate_documentation_chunk,
        generate_project_overview,
        generate_summary,
    )
except ImportError:
    st.error(
        "Please make sure you're running from the PocketFlow directory with all dependencies installed"
    )
    st.stop()


def setup_page():
    st.set_page_config(
        page_title="Code2Documentation",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📚 Code2Documentation Generator")
    st.markdown("Transform your codebase into comprehensive documentation using AI")


def check_llm_setup():
    """Check if LLM is properly configured"""
    try:
        test_result = test_llm_connection()
        return True, "LLM connection successful"
    except Exception as e:
        return False, f"LLM setup error: {str(e)}"


def format_duration(seconds):
    """Format duration in a human-readable way"""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{int(minutes)} minutes {remaining_seconds:.1f} seconds"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{int(hours)} hours {int(remaining_minutes)} minutes"


def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            return text.strip()
    except Exception as e:
        st.warning(f"Error reading PDF {file_path}: {str(e)}")
        return None


def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    try:
        doc = Document(file_path)
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        return "\n".join(text)
    except Exception as e:
        st.warning(f"Error reading DOCX {file_path}: {str(e)}")
        return None


def read_file_content(file_path):
    """Read file content based on file type"""
    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == ".pdf":
        return extract_text_from_pdf(file_path)
    elif file_extension == ".docx":
        return extract_text_from_docx(file_path)
    else:
        # For text/code files
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            st.warning(f"Error reading file {file_path}: {str(e)}")
            return None


def get_file_type_icon(file_path):
    """Get appropriate icon for file type"""
    file_extension = os.path.splitext(file_path)[1].lower()

    icons = {
        ".py": "🐍",
        ".js": "📜",
        ".jsx": "⚛️",
        ".tsx": "⚛️",
        ".java": "☕",
        ".cpp": "⚙️",
        ".h": "📋",
        ".md": "📝",
        ".rst": "📝",
        ".pdf": "📄",
        ".docx": "📄",
        ".doc": "📄",
        ".txt": "📄",
    }

    return icons.get(file_extension, "📄")


def clone_repository(repo_url, temp_dir):
    """Clone repository to temporary directory"""
    try:
        # Check if GitHub token is available for private repos
        github_token = os.getenv("GITHUB_TOKEN")

        if github_token and "github.com" in repo_url:
            # Modify URL to include token for private repos
            if repo_url.startswith("https://github.com/"):
                repo_url = repo_url.replace(
                    "https://github.com/", f"https://{github_token}@github.com/"
                )

        result = subprocess.run(
            ["git", "clone", repo_url, temp_dir],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True, "Repository cloned successfully"
        else:
            return False, f"Git clone failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Repository cloning timed out"
    except Exception as e:
        return False, f"Error cloning repository: {str(e)}"


def save_uploaded_file(uploaded_file, temp_dir):
    """Save uploaded file to temporary directory"""
    try:
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return True, file_path
    except Exception as e:
        return False, f"Error saving file: {str(e)}"


def extract_zip_file(zip_path, extract_to):
    """Extract zip file to directory"""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)
        return True, "Files extracted successfully"
    except Exception as e:
        return False, f"Error extracting zip: {str(e)}"


def should_include_file(file_path, include_patterns, exclude_patterns):
    """Check if file should be included based on patterns"""
    file_name = os.path.basename(file_path)
    relative_path = file_path

    # Check exclude patterns first
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(
            relative_path, pattern
        ):
            return False

    # Check include patterns
    for pattern in include_patterns:
        if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(
            relative_path, pattern
        ):
            return True

    return False


def get_files_to_process(source_path, include_patterns, exclude_patterns, max_size):
    """Get list of files to process based on patterns and size"""
    files_to_process = []

    for root, dirs, files in os.walk(source_path):
        # Filter directories based on exclude patterns
        dirs[:] = [
            d
            for d in dirs
            if not any(
                fnmatch.fnmatch(d, pattern.rstrip("/*")) for pattern in exclude_patterns
            )
        ]

        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, source_path)

            # Check if file should be included
            if should_include_file(relative_path, include_patterns, exclude_patterns):
                try:
                    if os.path.getsize(file_path) <= max_size:
                        files_to_process.append(file_path)
                except OSError:
                    # Skip files that can't be accessed
                    continue

    return files_to_process


def generate_project_structure(source_path, include_patterns, exclude_patterns):
    """Generate a string representation of project structure"""
    structure = []

    for root, dirs, files in os.walk(source_path):
        # Filter directories
        dirs[:] = [
            d
            for d in dirs
            if not any(
                fnmatch.fnmatch(d, pattern.rstrip("/*")) for pattern in exclude_patterns
            )
        ]

        level = root.replace(source_path, "").count(os.sep)
        indent = " " * 2 * level
        structure.append(f"{indent}{os.path.basename(root)}/")

        # Add files with icons
        subindent = " " * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, source_path)
            if should_include_file(relative_path, include_patterns, exclude_patterns):
                icon = get_file_type_icon(file_path)
                structure.append(f"{subindent}{icon} {file}")

    return "\n".join(structure)


def generate_docs(
    source_path,
    include_patterns,
    exclude_patterns,
    language,
    max_size,
    max_files_to_process,
):
    """Generate documentation using direct LLM calls"""
    try:
        # Start timing
        start_time = time.time()

        progress_bar = st.progress(0)
        status_text = st.empty()

        # Step 1: Get files to process
        status_text.text("Analyzing project structure...")
        files_to_process = get_files_to_process(
            source_path, include_patterns, exclude_patterns, max_size
        )

        if not files_to_process:
            return False, "No files found matching the specified patterns", None

        progress_bar.progress(0.1)

        # Step 2: Generate project structure
        status_text.text("Generating project structure...")
        project_structure = generate_project_structure(
            source_path, include_patterns, exclude_patterns
        )
        progress_bar.progress(0.2)

        # Step 3: Generate project overview
        status_text.text("Generating project overview...")
        project_overview = generate_project_overview(project_structure, language)
        progress_bar.progress(0.3)

        # Step 4: Process individual files (use user-defined limit)
        documentation_parts = [project_overview]
        total_files = len(files_to_process)
        files_to_process_count = min(total_files, max_files_to_process)

        # Track file types processed
        file_types_processed = {}

        for i, file_path in enumerate(files_to_process[:files_to_process_count]):
            file_name = os.path.basename(file_path)
            file_extension = os.path.splitext(file_path)[1].lower()

            # Track file types
            if file_extension not in file_types_processed:
                file_types_processed[file_extension] = 0
            file_types_processed[file_extension] += 1

            icon = get_file_type_icon(file_path)
            status_text.text(
                f"Processing file {i + 1}/{files_to_process_count}: {icon} {file_name}"
            )

            try:
                # Use the enhanced file reading function
                content = read_file_content(file_path)

                if content is None:
                    continue  # Skip files that couldn't be read

                if not content.strip():
                    st.warning(f"Skipped empty file: {file_name}")
                    continue

                relative_path = os.path.relpath(file_path, source_path)

                # Add file type context for better documentation
                file_type_context = ""
                if file_extension == ".pdf":
                    file_type_context = " (PDF Document)"
                elif file_extension == ".docx":
                    file_type_context = " (Word Document)"

                file_docs = generate_documentation_chunk(
                    content, relative_path + file_type_context, language
                )
                documentation_parts.append(
                    f"\n\n## File: {icon} {relative_path}{file_type_context}\n\n{file_docs}"
                )

            except Exception as e:
                st.warning(f"Skipped file {relative_path}: {str(e)}")

            progress_bar.progress(0.3 + (0.6 * (i + 1) / files_to_process_count))

        # Step 5: Generate summary
        status_text.text("Generating final summary...")
        final_summary = generate_summary(documentation_parts, language)
        progress_bar.progress(0.95)

        # Step 6: Combine everything
        status_text.text("Finalizing documentation...")

        # Calculate total time
        end_time = time.time()
        total_time = end_time - start_time

        # Create file types summary
        file_types_summary = "\n".join(
            [
                f"  - {ext or 'no extension'}: {count} files"
                for ext, count in sorted(file_types_processed.items())
            ]
        )

        final_documentation = f"""# Project Documentation

{final_summary}

---

{chr(10).join(documentation_parts)}

---

## Processing Summary
- Total files found: {total_files}
- Files processed: {files_to_process_count}
- File types processed:
{file_types_summary}
- Project structure analyzed: ✓
- Time taken: {format_duration(total_time)}
- Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        progress_bar.progress(1.0)
        status_text.text("Documentation generation complete!")

        return (
            True,
            final_documentation,
            {
                "files_processed": files_to_process_count,
                "total_files": total_files,
                "processing_time": total_time,
                "start_time": start_time,
                "end_time": end_time,
                "file_types_processed": file_types_processed,
            },
        )

    except Exception as e:
        return False, f"Error generating documentation: {str(e)}", None


def create_download_link(content, filename):
    """Create download link for generated documentation"""
    return st.download_button(
        label=f"📥 Download {filename}",
        data=content,
        file_name=filename,
        mime="text/markdown",
    )


def main():
    setup_page()

    # Check for required libraries
    try:
        import PyPDF2
        import docx

        pdf_support = True
    except ImportError:
        pdf_support = False
        st.warning(
            "⚠️ PDF/DOCX support not available. Install: pip install PyPDF2 python-docx"
        )

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # PDF/DOCX Support Status
        if pdf_support:
            st.success("✅ PDF & DOCX support enabled")
        else:
            st.error("❌ PDF & DOCX support disabled")

        # GitHub token info
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            st.success("✅ GitHub token configured (can access private repos)")
        else:
            st.info("ℹ️ No GitHub token - only public repos accessible")

        # LLM Setup Check
        st.subheader("🔗 LLM Connection")
        if st.button("Test LLM Connection"):
            is_connected, message = check_llm_setup()
            if is_connected:
                st.success(message)
            else:
                st.error(message)
                st.info("Please configure your LLM in utils/call_llm.py")

        st.subheader("📋 Processing Options")
        language = st.selectbox(
            "Documentation Language",
            ["English", "Chinese", "Spanish", "French", "German"],
            index=0,
        )

        max_size = st.number_input(
            "Max File Size (bytes)",
            min_value=1000,
            max_value=100000,
            value=50000,
            step=1000,
        )

        # NEW: Add option for maximum files to process
        st.subheader("🔢 File Processing Limit")
        max_files_to_process = st.number_input(
            "Maximum Files to Process",
            min_value=1,
            max_value=500,
            value=10,
            step=1,
            help="Choose how many files you want to process. More files = longer processing time but more complete documentation.",
        )

        # Show estimated processing time
        estimated_time_per_file = 15  # seconds per file (rough estimate)
        estimated_total_time = max_files_to_process * estimated_time_per_file
        st.info(
            f"⏱️ Estimated processing time: ~{format_duration(estimated_total_time)}"
        )

        # Enhanced include patterns with PDF/DOCX support
        default_include_patterns = (
            "*.py\n*.js\n*.tsx\n*.jsx\n*.java\n*.cpp\n*.h\n*.md\n*.rst"
        )
        if pdf_support:
            default_include_patterns += "\n*.pdf\n*.docx\n*.doc"

        include_patterns = (
            st.text_area(
                "Include Patterns (one per line)",
                value=default_include_patterns,
                height=120,
            )
            .strip()
            .split("\n")
        )

        exclude_patterns = (
            st.text_area(
                "Exclude Patterns (one per line)",
                value="tests/*\n*test*\n*.min.js\nnode_modules/*\n__pycache__/*\nvenv/*\n.venv/*\n.git/*\ndist/*\nbuild/*",
                height=100,
            )
            .strip()
            .split("\n")
        )

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("📂 Input Source")

        # Input method selection
        input_method = st.radio(
            "Choose input method:",
            ["GitHub Repository", "Upload File", "Upload Folder (ZIP)"],
        )

        source_path = None
        temp_dir = None

        if input_method == "GitHub Repository":
            repo_url = st.text_input(
                "GitHub Repository URL",
                placeholder="https://github.com/username/repository",
            )

            if st.button("📥 Clone Repository") and repo_url:
                with st.spinner("Cloning repository..."):
                    temp_dir = tempfile.mkdtemp()
                    success, message = clone_repository(repo_url, temp_dir)
                    if success:
                        st.success(message)
                        source_path = temp_dir
                        st.session_state.source_path = source_path
                    else:
                        st.error(message)

        elif input_method == "Upload File":
            # Enhanced file types including PDF/DOCX
            supported_types = [
                "py",
                "js",
                "jsx",
                "tsx",
                "java",
                "cpp",
                "h",
                "c",
                "cs",
                "php",
                "rb",
                "go",
                "rs",
                "md",
                "rst",
                "txt",
            ]

            if pdf_support:
                supported_types.extend(["pdf", "docx", "doc"])

            uploaded_file = st.file_uploader(
                "Choose a file",
                type=supported_types,
            )

            if uploaded_file is not None:
                temp_dir = tempfile.mkdtemp()
                success, file_path = save_uploaded_file(uploaded_file, temp_dir)
                if success:
                    icon = get_file_type_icon(uploaded_file.name)
                    st.success(f"File uploaded: {icon} {uploaded_file.name}")
                    source_path = temp_dir
                    st.session_state.source_path = source_path
                else:
                    st.error(file_path)

        elif input_method == "Upload Folder (ZIP)":
            uploaded_zip = st.file_uploader("Choose a ZIP file", type=["zip"])

            if uploaded_zip is not None:
                temp_dir = tempfile.mkdtemp()
                zip_path = os.path.join(temp_dir, uploaded_zip.name)

                with open(zip_path, "wb") as f:
                    f.write(uploaded_zip.getbuffer())

                extract_dir = os.path.join(temp_dir, "extracted")
                success, message = extract_zip_file(zip_path, extract_dir)

                if success:
                    st.success(f"ZIP file uploaded and extracted: {uploaded_zip.name}")
                    source_path = extract_dir
                    st.session_state.source_path = source_path
                else:
                    st.error(message)

    with col2:
        st.header("📄 Documentation Generation")

        # Use source_path from session state if available
        if "source_path" in st.session_state:
            source_path = st.session_state.source_path

        if source_path and st.button("🚀 Generate Documentation"):
            success, content, result = generate_docs(
                source_path,
                include_patterns,
                exclude_patterns,
                language,
                max_size,
                max_files_to_process,
            )

            if success:
                st.success("Documentation generated successfully!")
                if result:
                    # Enhanced success message with timing
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Files Processed", f"{result['files_processed']}")
                        st.metric("Total Files Found", f"{result['total_files']}")
                    with col2:
                        st.metric(
                            "Processing Time",
                            format_duration(result["processing_time"]),
                        )
                        st.metric(
                            "Files per Second",
                            f"{result['files_processed'] / result['processing_time']:.2f}",
                        )

                    # Show file types processed
                    if "file_types_processed" in result:
                        st.subheader("📊 File Types Processed")
                        for ext, count in result["file_types_processed"].items():
                            icon = get_file_type_icon(f"dummy{ext}")
                            st.write(
                                f"{icon} **{ext or 'no extension'}**: {count} files"
                            )

                # Store in session state
                st.session_state.generated_docs = content
                st.session_state.doc_result = result

            else:
                st.error(content)

    # Documentation display and download section
    if "generated_docs" in st.session_state and st.session_state.generated_docs:
        st.header("📋 Generated Documentation")

        # Show processing summary in a nice format
        if "doc_result" in st.session_state:
            result = st.session_state.doc_result

            # Create metrics display
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📁 Files Processed", result["files_processed"])
            with col2:
                st.metric("📊 Total Files", result["total_files"])
            with col3:
                st.metric(
                    "⏱️ Processing Time", format_duration(result["processing_time"])
                )
            with col4:
                completion_percentage = (
                    result["files_processed"] / result["total_files"]
                ) * 100
                st.metric("✅ Completion", f"{completion_percentage:.1f}%")

        # Create tabs for different views
        tab1, tab2 = st.tabs(["📖 Preview", "📥 Download"])

        with tab1:
            st.markdown(st.session_state.generated_docs)

        with tab2:
            col1, col2 = st.columns(2)

            with col1:
                create_download_link(
                    st.session_state.generated_docs, "documentation.md"
                )

            with col2:
                if st.button("🗑️ Clear Documentation"):
                    del st.session_state.generated_docs
                    if "doc_result" in st.session_state:
                        del st.session_state.doc_result
                    st.rerun()

    # Footer
    st.markdown("---")
    st.markdown("Built with ❤️ using PocketFlow and Streamlit")


if __name__ == "__main__":
    main()
