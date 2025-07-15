import os
import google.generativeai as genai
from google.generativeai import GenerationConfig
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize Gemini client
def initialize_gemini():
    """Initialize Gemini AI client"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")

    genai.configure(api_key=api_key)

    # Try different available models
    model_names = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro", "gemini-pro"]

    for model_name in model_names:
        try:
            model = genai.GenerativeModel(model_name)
            logger.info(f"Successfully initialized with model: {model_name}")
            return model
        except Exception as e:
            logger.warning(f"Failed to initialize {model_name}: {e}")
            continue

    raise ValueError("No available Gemini models found")


# Global client instance
try:
    client = initialize_gemini()
    logger.info("Gemini client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    client = None


def call_llm(prompt, max_tokens=4000, temperature=0.7, max_retries=3):
    """
    Call Gemini LLM with the given prompt

    Args:
        prompt (str): The input prompt
        max_tokens (int): Maximum tokens in response
        temperature (float): Temperature for response generation
        max_retries (int): Maximum number of retry attempts

    Returns:
        str: The generated response
    """
    if client is None:
        raise RuntimeError("Gemini client is not initialized")

    generation_config = GenerationConfig(
        max_output_tokens=max_tokens, temperature=temperature, top_p=0.8, top_k=40
    )

    for attempt in range(max_retries):
        try:
            response = client.generate_content(
                prompt, generation_config=generation_config
            )

            if response.text:
                return response.text.strip()
            else:
                logger.warning(f"Empty response on attempt {attempt + 1}")

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2**attempt)  # Exponential backoff
            else:
                raise RuntimeError(
                    f"Failed to get response after {max_retries} attempts: {e}"
                )

    raise RuntimeError("Failed to generate response")


def test_llm_connection():
    """Test the LLM connection"""
    try:
        test_prompt = (
            "Hello, please respond with 'Connection successful' if you can read this."
        )
        response = call_llm(test_prompt, max_tokens=50)
        logger.info("LLM connection test successful")
        return response
    except Exception as e:
        logger.error(f"LLM connection test failed: {e}")
        raise


def generate_documentation_chunk(code_content, file_path, language="English"):
    """
    Generate documentation for a code chunk

    Args:
        code_content (str): The code content to document
        file_path (str): Path to the file being documented
        language (str): Target language for documentation

    Returns:
        str: Generated documentation
    """
    prompt = f"""
    You are a technical documentation expert. Generate comprehensive documentation for the following code file.

    File: {file_path}
    Language: {language}

    Code:
    ```
    {code_content}
    ```

    Please provide:
    1. A brief overview of what this code does
    2. Key functions/classes and their purposes
    3. Important variables and their roles
    4. Dependencies and imports
    5. Usage examples where applicable
    6. Any important notes or considerations

    Format the response in clear, well-structured Markdown.
    """

    return call_llm(prompt, max_tokens=3000)


def generate_project_overview(project_structure, language="English"):
    """
    Generate a project overview based on the structure

    Args:
        project_structure (str): String representation of project structure
        language (str): Target language for documentation

    Returns:
        str: Generated project overview
    """
    prompt = f"""
    You are a technical documentation expert. Generate a comprehensive project overview based on the following project structure.

    Language: {language}

    Project Structure:
    {project_structure}

    Please provide:
    1. Project overview and purpose
    2. Architecture and organization
    3. Key components and their relationships
    4. Technology stack and dependencies
    5. Getting started guide
    6. Important files and directories explanation

    Format the response in clear, well-structured Markdown with proper headers and sections.
    """

    return call_llm(prompt, max_tokens=4000)


def generate_summary(documentation_parts, language="English"):
    """
    Generate a summary of all documentation parts

    Args:
        documentation_parts (list): List of documentation strings
        language (str): Target language for documentation

    Returns:
        str: Generated summary
    """
    combined_docs = "\n\n".join(documentation_parts)

    prompt = f"""
    You are a technical documentation expert. Create a comprehensive summary and table of contents for the following documentation.

    Language: {language}

    Documentation Content:
    {combined_docs}

    Please provide:
    1. Executive Summary
    2. Table of Contents
    3. Key Features and Components
    4. Quick Start Guide
    5. Architecture Overview

    Format the response in clear, well-structured Markdown.
    """

    return call_llm(prompt, max_tokens=2000)


def list_available_models():
    """List all available Gemini models"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        genai.configure(api_key=api_key)

        print("Available Gemini models:")
        for model in genai.list_models():
            if "generateContent" in model.supported_generation_methods:
                print(f"  - {model.name}")

    except Exception as e:
        print(f"Error listing models: {e}")


if __name__ == "__main__":
    # List available models first
    print("Listing available models...")
    list_available_models()
    print("\n" + "=" * 50 + "\n")

    # Test the LLM connection
    try:
        print("Testing LLM connection...")
        response = test_llm_connection()
        print(f"✅ Success: {response}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        print("\nPlease make sure:")
        print("1. You have set the GEMINI_API_KEY environment variable")
        print("2. Your API key is valid")
        print("3. You have internet connection")
