import os
import base64
import json
import time
import logging
import traceback
import httpx
try:
    from openai import OpenAI, APITimeoutError, RateLimitError, BadRequestError, APIError, APIConnectionError
except ImportError:
    # In case specific error types aren't available in the version
    from openai import OpenAI
    APITimeoutError = Exception
    RateLimitError = Exception
    BadRequestError = Exception
    APIError = Exception
    APIConnectionError = Exception

# User has requested to use "gpt-4.1-mini" instead of the default "gpt-4o" model
# This was changed from gpt-4o at the user's request

# Configure OpenAI client with improved timeout and connection settings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
timeout_settings = 90.0  # 90 seconds timeout for API calls (increased from 60s)
max_retries = 2  # Try up to 3 times total (1 initial + 2 retries)
retry_delay = 3  # Wait 3 seconds between retries (increased for more breathing room)

# Add detailed logging about API configuration
logging.info(f"OpenAI configuration: Timeout={timeout_settings}s, Retries={max_retries}, Delay={retry_delay}s")
api_timeout_error_msg = "OpenAI API request timed out. The service might be experiencing high load."

# Initialize OpenAI client with improved timeout settings
try:
    # Create a custom httpx client with specific timeout settings
    http_client = httpx.Client(
        timeout=httpx.Timeout(
            connect=10.0,  # connection timeout
            read=timeout_settings,  # read timeout
            write=10.0,  # write timeout
            pool=10.0  # pool timeout
        ),
        limits=httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        ),
        # Enable HTTP/2 for better performance with OpenAI API
        http2=True
    )
    
    # Initialize OpenAI client
    openai = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=timeout_settings,
        max_retries=max_retries,
        http_client=http_client
    )
    logging.info("OpenAI client initialized with custom HTTP client and timeout settings")
except Exception as client_init_error:
    logging.error(f"Error initializing OpenAI client with custom settings: {client_init_error}")
    # Fall back to default client if custom initialization fails and API key is set
    if OPENAI_API_KEY:
        openai = OpenAI(
            api_key=OPENAI_API_KEY
        )
        logging.info("Initialized OpenAI client with default settings due to error with custom settings")
    else:
        logging.warning("OPENAI_API_KEY not set. OpenAI functionality will be limited.")
        openai = None

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
    Extract text from an image using GPT-4.1-mini vision with retry logic
    
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
                    model="gpt-4.1-mini",
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

def prepare_grading_document(extracted_data, pdf_text, standard_num):
    """
    Prepare a single document with all answers for grading
    
    Args:
        extracted_data: List of dictionaries with extracted text data
        pdf_text: Reference text from the standard PDF
        standard_num: Standard number being graded
        
    Returns:
        A structured document for grading
    """
    # Create the document header with clear instructions
    document = f"""
    STANDARD {standard_num} ASSESSMENT GRADING
    ----------------------------------------
    
    REFERENCE MATERIAL FOR STANDARD {standard_num}:
    {pdf_text[:3000]}  # Truncate to reasonable size
    
    STUDENT ANSWERS TO GRADE:
    """
    
    # Add each answer with clear separation and numbering
    for i, item in enumerate(extracted_data):
        data = item.get('data', {})
        handwritten = data.get('handwritten_content', 'No content provided')
        filename = item.get('filename', f'Image {i+1}')
        
        # Clean up handwritten content if needed
        if isinstance(handwritten, dict):
            # If it's a dictionary, convert to string
            handwritten = json.dumps(handwritten)
        
        # Ensure it's not too long
        if len(handwritten) > 1000:
            handwritten = handwritten[:1000] + "... [content truncated]"
        
        document += f"""
    ----------------------------------------
    ANSWER {i+1} ({filename}):
    {handwritten}
    ----------------------------------------
    """
    
    return document

def grade_combined_document(document, standard_num, extracted_data):
    """
    Grade all answers in a single API call
    
    Args:
        document: Formatted document with all answers
        standard_num: Standard number being graded
        extracted_data: Original extraction data
        
    Returns:
        Dictionary with grading results
    """
    # Create a clear, concise prompt
    system_prompt = f"""
    You are grading student answers for Standard {standard_num} of healthcare training.
    Evaluate each answer based on accuracy, completeness, and understanding of the reference material.
    
    For EACH answer separately:
    1. Assign a score from 0-10
    2. Provide brief, constructive feedback (2-3 sentences maximum)
    
    Format your response as a JSON object with this exact structure:
    {{
      "answers": [
        {{
          "answer_number": 1,
          "score": 8,
          "feedback": "Good explanation of key concepts. Could include more about..."
        }},
        ...more answers...
      ]
    }}
    """
    
    # Make the API call with optimized settings
    logging.info(f"Making single API call to grade Standard {standard_num} document with {len(extracted_data)} answers")
    
    start_time = time.time()
    max_api_attempts = 2
    current_attempt = 0
    
    while current_attempt < max_api_attempts:
        current_attempt += 1
        try:
            logging.info(f"Combined grading API attempt {current_attempt}/{max_api_attempts}")
            
            response = openai.chat.completions.create(
                model="gpt-4.1-mini",  # Using requested model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": document}
                ],
                response_format={"type": "json_object"},
                max_tokens=3000,
                temperature=0
            )
            
            # Calculate response time
            elapsed_time = time.time() - start_time
            logging.info(f"OpenAI API response received in {elapsed_time:.2f} seconds for combined grading")
            
            # Parse the response
            content = response.choices[0].message.content
            
            # Verify the response is valid JSON and not empty
            if not content:
                raise ValueError("Empty response received from OpenAI")
                
            # Parse the JSON response
            grading_results = json.loads(content)
            
            # Transform into our expected format
            return transform_grading_results(grading_results, extracted_data)
            
        except (APITimeoutError, APIConnectionError, httpx.ReadTimeout) as timeout_error:
            elapsed_time = time.time() - start_time
            logging.error(f"API timeout after {elapsed_time:.2f}s: {str(timeout_error)}")
            
            # If not the last attempt, retry after a delay
            if current_attempt < max_api_attempts:
                retry_wait = 3 * current_attempt  # Incremental backoff
                logging.info(f"Waiting {retry_wait}s before retry...")
                time.sleep(retry_wait)
            else:
                # Last attempt failed
                logging.error(f"All {max_api_attempts} API attempts failed for combined grading")
                raise
        
        except Exception as e:
            logging.error(f"Error during combined grading: {str(e)}")
            raise
    
    # Should never reach here due to exceptions
    raise ValueError("Failed to grade answers after all attempts")

def transform_grading_results(grading_results, extracted_data):
    """
    Transform the combined grading results into our standard format
    
    Args:
        grading_results: Results from API call
        extracted_data: Original extraction data
        
    Returns:
        Results in our standard format
    """
    # Initialize our standard format
    standard_format = {
        "images": []
    }
    
    # Validate grading results
    if not isinstance(grading_results, dict):
        raise ValueError(f"Invalid grading results format: {type(grading_results)}")
        
    # Get the answers array
    answers = grading_results.get('answers', [])
    
    if not answers:
        logging.warning("No answers found in grading results")
        
    # For each answer, create an entry in our format
    for i, answer in enumerate(answers):
        # Safely get answer number (1-based)
        answer_number = answer.get('answer_number', i+1)
        # Adjust to 0-based index for lookup
        extract_index = answer_number - 1
        
        # Get original extracted data
        extract = extracted_data[extract_index] if extract_index < len(extracted_data) else {}
        data = extract.get('data', {})
        handwritten = data.get('handwritten_content', '')
        filename = extract.get('filename', f'image_{extract_index+1}.jpg')
        
        # Create the entry
        standard_format["images"].append({
            "filename": filename,
            "score": answer.get('score', 5),  # Default to 5 if missing
            "handwritten_content": handwritten,
            "feedback": answer.get('feedback', 'No feedback provided')
        })
    
    # Make sure we have entries for all extractions
    if len(standard_format["images"]) < len(extracted_data):
        logging.warning(f"Mismatch: {len(standard_format['images'])} graded answers vs {len(extracted_data)} extractions")
        # Add default entries for any missing answers
        for i in range(len(standard_format["images"]), len(extracted_data)):
            extract = extracted_data[i]
            data = extract.get('data', {})
            handwritten = data.get('handwritten_content', '')
            filename = extract.get('filename', f'image_{i+1}.jpg')
            
            standard_format["images"].append({
                "filename": filename,
                "score": 5,  # Default middle score
                "handwritten_content": handwritten,
                "feedback": "This answer received a default score as it was not included in the grading results."
            })
    
    return standard_format

def grade_answers(extracted_data, pdf_path):
    """
    Grade handwritten answers against a reference PDF
    
    Args:
        extracted_data: A list of dictionaries containing extracted text data
        pdf_path: Path to the reference PDF file
        
    Returns:
        A list of dictionaries with the graded results
    """
    try:
        standard_num = os.path.basename(pdf_path).replace("Standard-", "").replace(".pdf", "")
        logging.info(f"Starting grading process for {len(extracted_data)} uploaded images against Standard-{standard_num}")
        logging.info(f"PDF path: {pdf_path}, exists: {os.path.exists(pdf_path)}, size: {os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 'N/A'}")
        
        import PyPDF2
        
        # Extract text content from the PDF to use as reference material
        pdf_text = ""
        try:
            with open(pdf_path, "rb") as pdf_file:
                logging.info(f"Successfully opened PDF file: {pdf_path}")
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                total_pages = len(pdf_reader.pages)
                logging.info(f"PDF has {total_pages} pages")
                
                for page_num in range(total_pages):
                    try:
                        page = pdf_reader.pages[page_num]
                        page_text = page.extract_text()
                        pdf_text += page_text + "\n\n"
                        if page_num < 2 or page_num > total_pages - 3:
                            logging.debug(f"Page {page_num+1} extracted: {len(page_text)} chars")
                    except Exception as page_error:
                        logging.error(f"Error extracting page {page_num+1}: {str(page_error)}")
                    
            # Trim if too long to fit in prompt
            original_length = len(pdf_text)
            if original_length > 10000:
                pdf_text = pdf_text[:10000] + f"... (content truncated, original length: {original_length} chars)"
                
            logging.info(f"Successfully extracted {len(pdf_text)} characters from PDF (original: {original_length})")
            
            # Check if we actually got content
            if len(pdf_text.strip()) < 100:
                logging.warning(f"PDF text extraction yielded very little text ({len(pdf_text.strip())} chars)")
                
        except Exception as pdf_error:
            logging.error(f"Error extracting PDF text: {pdf_error}")
            logging.error(f"PDF error traceback: {traceback.format_exc()}")
            pdf_text = f"[Error extracting PDF content: {str(pdf_error)}]"
        
        # Determine which standard we're grading against
        standard_num = os.path.basename(pdf_path).replace("Standard-", "").replace(".pdf", "")
        logging.info(f"Grading against Standard {standard_num}")
        
        # Try the new combined grading approach
        try:
            # Prepare the single document with all answers for combined grading
            document = prepare_grading_document(extracted_data, pdf_text, standard_num)
            
            # Log document length for debugging
            logging.info(f"Prepared combined document with {len(document)} characters")
            
            # Grade the document in a single API call
            logging.info(f"Using new combined grading approach for Standard {standard_num}")
            return grade_combined_document(document, standard_num, extracted_data)
            
        except Exception as combined_error:
            # Log the error
            logging.error(f"Combined grading approach failed: {str(combined_error)}")
            logging.error(f"Falling back to original approach for Standard {standard_num}")
            
            # Continue with original approach below as fallback
        
        # Original approach (fallback if combined approach fails)
        # Convert the extracted_data to a formatted string for the prompt
        extraction_json = json.dumps(extracted_data, indent=2)
        
        # Add special handling for Standard-9, which may have issues
        standard_nine_desc = ""
        # For Standard 9, always add our fallback content regardless of extraction success
        if standard_num == "9":
            logging.warning("Standard 9 detected - using guaranteed fallback content")
            standard_nine_desc = """
Standard 9: Mental Health, Dementia and Learning Disabilities

Key learning points:
- Understanding the needs of people with mental health conditions, dementia, and learning disabilities
- Recognizing signs of mental health conditions like depression, anxiety, and psychosis
- Understanding how to support individuals with dementia and learning disabilities
- Promoting positive attitudes and reducing stigma
- Person-centered approaches to care
- Supporting independence and encouraging active participation
- The importance of early detection and intervention
- Understanding legal frameworks including Mental Capacity Act

Mental health conditions can affect:
- How a person thinks, feels, and behaves
- Their ability to handle daily activities and challenges
- Their relationships with others

Dementia is not a single illness but a group of symptoms caused by different diseases affecting the brain, including:
- Memory loss and confusion
- Difficulty with communication and language
- Reduced ability to problem-solve

Learning disabilities affect the way a person:
- Understands information
- Learns new skills
- Communicates with others
- May need additional support with daily activities
"""
            # Always use our fallback content for Standard 9 to ensure consistency
            pdf_text = standard_nine_desc
            
            logging.info(f"Using guaranteed Standard 9 fallback content, pdf_text now {len(pdf_text)} chars")
        
        # Construct a prompt based on the specific standard
        prompt = f"""You are an expert in grading handwritten answers against reference materials. 

I'll provide you with:
1. JSON data containing extracted text from images, with handwritten answers in the "handwritten_content" field
2. The content from Standard {standard_num} from The Care Certificate (included below)

You are grading answers specifically against the content from Standard {standard_num} only, not any other standard.

REFERENCE MATERIAL FROM STANDARD {standard_num}:
{pdf_text}

Your task:
- Evaluate each handwritten answer against this reference material
- For each answer with handwritten content, determine if it's correct, partially correct, or incorrect
- Assign a score out of 10 for each entry
- Provide brief feedback explaining why points were awarded or deducted

Format your response as a JSON object with:
- An "images" array containing details for each image
- For each image, include: filename, score, handwritten_content, and feedback

Here's the extracted JSON data containing handwritten answers:
{extraction_json}
"""
        
        logging.info("Making API request to grade answers")
        
        # Call the OpenAI API
        start_time = time.time()
        
        max_api_attempts = 2
        current_attempt = 0
        while current_attempt < max_api_attempts:
            current_attempt += 1
            try:
                logging.info(f"Grading API attempt {current_attempt}/{max_api_attempts} for Standard {standard_num}")
                
                # Optimization for Standard 9 to prevent issues
                if standard_num == '9':
                    # Special shorter system prompt
                    system_prompt = "Grade handwritten answers against the reference material provided."
                    # Consider reducing tokens further if needed
                    max_tokens_value = 2500
                    logging.info(f"Using optimized settings for Standard 9: shorter system prompt and {max_tokens_value} max tokens")
                else:
                    # Normal system prompt for other standards
                    system_prompt = "You are an expert grading system for educational assessments. Grade handwritten answers against reference materials with fairness and accuracy."
                    max_tokens_value = 4000
                
                # Using gpt-4.1-mini as requested by the user 
                # Changed from gpt-4o to gpt-4.1-mini per user request
                response = openai.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt + "\n\nNote: The PDF content has been included in this prompt text since we need to reference it."
                                }
                            ]
                        }
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens_value,
                    temperature=0
                )
                # If we get here, the API call succeeded
                break
                
            except (APITimeoutError, APIConnectionError, httpx.ReadTimeout, httpx.ConnectTimeout) as timeout_error:
                elapsed_time = time.time() - start_time
                logging.error(f"API timeout after {elapsed_time:.2f}s: {str(timeout_error)}")
                
                # If not the last attempt, retry after a delay
                if current_attempt < max_api_attempts:
                    retry_wait = 3 * current_attempt  # Incremental backoff
                    logging.info(f"Waiting {retry_wait}s before retry...")
                    time.sleep(retry_wait)
                else:
                    # Last attempt failed
                    logging.error(f"All {max_api_attempts} API attempts failed for grading Standard {standard_num}")
                    # Special handling for Standard 9
                    if standard_num == '9':
                        raise APIConnectionError(f"Could not connect to OpenAI API after {max_api_attempts} attempts: {str(timeout_error)}")
                    else:
                        raise
            
            except Exception as api_err:
                elapsed_time = time.time() - start_time
                logging.error(f"API error after {elapsed_time:.2f}s: {str(api_err)}")
                # For non-timeout errors, don't retry
                raise
        
        # Calculate and log API response time
        elapsed_time = time.time() - start_time
        logging.info(f"OpenAI API response received in {elapsed_time:.2f} seconds for grading")
        
        # Extract the grading results from the response
        content = response.choices[0].message.content
        
        # Verify the response is valid JSON and not empty
        if not content:
            raise ValueError("Empty response received from OpenAI")
            
        try:
            # Parse the JSON response
            grading_results = json.loads(content)
            
            # Return the grading results
            logging.info(f"Successfully graded {len(extracted_data)} answers")
            return grading_results
            
        except json.JSONDecodeError as json_err:
            logging.error(f"Failed to parse JSON response: {json_err}")
            raise ValueError(f"Invalid JSON response: {str(json_err)}")
    
    except Exception as e:
        logging.error(f"Error during grading process: {e}")
        logging.debug(f"Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to grade answers: {str(e)}")
