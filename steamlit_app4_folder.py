# import streamlit as st
# import os
# import tempfile
# import zipfile
# import shutil
# from pathlib import Path
# import subprocess
# import sys
# from io import StringIO
# import contextlib
# from dotenv import load_dotenv
# import fnmatch
# import glob
# import time
# from datetime import datetime, timedelta

# # Load environment variables
# load_dotenv()

# # Import your existing modules
# try:
#     from utils.call_llm import (
#         test_llm_connection,
#         generate_documentation_chunk,
#         generate_project_overview,
#         generate_summary,
#     )
# except ImportError:
#     st.error(
#         "Please make sure you're running from the PocketFlow directory with all dependencies installed"
#     )
#     st.stop()


# def setup_page():
#     st.set_page_config(
#         page_title="Code2Documentation",
#         page_icon="📚",
#         layout="wide",
#         initial_sidebar_state="expanded",
#     )

#     st.title("📚 Code2Documentation Generator")
#     st.markdown("Transform your codebase into comprehensive documentation using AI")


# def check_llm_setup():
#     """Check if LLM is properly configured"""
#     try:
#         test_result = test_llm_connection()
#         return True, "LLM connection successful"
#     except Exception as e:
#         return False, f"LLM setup error: {str(e)}"


# def format_duration(seconds):
#     """Format duration in a human-readable way"""
#     if seconds < 60:
#         return f"{seconds:.1f} seconds"
#     elif seconds < 3600:
#         minutes = seconds // 60
#         remaining_seconds = seconds % 60
#         return f"{int(minutes)} minutes {remaining_seconds:.1f} seconds"
#     else:
#         hours = seconds // 3600
#         remaining_minutes = (seconds % 3600) // 60
#         return f"{int(hours)} hours {int(remaining_minutes)} minutes"


# def clone_repository(repo_url, temp_dir):
#     """Clone repository to temporary directory"""
#     try:
#         # Check if GitHub token is available for private repos
#         github_token = os.getenv("GITHUB_TOKEN")

#         if github_token and "github.com" in repo_url:
#             # Modify URL to include token for private repos
#             if repo_url.startswith("https://github.com/"):
#                 repo_url = repo_url.replace(
#                     "https://github.com/", f"https://{github_token}@github.com/"
#                 )

#         result = subprocess.run(
#             ["git", "clone", repo_url, temp_dir],
#             capture_output=True,
#             text=True,
#             timeout=300,
#         )
#         if result.returncode == 0:
#             return True, "Repository cloned successfully"
#         else:
#             return False, f"Git clone failed: {result.stderr}"
#     except subprocess.TimeoutExpired:
#         return False, "Repository cloning timed out"
#     except Exception as e:
#         return False, f"Error cloning repository: {str(e)}"


# def save_uploaded_files(uploaded_files, temp_dir):
#     """Save uploaded files to temporary directory maintaining folder structure"""
#     try:
#         for uploaded_file in uploaded_files:
#             # Create directory structure if needed
#             file_path = os.path.join(temp_dir, uploaded_file.name)
#             os.makedirs(os.path.dirname(file_path), exist_ok=True)

#             with open(file_path, "wb") as f:
#                 f.write(uploaded_file.getbuffer())

#         return True, f"Successfully saved {len(uploaded_files)} files"
#     except Exception as e:
#         return False, f"Error saving files: {str(e)}"


# def extract_zip_file(zip_path, extract_to):
#     """Extract zip file to directory"""
#     try:
#         with zipfile.ZipFile(zip_path, "r") as zip_ref:
#             zip_ref.extractall(extract_to)
#         return True, "Files extracted successfully"
#     except Exception as e:
#         return False, f"Error extracting zip: {str(e)}"


# def find_project_root(extracted_path):
#     """
#     Intelligently find the actual project root in extracted ZIP.
#     This handles cases where ZIP contains nested folders.
#     """
#     # Strategy 1: Look for common project indicators
#     project_indicators = [
#         "requirements.txt",
#         "package.json",
#         "pom.xml",
#         "build.gradle",
#         "Cargo.toml",
#         "go.mod",
#         "setup.py",
#         "pyproject.toml",
#         "composer.json",
#         "Gemfile",
#         "yarn.lock",
#         "package-lock.json",
#         ".gitignore",
#         "README.md",
#         "LICENSE",
#         "Makefile",
#         "Dockerfile",
#     ]

#     # Strategy 2: Look for source code directories
#     source_dirs = ["src", "lib", "app", "components", "modules", "packages"]

#     def score_directory(dir_path):
#         """Score a directory based on how likely it is to be the project root"""
#         score = 0

#         if not os.path.isdir(dir_path):
#             return 0

#         files = os.listdir(dir_path)

#         # Check for project indicators
#         for indicator in project_indicators:
#             if indicator in files:
#                 score += 10

#         # Check for source directories
#         for src_dir in source_dirs:
#             if src_dir in files:
#                 score += 5

#         # Check for code files in root
#         code_extensions = [".py", ".js", ".java", ".cpp", ".go", ".rs", ".php", ".rb"]
#         for file in files:
#             if any(file.endswith(ext) for ext in code_extensions):
#                 score += 1

#         # Penalty for being too nested (prefer shallower directories)
#         depth = len(os.path.relpath(dir_path, extracted_path).split(os.sep))
#         score -= depth * 2

#         return score

#     # Find all directories and score them
#     candidates = []
#     for root, dirs, files in os.walk(extracted_path):
#         score = score_directory(root)
#         candidates.append((root, score))

#         # Don't go too deep
#         if len(os.path.relpath(root, extracted_path).split(os.sep)) > 3:
#             dirs.clear()

#     # Sort by score and return the best candidate
#     candidates.sort(key=lambda x: x[1], reverse=True)

#     if candidates and candidates[0][1] > 0:
#         return candidates[0][0]
#     else:
#         # Fallback: return the first non-empty directory or the extracted path itself
#         for root, dirs, files in os.walk(extracted_path):
#             if files:  # Directory with files
#                 return root
#         return extracted_path


# def should_include_file(file_path, include_patterns, exclude_patterns):
#     """Check if file should be included based on patterns"""
#     file_name = os.path.basename(file_path)
#     # Normalize path separators for consistent matching
#     relative_path = file_path.replace(os.path.sep, "/")

#     # Check exclude patterns first (more specific matching)
#     for pattern in exclude_patterns:
#         # Handle different types of exclude patterns
#         if pattern.endswith("/*"):
#             # Directory pattern like "tests/*"
#             dir_pattern = pattern[:-2]  # Remove "/*"
#             if f"/{dir_pattern}/" in f"/{relative_path}" or relative_path.startswith(
#                 f"{dir_pattern}/"
#             ):
#                 return False
#         elif pattern.startswith("*") and pattern.endswith("*"):
#             # Pattern like "*test*" - check if substring is in path
#             substring = pattern[1:-1]  # Remove * from both ends
#             if substring in relative_path:
#                 return False
#         elif fnmatch.fnmatch(file_name, pattern):
#             # Direct filename pattern match
#             return False
#         elif fnmatch.fnmatch(relative_path, pattern):
#             # Direct path pattern match
#             return False

#     # Check include patterns
#     for pattern in include_patterns:
#         if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(
#             relative_path, pattern
#         ):
#             return True

#     return False


# def get_files_to_process(source_path, include_patterns, exclude_patterns, max_size):
#     """Get list of files to process based on patterns and size"""
#     files_to_process = []

#     for root, dirs, files in os.walk(source_path):
#         # Filter directories based on exclude patterns
#         dirs_to_remove = []
#         for d in dirs:
#             dir_path = os.path.relpath(os.path.join(root, d), source_path)
#             for pattern in exclude_patterns:
#                 if pattern.endswith("/*"):
#                     dir_pattern = pattern[:-2]
#                     if fnmatch.fnmatch(d, dir_pattern) or fnmatch.fnmatch(
#                         dir_path, dir_pattern
#                     ):
#                         dirs_to_remove.append(d)
#                         break

#         for d in dirs_to_remove:
#             dirs.remove(d)

#         for file in files:
#             file_path = os.path.join(root, file)
#             relative_path = os.path.relpath(file_path, source_path)

#             # Check if file should be included
#             if should_include_file(relative_path, include_patterns, exclude_patterns):
#                 try:
#                     file_size = os.path.getsize(file_path)
#                     if file_size <= max_size:
#                         files_to_process.append(file_path)
#                 except OSError:
#                     continue

#     return files_to_process


# def generate_project_structure(source_path, include_patterns, exclude_patterns):
#     """Generate a string representation of project structure"""
#     structure = []

#     for root, dirs, files in os.walk(source_path):
#         # Filter directories based on exclude patterns
#         dirs_to_remove = []
#         for d in dirs:
#             dir_path = os.path.relpath(os.path.join(root, d), source_path)
#             for pattern in exclude_patterns:
#                 if pattern.endswith("/*"):
#                     dir_pattern = pattern[:-2]
#                     if fnmatch.fnmatch(d, dir_pattern) or fnmatch.fnmatch(
#                         dir_path, dir_pattern
#                     ):
#                         dirs_to_remove.append(d)
#                         break

#         for d in dirs_to_remove:
#             dirs.remove(d)

#         level = root.replace(source_path, "").count(os.sep)
#         indent = " " * 2 * level
#         structure.append(f"{indent}{os.path.basename(root)}/")

#         # Add files
#         subindent = " " * 2 * (level + 1)
#         for file in files:
#             file_path = os.path.join(root, file)
#             relative_path = os.path.relpath(file_path, source_path)
#             if should_include_file(relative_path, include_patterns, exclude_patterns):
#                 structure.append(f"{subindent}{file}")

#     return "\n".join(structure)


# def generate_docs(
#     source_path,
#     include_patterns,
#     exclude_patterns,
#     language,
#     max_size,
#     max_files_to_process,
# ):
#     """Generate documentation using direct LLM calls"""
#     try:
#         # Start timing
#         start_time = time.time()

#         progress_bar = st.progress(0)
#         status_text = st.empty()

#         # Step 1: Get files to process
#         status_text.text("Analyzing project structure...")
#         files_to_process = get_files_to_process(
#             source_path, include_patterns, exclude_patterns, max_size
#         )

#         if not files_to_process:
#             return False, "No files found matching the specified patterns", None

#         progress_bar.progress(0.1)

#         # Step 2: Generate project structure
#         status_text.text("Generating project structure...")
#         project_structure = generate_project_structure(
#             source_path, include_patterns, exclude_patterns
#         )
#         progress_bar.progress(0.2)

#         # Step 3: Generate project overview
#         status_text.text("Generating project overview...")
#         project_overview = generate_project_overview(project_structure, language)
#         progress_bar.progress(0.3)

#         # Step 4: Process individual files (use user-defined limit)
#         documentation_parts = [project_overview]
#         total_files = len(files_to_process)
#         files_to_process_count = min(total_files, max_files_to_process)

#         for i, file_path in enumerate(files_to_process[:files_to_process_count]):
#             status_text.text(
#                 f"Processing file {i + 1}/{files_to_process_count}: {os.path.basename(file_path)}"
#             )

#             try:
#                 with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                     content = f.read()

#                 relative_path = os.path.relpath(file_path, source_path)
#                 file_docs = generate_documentation_chunk(
#                     content, relative_path, language
#                 )
#                 documentation_parts.append(
#                     f"\n\n## File: {relative_path}\n\n{file_docs}"
#                 )

#             except Exception as e:
#                 st.warning(f"Skipped file {relative_path}: {str(e)}")

#             progress_bar.progress(0.3 + (0.6 * (i + 1) / files_to_process_count))

#         # Step 5: Generate summary
#         status_text.text("Generating final summary...")
#         final_summary = generate_summary(documentation_parts, language)
#         progress_bar.progress(0.95)

#         # Step 6: Combine everything
#         status_text.text("Finalizing documentation...")

#         # Calculate total time
#         end_time = time.time()
#         total_time = end_time - start_time

#         final_documentation = f"""# Project Documentation

# {final_summary}

# ---

# {chr(10).join(documentation_parts)}

# ---

# ## Processing Summary
# - Total files found: {total_files}
# - Files processed: {files_to_process_count}
# - Project structure analyzed: ✓
# - Time taken: {format_duration(total_time)}
# - Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# """

#         progress_bar.progress(1.0)
#         status_text.text("Documentation generation complete!")

#         return (
#             True,
#             final_documentation,
#             {
#                 "files_processed": files_to_process_count,
#                 "total_files": total_files,
#                 "processing_time": total_time,
#                 "start_time": start_time,
#                 "end_time": end_time,
#             },
#         )

#     except Exception as e:
#         return False, f"Error generating documentation: {str(e)}", None


# def create_download_link(content, filename):
#     """Create download link for generated documentation"""
#     return st.download_button(
#         label=f"📥 Download {filename}",
#         data=content,
#         file_name=filename,
#         mime="text/markdown",
#     )


# def main():
#     setup_page()

#     # Sidebar for configuration
#     with st.sidebar:
#         st.header("⚙️ Configuration")

#         # GitHub token info
#         github_token = os.getenv("GITHUB_TOKEN")
#         if github_token:
#             st.success("✅ GitHub token configured (can access private repos)")
#         else:
#             st.info("ℹ️ No GitHub token - only public repos accessible")

#         # LLM Setup Check
#         st.subheader("🔗 LLM Connection")
#         if st.button("Test LLM Connection"):
#             is_connected, message = check_llm_setup()
#             if is_connected:
#                 st.success(message)
#             else:
#                 st.error(message)
#                 st.info("Please configure your LLM in utils/call_llm.py")

#         st.subheader("📋 Processing Options")
#         language = st.selectbox(
#             "Documentation Language",
#             ["English", "Chinese", "Spanish", "French", "German"],
#             index=0,
#         )

#         max_size = st.number_input(
#             "Max File Size (bytes)",
#             min_value=1000,
#             max_value=100000,
#             value=50000,
#             step=1000,
#         )

#         # NEW: Add option for maximum files to process
#         st.subheader("🔢 File Processing Limit")
#         max_files_to_process = st.number_input(
#             "Maximum Files to Process",
#             min_value=1,
#             max_value=500,
#             value=10,
#             step=1,
#             help="Choose how many files you want to process. More files = longer processing time but more complete documentation.",
#         )

#         # Show estimated processing time
#         estimated_time_per_file = 15  # seconds per file (rough estimate)
#         estimated_total_time = max_files_to_process * estimated_time_per_file
#         st.info(
#             f"⏱️ Estimated processing time: ~{format_duration(estimated_total_time)}"
#         )

#         # FIXED: Better default exclude patterns
#         include_patterns_text = st.text_area(
#             "Include Patterns (one per line)",
#             value="*.py\n*.js\n*.tsx\n*.jsx\n*.java\n*.cpp\n*.h\n*.md\n*.rst",
#             height=100,
#         )
#         include_patterns = [
#             p.strip() for p in include_patterns_text.strip().split("\n") if p.strip()
#         ]

#         exclude_patterns_text = st.text_area(
#             "Exclude Patterns (one per line)",
#             value="tests/*\n*test*\n*.min.js\nnode_modules/*\n__pycache__/*\nvenv/*\n.venv/*\n.git/*\ndist/*\nbuild/*\n*.log\n*.tmp",
#             height=100,
#         )
#         exclude_patterns = [
#             p.strip() for p in exclude_patterns_text.strip().split("\n") if p.strip()
#         ]

#     # Main content area - Two columns for input and documentation
#     main_col1, main_col2 = st.columns([1, 1])

#     with main_col1:
#         st.header("📂 Input Source")

#         # Input method selection
#         input_method = st.radio(
#             "Choose input method:",
#             [
#                 "GitHub Repository",
#                 "Upload Single File",
#                 "Upload Folder",
#                 "Upload ZIP File",
#             ],
#         )

#         source_path = None
#         temp_dir = None

#         if input_method == "GitHub Repository":
#             repo_url = st.text_input(
#                 "GitHub Repository URL",
#                 placeholder="https://github.com/username/repository",
#             )

#             if st.button("📥 Clone Repository") and repo_url:
#                 with st.spinner("Cloning repository..."):
#                     temp_dir = tempfile.mkdtemp()
#                     success, message = clone_repository(repo_url, temp_dir)
#                     if success:
#                         st.success(message)
#                         source_path = temp_dir
#                         st.session_state.source_path = source_path
#                     else:
#                         st.error(message)

#         elif input_method == "Upload Single File":
#             uploaded_file = st.file_uploader(
#                 "Choose a file",
#                 type=[
#                     "py",
#                     "js",
#                     "jsx",
#                     "tsx",
#                     "java",
#                     "cpp",
#                     "h",
#                     "c",
#                     "cs",
#                     "php",
#                     "rb",
#                     "go",
#                     "rs",
#                     "md",
#                     "rst",
#                 ],
#             )

#             if uploaded_file is not None:
#                 temp_dir = tempfile.mkdtemp()
#                 success, message = save_uploaded_files([uploaded_file], temp_dir)
#                 if success:
#                     st.success(f"File uploaded: {uploaded_file.name}")
#                     source_path = temp_dir
#                     st.session_state.source_path = source_path
#                 else:
#                     st.error(message)

#         elif input_method == "Upload Folder":
#             st.info("📁 Upload multiple files to create a folder structure")
#             st.markdown("""
#             **Instructions:**
#             1. Select multiple files from your project folder
#             2. You can select files from different subdirectories
#             3. The app will maintain the folder structure based on file names
#             4. Use files with clear paths (e.g., `src/main.py`, `tests/test_main.py`)
#             """)

#             uploaded_files = st.file_uploader(
#                 "Choose files from your project folder",
#                 type=[
#                     "py",
#                     "js",
#                     "jsx",
#                     "tsx",
#                     "java",
#                     "cpp",
#                     "h",
#                     "c",
#                     "cs",
#                     "php",
#                     "rb",
#                     "go",
#                     "rs",
#                     "md",
#                     "rst",
#                     "txt",
#                     "json",
#                     "xml",
#                     "html",
#                     "css",
#                     "scss",
#                     "less",
#                     "ts",
#                     "vue",
#                     "swift",
#                     "kt",
#                     "scala",
#                     "r",
#                     "m",
#                     "mm",
#                     "sh",
#                     "bat",
#                 ],
#                 accept_multiple_files=True,
#             )

#             if uploaded_files:
#                 temp_dir = tempfile.mkdtemp()
#                 success, message = save_uploaded_files(uploaded_files, temp_dir)
#                 if success:
#                     st.success(f"Successfully uploaded {len(uploaded_files)} files")
#                     source_path = temp_dir
#                     st.session_state.source_path = source_path

#                     # Show uploaded files structure
#                     st.subheader("📁 Uploaded Files Structure")
#                     for uploaded_file in uploaded_files:
#                         st.write(f"📄 {uploaded_file.name}")

#                     # Show actual directory structure
#                     st.subheader("📂 Directory Structure")
#                     for root, dirs, files in os.walk(temp_dir):
#                         level = root.replace(temp_dir, "").count(os.sep)
#                         indent = " " * 2 * level
#                         folder_name = (
#                             os.path.basename(root) if os.path.basename(root) else "root"
#                         )
#                         st.write(f"{indent}{folder_name}/")
#                         subindent = " " * 2 * (level + 1)
#                         for file in files:
#                             st.write(f"{subindent}{file}")
#                 else:
#                     st.error(message)

#         elif input_method == "Upload ZIP File":
#             st.info("📦 Upload a ZIP file containing your project")
#             st.markdown("""
#             **Features:**
#             - 🧠 **Smart Root Detection**: Automatically finds your project's actual root folder
#             - 📁 **Handles Nested Folders**: Works even if your ZIP has extra wrapper folders
#             - 🔍 **Project Intelligence**: Looks for `package.json`, `requirements.txt`, `README.md`, etc.
#             - 📊 **Shows Structure**: Displays both extracted and detected project structure
#             """)

#             uploaded_zip = st.file_uploader(
#                 "Choose a ZIP file containing your project", type=["zip"]
#             )

#             if uploaded_zip is not None:
#                 temp_dir = tempfile.mkdtemp()
#                 zip_path = os.path.join(temp_dir, uploaded_zip.name)

#                 # Save the ZIP file
#                 with open(zip_path, "wb") as f:
#                     f.write(uploaded_zip.getbuffer())

#                 # Extract the ZIP file
#                 extract_dir = os.path.join(temp_dir, "extracted")
#                 success, message = extract_zip_file(zip_path, extract_dir)

#                 if success:
#                     st.success(f"ZIP file uploaded and extracted: {uploaded_zip.name}")

#                     # Find the actual project root using intelligent detection
#                     project_root = find_project_root(extract_dir)
#                     source_path = project_root
#                     st.session_state.source_path = source_path

#                     # Show extraction results in a more compact way
#                     st.subheader("📦 Extraction Results")

#                     # Detected project root
#                     relative_root = os.path.relpath(project_root, extract_dir)
#                     if relative_root == ".":
#                         st.write("✅ Project root: **Root directory**")
#                     else:
#                         st.write(f"✅ Project root: **{relative_root}**")

#                     # Show project structure (limited depth)
#                     st.write("**Project structure:**")
#                     for root, dirs, files in os.walk(project_root):
#                         level = root.replace(project_root, "").count(os.sep)
#                         if level > 2:  # Limit depth for display
#                             continue
#                         indent = " " * 2 * level
#                         folder_name = (
#                             os.path.basename(root)
#                             if os.path.basename(root)
#                             else "project"
#                         )
#                         st.write(f"{indent}{folder_name}/")
#                         subindent = " " * 2 * (level + 1)
#                         for file in files[:3]:  # Show first 3 files
#                             st.write(f"{subindent}{file}")
#                         if len(files) > 3:
#                             st.write(f"{subindent}... and {len(files) - 3} more files")

#                     # Show project indicators found
#                     project_indicators = [
#                         "requirements.txt",
#                         "package.json",
#                         "pom.xml",
#                         "build.gradle",
#                         "Cargo.toml",
#                         "go.mod",
#                         "setup.py",
#                         "pyproject.toml",
#                         "composer.json",
#                         "Gemfile",
#                         "yarn.lock",
#                         "package-lock.json",
#                         ".gitignore",
#                         "README.md",
#                         "LICENSE",
#                         "Makefile",
#                         "Dockerfile",
#                     ]

#                     found_indicators = []
#                     if os.path.exists(project_root):
#                         for indicator in project_indicators:
#                             if os.path.exists(os.path.join(project_root, indicator)):
#                                 found_indicators.append(indicator)

#                     if found_indicators:
#                         st.subheader("🎯 Project Indicators Found")
#                         st.write("Files that helped identify the project root:")
#                         for indicator in found_indicators:
#                             st.write(f"✅ {indicator}")

#                 else:
#                     st.error(message)

#     with main_col2:
#         st.header("📄 Documentation Generation")

#         # Use source_path from session state if available
#         if "source_path" in st.session_state:
#             source_path = st.session_state.source_path

#         if source_path and st.button("🚀 Generate Documentation"):
#             success, content, result = generate_docs(
#                 source_path,
#                 include_patterns,
#                 exclude_patterns,
#                 language,
#                 max_size,
#                 max_files_to_process,
#             )

#             if success:
#                 st.success("Documentation generated successfully!")
#                 if result:
#                     # Success metrics (non-nested)
#                     st.write("**Processing Summary:**")
#                     st.write(f"📁 Files Processed: {result['files_processed']}")
#                     st.write(f"📊 Total Files Found: {result['total_files']}")
#                     st.write(
#                         f"⏱️ Processing Time: {format_duration(result['processing_time'])}"
#                     )
#                     completion_percentage = (
#                         result["files_processed"] / result["total_files"]
#                     ) * 100
#                     st.write(f"✅ Completion: {completion_percentage:.1f}%")

#                 # Store in session state
#                 st.session_state.generated_docs = content
#                 st.session_state.doc_result = result

#             else:
#                 st.error(content)

#         # Documentation display section - moved to right column
#         if "generated_docs" in st.session_state and st.session_state.generated_docs:
#             st.subheader("📋 Generated Documentation")

#             # Create tabs for different views
#             tab1, tab2 = st.tabs(["📖 Preview", "📥 Download"])

#             with tab1:
#                 # Show a preview of the documentation (first 2000 characters)
#                 preview_text = st.session_state.generated_docs[:2000]
#                 if len(st.session_state.generated_docs) > 2000:
#                     preview_text += "\n\n... [Content truncated for preview. Download to see full documentation]"

#                 st.markdown(preview_text)

#             with tab2:
#                 # Download and clear options
#                 create_download_link(
#                     st.session_state.generated_docs, "documentation.md"
#                 )

#                 st.write("")  # Add some space

#                 if st.button("🗑️ Clear Documentation"):
#                     del st.session_state.generated_docs
#                     if "doc_result" in st.session_state:
#                         del st.session_state.doc_result
#                     st.rerun()

#     # Footer
#     st.markdown("---")
#     st.markdown("Built with ❤️ using PocketFlow and Streamlit")


# if __name__ == "__main__":
#     main()


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
    """Format duration in seconds only"""
    return f"{seconds:.1f}s"


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


def save_uploaded_files(uploaded_files, temp_dir):
    """Save uploaded files to temporary directory maintaining folder structure"""
    try:
        for uploaded_file in uploaded_files:
            # Create directory structure if needed
            file_path = os.path.join(temp_dir, uploaded_file.name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

        return True, f"Successfully saved {len(uploaded_files)} files"
    except Exception as e:
        return False, f"Error saving files: {str(e)}"


def extract_zip_file(zip_path, extract_to):
    """Extract zip file to directory"""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)
        return True, "Files extracted successfully"
    except Exception as e:
        return False, f"Error extracting zip: {str(e)}"


def find_project_root(extracted_path):
    """
    Intelligently find the actual project root in extracted ZIP.
    This handles cases where ZIP contains nested folders.
    """
    # Strategy 1: Look for common project indicators
    project_indicators = [
        "requirements.txt",
        "package.json",
        "pom.xml",
        "build.gradle",
        "Cargo.toml",
        "go.mod",
        "setup.py",
        "pyproject.toml",
        "composer.json",
        "Gemfile",
        "yarn.lock",
        "package-lock.json",
        ".gitignore",
        "README.md",
        "LICENSE",
        "Makefile",
        "Dockerfile",
    ]

    # Strategy 2: Look for source code directories
    source_dirs = ["src", "lib", "app", "components", "modules", "packages"]

    def score_directory(dir_path):
        """Score a directory based on how likely it is to be the project root"""
        score = 0

        if not os.path.isdir(dir_path):
            return 0

        files = os.listdir(dir_path)

        # Check for project indicators
        for indicator in project_indicators:
            if indicator in files:
                score += 10

        # Check for source directories
        for src_dir in source_dirs:
            if src_dir in files:
                score += 5

        # Check for code files in root
        code_extensions = [".py", ".js", ".java", ".cpp", ".go", ".rs", ".php", ".rb",]
        for file in files:
            if any(file.endswith(ext) for ext in code_extensions):
                score += 1

        # Penalty for being too nested (prefer shallower directories)
        depth = len(os.path.relpath(dir_path, extracted_path).split(os.sep))
        score -= depth * 2

        return score

    # Find all directories and score them
    candidates = []
    for root, dirs, files in os.walk(extracted_path):
        score = score_directory(root)
        candidates.append((root, score))

        # Don't go too deep
        if len(os.path.relpath(root, extracted_path).split(os.sep)) > 3:
            dirs.clear()

    # Sort by score and return the best candidate
    candidates.sort(key=lambda x: x[1], reverse=True)

    if candidates and candidates[0][1] > 0:
        return candidates[0][0]
    else:
        # Fallback: return the first non-empty directory or the extracted path itself
        for root, dirs, files in os.walk(extracted_path):
            if files:  # Directory with files
                return root
        return extracted_path


def should_include_file(file_path, include_patterns, exclude_patterns):
    """Check if file should be included based on patterns"""
    file_name = os.path.basename(file_path)
    # Normalize path separators for consistent matching
    relative_path = file_path.replace(os.path.sep, "/")

    # Check exclude patterns first (more specific matching)
    for pattern in exclude_patterns:
        # Handle different types of exclude patterns
        if pattern.endswith("/*"):
            # Directory pattern like "tests/*"
            dir_pattern = pattern[:-2]  # Remove "/*"
            if f"/{dir_pattern}/" in f"/{relative_path}" or relative_path.startswith(
                f"{dir_pattern}/"
            ):
                return False
        elif pattern.startswith("*") and pattern.endswith("*"):
            # Pattern like "*test*" - check if substring is in path
            substring = pattern[1:-1]  # Remove * from both ends
            if substring in relative_path:
                return False
        elif fnmatch.fnmatch(file_name, pattern):
            # Direct filename pattern match
            return False
        elif fnmatch.fnmatch(relative_path, pattern):
            # Direct path pattern match
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
        dirs_to_remove = []
        for d in dirs:
            dir_path = os.path.relpath(os.path.join(root, d), source_path)
            for pattern in exclude_patterns:
                if pattern.endswith("/*"):
                    dir_pattern = pattern[:-2]
                    if fnmatch.fnmatch(d, dir_pattern) or fnmatch.fnmatch(
                        dir_path, dir_pattern
                    ):
                        dirs_to_remove.append(d)
                        break

        for d in dirs_to_remove:
            dirs.remove(d)

        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, source_path)

            # Check if file should be included
            if should_include_file(relative_path, include_patterns, exclude_patterns):
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size <= max_size:
                        files_to_process.append(file_path)
                except OSError:
                    continue

    return files_to_process


def generate_project_structure(source_path, include_patterns, exclude_patterns):
    """Generate a string representation of project structure"""
    structure = []

    for root, dirs, files in os.walk(source_path):
        # Filter directories based on exclude patterns
        dirs_to_remove = []
        for d in dirs:
            dir_path = os.path.relpath(os.path.join(root, d), source_path)
            for pattern in exclude_patterns:
                if pattern.endswith("/*"):
                    dir_pattern = pattern[:-2]
                    if fnmatch.fnmatch(d, dir_pattern) or fnmatch.fnmatch(
                        dir_path, dir_pattern
                    ):
                        dirs_to_remove.append(d)
                        break

        for d in dirs_to_remove:
            dirs.remove(d)

        level = root.replace(source_path, "").count(os.sep)
        indent = " " * 2 * level
        structure.append(f"{indent}{os.path.basename(root)}/")

        # Add files
        subindent = " " * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, source_path)
            if should_include_file(relative_path, include_patterns, exclude_patterns):
                structure.append(f"{subindent}{file}")

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

        for i, file_path in enumerate(files_to_process[:files_to_process_count]):
            status_text.text(
                f"Processing file {i + 1}/{files_to_process_count}: {os.path.basename(file_path)}"
            )

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                relative_path = os.path.relpath(file_path, source_path)
                file_docs = generate_documentation_chunk(
                    content, relative_path, language
                )
                documentation_parts.append(
                    f"\n\n## File: {relative_path}\n\n{file_docs}"
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

        final_documentation = f"""# Project Documentation
 
{final_summary}
 
---
 
{chr(10).join(documentation_parts)}
 
---
 
## Processing Summary
- Total files found: {total_files}
- Files processed: {files_to_process_count}
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

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

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

        # Show estimated processing time (simplified)
        estimated_time_per_file = 15  # seconds per file (rough estimate)
        estimated_total_time = max_files_to_process * estimated_time_per_file
        st.info(
            f"⏱️ Estimated processing time: ~{format_duration(estimated_total_time)}"
        )

        # FIXED: Better default exclude patterns
        include_patterns_text = st.text_area(
            "Include Patterns (one per line)",
            value="*.py\n*.js\n*.tsx\n*.jsx\n*.java\n*.cpp\n*.h\n*.md\n*.rst",
            height=100,
        )
        include_patterns = [
            p.strip() for p in include_patterns_text.strip().split("\n") if p.strip()
        ]

        exclude_patterns_text = st.text_area(
            "Exclude Patterns (one per line)",
            value="tests/*\n*test*\n*.min.js\nnode_modules/*\n__pycache__/*\nvenv/*\n.venv/*\n.git/*\ndist/*\nbuild/*\n*.log\n*.tmp",
            height=100,
        )
        exclude_patterns = [
            p.strip() for p in exclude_patterns_text.strip().split("\n") if p.strip()
        ]

    # Main content area - Two columns for input and generation
    main_col1, main_col2 = st.columns([1, 1])

    with main_col1:
        st.header("📂 Input Source")

        # Input method selection
        input_method = st.radio(
            "Choose input method:",
            [
                "GitHub Repository",
                "Upload Single File",
                "Upload Folder",
                "Upload ZIP File",
            ],
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

        elif input_method == "Upload Single File":
            uploaded_file = st.file_uploader(
                "Choose a file",
                type=[
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
                ],
            )

            if uploaded_file is not None:
                temp_dir = tempfile.mkdtemp()
                success, message = save_uploaded_files([uploaded_file], temp_dir)
                if success:
                    st.success(f"File uploaded: {uploaded_file.name}")
                    source_path = temp_dir
                    st.session_state.source_path = source_path
                else:
                    st.error(message)

        elif input_method == "Upload Folder":
            st.info("📁 Upload multiple files to create a folder structure")
            st.markdown("""
            **Instructions:**
            1. Select multiple files from your project folder
            2. You can select files from different subdirectories
            3. The app will maintain the folder structure based on file names
            4. Use files with clear paths (e.g., `src/main.py`, `tests/test_main.py`)
            """)

            uploaded_files = st.file_uploader(
                "Choose files from your project folder",
                type=[
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
                    "json",
                    "xml",
                    "html",
                    "css",
                    "scss",
                    "less",
                    "ts",
                    "vue",
                    "swift",
                    "kt",
                    "scala",
                    "r",
                    "m",
                    "mm",
                    "sh",
                    "bat",
                ],
                accept_multiple_files=True,
            )

            if uploaded_files:
                temp_dir = tempfile.mkdtemp()
                success, message = save_uploaded_files(uploaded_files, temp_dir)
                if success:
                    st.success(f"Successfully uploaded {len(uploaded_files)} files")
                    source_path = temp_dir
                    st.session_state.source_path = source_path

                    # Show uploaded files structure
                    st.subheader("📁 Uploaded Files Structure")
                    for uploaded_file in uploaded_files:
                        st.write(f"📄 {uploaded_file.name}")

                    # Show actual directory structure
                    st.subheader("📂 Directory Structure")
                    for root, dirs, files in os.walk(temp_dir):
                        level = root.replace(temp_dir, "").count(os.sep)
                        indent = " " * 2 * level
                        folder_name = (
                            os.path.basename(root) if os.path.basename(root) else "root"
                        )
                        st.write(f"{indent}{folder_name}/")
                        subindent = " " * 2 * (level + 1)
                        for file in files:
                            st.write(f"{subindent}{file}")
                else:
                    st.error(message)

        elif input_method == "Upload ZIP File":
            st.info("📦 Upload a ZIP file containing your project")
            st.markdown("""
            **Features:**
            - 🧠 **Smart Root Detection**: Automatically finds your project's actual root folder
            - 📁 **Handles Nested Folders**: Works even if your ZIP has extra wrapper folders
            - 🔍 **Project Intelligence**: Looks for `package.json`, `requirements.txt`, `README.md`, etc.
            - 📊 **Shows Structure**: Displays both extracted and detected project structure
            """)

            uploaded_zip = st.file_uploader(
                "Choose a ZIP file containing your project", type=["zip"]
            )

            if uploaded_zip is not None:
                temp_dir = tempfile.mkdtemp()
                zip_path = os.path.join(temp_dir, uploaded_zip.name)

                # Save the ZIP file
                with open(zip_path, "wb") as f:
                    f.write(uploaded_zip.getbuffer())

                # Extract the ZIP file
                extract_dir = os.path.join(temp_dir, "extracted")
                success, message = extract_zip_file(zip_path, extract_dir)

                if success:
                    st.success(f"ZIP file uploaded and extracted: {uploaded_zip.name}")

                    # Find the actual project root using intelligent detection
                    project_root = find_project_root(extract_dir)
                    source_path = project_root
                    st.session_state.source_path = source_path

                    # Show extraction results in a more compact way
                    st.subheader("📦 Extraction Results")

                    # Detected project root
                    relative_root = os.path.relpath(project_root, extract_dir)
                    if relative_root == ".":
                        st.write("✅ Project root: **Root directory**")
                    else:
                        st.write(f"✅ Project root: **{relative_root}**")

                    # Show project structure (limited depth)
                    st.write("**Project structure:**")
                    for root, dirs, files in os.walk(project_root):
                        level = root.replace(project_root, "").count(os.sep)
                        if level > 2:  # Limit depth for display
                            continue
                        indent = " " * 2 * level
                        folder_name = (
                            os.path.basename(root)
                            if os.path.basename(root)
                            else "project"
                        )
                        st.write(f"{indent}{folder_name}/")
                        subindent = " " * 2 * (level + 1)
                        for file in files[:3]:  # Show first 3 files
                            st.write(f"{subindent}{file}")
                        if len(files) > 3:
                            st.write(f"{subindent}... and {len(files) - 3} more files")

                    # Show project indicators found
                    project_indicators = [
                        "requirements.txt",
                        "package.json",
                        "pom.xml",
                        "build.gradle",
                        "Cargo.toml",
                        "go.mod",
                        "setup.py",
                        "pyproject.toml",
                        "composer.json",
                        "Gemfile",
                        "yarn.lock",
                        "package-lock.json",
                        ".gitignore",
                        "README.md",
                        "LICENSE",
                        "Makefile",
                        "Dockerfile",
                    ]

                    found_indicators = []
                    if os.path.exists(project_root):
                        for indicator in project_indicators:
                            if os.path.exists(os.path.join(project_root, indicator)):
                                found_indicators.append(indicator)

                    if found_indicators:
                        st.subheader("🎯 Project Indicators Found")
                        st.write("Files that helped identify the project root:")
                        for indicator in found_indicators:
                            st.write(f"✅ {indicator}")

                else:
                    st.error(message)

    with main_col2:
        st.header("🚀 Documentation Generation")

        # Use source_path from session state if available
        if "source_path" in st.session_state:
            source_path = st.session_state.source_path

        if source_path and st.button("📄 Generate Documentation"):
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
                    # Success metrics
                    st.write("**Processing Summary:**")
                    st.write(f"📁 Files Processed: {result['files_processed']}")
                    st.write(f"📊 Total Files Found: {result['total_files']}")
                    st.write(
                        f"⏱️ Processing Time: {format_duration(result['processing_time'])}"
                    )
                    completion_percentage = (
                        result["files_processed"] / result["total_files"]
                    ) * 100
                    st.write(f"✅ Completion: {completion_percentage:.1f}%")

                # Store in session state
                st.session_state.generated_docs = content
                st.session_state.doc_result = result

            else:
                st.error(content)

        # Show status if documentation exists
        if "generated_docs" in st.session_state and st.session_state.generated_docs:
            st.success("✅ Documentation ready - scroll down to view!")

    # Full-width documentation display section at the bottom
    if "generated_docs" in st.session_state and st.session_state.generated_docs:
        st.markdown("---")
        st.header("📋 Generated Documentation")

        # Create tabs for different views
        tab1, tab2 = st.tabs(["📖 Full Preview", "📥 Download & Actions"])

        with tab1:
            # Show the full documentation
            st.markdown(st.session_state.generated_docs)

        with tab2:
            # Download and clear options
            st.subheader("📥 Download Documentation")
            create_download_link(st.session_state.generated_docs, "documentation.md")

            st.subheader("🔧 Actions")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("🗑️ Clear Documentation"):
                    del st.session_state.generated_docs
                    if "doc_result" in st.session_state:
                        del st.session_state.doc_result
                    st.rerun()

            with col2:
                if st.button("🔄 Generate New Documentation"):
                    if "source_path" in st.session_state:
                        # Clear existing docs and rerun
                        if "generated_docs" in st.session_state:
                            del st.session_state.generated_docs
                        if "doc_result" in st.session_state:
                            del st.session_state.doc_result
                        st.rerun()

    # Footer
    st.markdown("---")
    st.markdown("Built with ❤️ using PocketFlow and Streamlit")


if __name__ == "__main__":
    main()
