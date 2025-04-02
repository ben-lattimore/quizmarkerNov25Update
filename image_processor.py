import os
import base64
import json
import time
import logging
import traceback
from openai import OpenAI, APITimeoutError, RateLimitError, BadRequestError

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user

# Configure OpenAI client with timeout and connection settings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
timeout_settings = 90.0  # 90 seconds timeout for API calls
max_retries = 2  # Try up to 3 times total (1 initial + 2 retries)
retry_delay = 2  # Wait 2 seconds between retries
api_timeout_error_msg = "OpenAI API request timed out. The service might be experiencing high load."

# Initialize OpenAI client with improved timeout settings
openai = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=timeout_settings,
    max_retries=max_retries
)

def encode_image_to_base64(image_path):
    """Convert an image file to base64 encoding"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image {image_path}: {e}")
        raise ValueError(f"Failed to encode image: {str(e)}")

def extract_text_from_image(image_path, max_attempts=3):
    """
    Extract text from an image using GPT-4o vision with retry logic
    
    Args:
        image_path: Path to the image file
        max_attempts: Maximum number of API call attempts
    """
    attempt = 0
    last_error = None
    
    # Log basic information for this processing request
    filename = os.path.basename(image_path)
    file_size = os.path.getsize(image_path) / 1024  # Size in KB
    logging.info(f"Processing image: {filename} ({file_size:.1f} KB)")
    
    while attempt < max_attempts:
        attempt += 1
        try:
            logging.info(f"API attempt {attempt}/{max_attempts} for {filename}")
            
            # Encode the image to base64
            base64_image = encode_image_to_base64(image_path)
            logging.info(f"Successfully encoded image: {filename}")
            
            # Make the API request with timeout handling
            start_time = time.time()
            
            # Get image file information for logging purposes
            img_size_kb = os.path.getsize(image_path) / 1024
            img_ext = os.path.splitext(image_path)[1]
            
            # Log these details for troubleshooting
            logging.info(f"Making API request for {filename} ({img_size_kb:.1f} KB, {img_ext})")
            
            try:
                # Use temperature=0 for more deterministic results
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a text extraction expert. Analyze the provided image and extract all visible text, carefully organizing it into structured categories.

Pay special attention to:
1. Titles or headers (often larger or bold text)
2. Main or lead text (the primary content or instructions)
3. Handwritten text (differentiate from printed text)
4. Informational text (footnotes, page numbers, references)
5. Questions, instructions, or prompts in the image

Format your response as a detailed JSON object with the following structure:
{
  "document_type": "brief description of what kind of document this is",
  "title": "the main title or header of the document",
  "subtitle": "any secondary title or identifier",
  "main_instructions": "primary instructions or lead text",
  "handwritten_content": "all handwritten text, accurately transcribed",
  "printed_content": "all machine-printed text not captured in other fields",
  "reference_info": "any reference numbers, page numbers, dates",
  "other_elements": "any other notable textual elements"
}"""
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": "Extract all text from this image and organize it into a structured JSON format. Carefully distinguish between different text elements (titles, instructions, handwritten text, etc.) and ensure each is properly categorized."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                }
                            ]
                        }
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=1500,
                    temperature=0
                )
            except Exception as api_err:
                # Specific handling for API errors with more details
                elapsed_time = time.time() - start_time
                logging.error(f"API error after {elapsed_time:.2f}s: {str(api_err)}")
                raise
            
            # Calculate and log API response time
            elapsed_time = time.time() - start_time
            logging.info(f"OpenAI API response received in {elapsed_time:.2f} seconds for {filename}")
            
            # Extract the content from the response
            content = response.choices[0].message.content
            
            # Verify the response is valid JSON and not empty
            if not content:
                raise ValueError("Empty response received from OpenAI")
                
            try:
                # Parse the JSON response
                result = json.loads(content)
                
                # Validate that we have a dictionary
                if not isinstance(result, dict):
                    raise ValueError("Response is not a valid JSON object")
                    
                # Check if we have at least some expected keys
                required_keys = ["document_type", "title", "handwritten_content", "printed_content"]
                missing_keys = [key for key in required_keys if key not in result]
                
                if missing_keys:
                    logging.warning(f"Response missing expected keys: {missing_keys}")
                    # Add empty values for missing keys to avoid frontend errors
                    for key in missing_keys:
                        result[key] = ""
                        
                # Success! Return the result
                logging.info(f"Successfully extracted text from {filename}")
                return result
                
            except json.JSONDecodeError as json_err:
                logging.error(f"Failed to parse JSON response: {json_err}")
                raise ValueError(f"Invalid JSON response: {str(json_err)}")
        
        except (APITimeoutError, RateLimitError) as timeout_err:
            # Handle timeout-specific errors
            last_error = timeout_err
            logging.warning(f"API timeout on attempt {attempt} for {filename}: {str(timeout_err)}")
            
            if attempt < max_attempts:
                # Calculate exponential backoff
                wait_time = retry_delay * (2 ** (attempt - 1))
                logging.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logging.error(f"Max retries ({max_attempts}) reached for {filename}")
                
        except BadRequestError as api_err:
            # Handle API-specific errors that won't benefit from retries
            last_error = api_err
            logging.error(f"Bad request error: {str(api_err)}")
            break  # Don't retry on bad requests
            
        except Exception as e:
            # General error handling
            last_error = e
            logging.error(f"Error on attempt {attempt} for {filename}: {e}")
            logging.debug(f"Traceback: {traceback.format_exc()}")
            
            if attempt < max_attempts:
                # Wait before retrying
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed after {max_attempts} attempts for {filename}")
    
    # If we got here, all attempts failed
    error_message = f"Failed to process image after {max_attempts} attempts: {str(last_error)}"
    logging.error(error_message)
    raise Exception(error_message)

def process_single_image(image_path, image_id=1):
    """Process a single image and extract text from it
    
    Args:
        image_path: Path to the image file
        image_id: Identifier for this image in the sequence
        
    Returns:
        A dictionary with the extraction results or error information
    """
    try:
        # Get the filename for identification
        filename = os.path.basename(image_path)
        
        try:
            # Extract text from the image
            extraction_result = extract_text_from_image(image_path)
            
            # Verify JSON structure - this helps catch malformed responses
            if not isinstance(extraction_result, dict):
                raise ValueError("Invalid response format received")
            
            # Return structured result
            return {
                "image_id": image_id,
                "filename": filename,
                "data": extraction_result
            }
            
        except Exception as extract_error:
            # Specific error for this image only
            logging.error(f"Error extracting text from image {filename}: {str(extract_error)}")
            return {
                "image_id": image_id,
                "filename": filename,
                "error": f"Failed to process image: {str(extract_error)}"
            }
    
    except Exception as e:
        # Critical error handling
        logging.error(f"Critical error with image {image_id}: {str(e)}")
        return {
            "image_id": image_id,
            "filename": os.path.basename(image_path) if image_path else f"unknown-{image_id}",
            "error": f"Processing error: {str(e)}"
        }

def process_images(image_paths):
    """Process a list of images and extract text from each
    
    This function processes images one at a time with delays between API calls.
    This helps prevent API rate limits and timeouts when processing multiple images.
    """
    results = []
    total_images = len(image_paths)
    
    logging.info(f"Starting to process {total_images} images")
    
    # If we have multiple images, warn about increased processing time
    if total_images > 1:
        logging.info(f"Processing {total_images} images sequentially to avoid API timeouts")
    
    for i, image_path in enumerate(image_paths):
        # Log progress for multiple images
        logging.info(f"Processing image {i+1} of {total_images}: {os.path.basename(image_path)}")
        
        # Process each image independently
        try:
            result = process_single_image(image_path, i + 1)
            results.append(result)
            
            # Add a delay between API calls to prevent rate limiting
            # Only add delay if we have more images to process
            if i < total_images - 1 and total_images > 1:
                delay_time = 2  # seconds between API calls
                logging.info(f"Adding {delay_time}s delay before processing next image")
                time.sleep(delay_time)
                
        except Exception as e:
            logging.error(f"Failed to process image {i+1}: {str(e)}")
            # Add error entry for this image
            results.append({
                "image_id": i + 1,
                "filename": os.path.basename(image_path),
                "error": f"Processing failed: {str(e)}"
            })
            # Continue with next image rather than failing the whole batch
            continue
    
    # Log completion
    success_count = sum(1 for r in results if "error" not in r)
    logging.info(f"Completed processing {success_count}/{total_images} images successfully")
    
    # Return whatever results we have managed to collect
    return results
