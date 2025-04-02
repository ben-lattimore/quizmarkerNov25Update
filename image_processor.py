import os
import base64
import json
import logging
from openai import OpenAI

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user

# Configure OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

def encode_image_to_base64(image_path):
    """Convert an image file to base64 encoding"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_text_from_image(image_path):
    """Extract text from an image using GPT-4o vision"""
    try:
        # Encode the image to base64
        base64_image = encode_image_to_base64(image_path)
        logging.info(f"Successfully encoded image: {os.path.basename(image_path)}")
        
        # Create the API request to GPT-4o
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
            max_tokens=1500
        )
        
        # Extract the content from the response
        content = response.choices[0].message.content
        logging.info(f"Received response for image: {os.path.basename(image_path)}")
        
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
                    
            return result
            
        except json.JSONDecodeError as json_err:
            logging.error(f"Failed to parse JSON response: {json_err}")
            raise ValueError(f"Invalid JSON response: {str(json_err)}")
    
    except Exception as e:
        logging.error(f"Error extracting text from image {image_path}: {e}")
        raise Exception(f"Failed to process image: {str(e)}")

def process_images(image_paths):
    """Process a list of images and extract text from each"""
    results = []
    
    for i, image_path in enumerate(image_paths):
        try:
            # Get the filename for identification
            filename = os.path.basename(image_path)
            logging.info(f"Processing image {i+1}/{len(image_paths)}: {filename}")
            
            try:
                # Extract text from the image - process one at a time
                extraction_result = extract_text_from_image(image_path)
                
                # Verify JSON structure - this helps catch malformed responses
                if not isinstance(extraction_result, dict):
                    raise ValueError("Invalid response format received")
                
                # Add to results with image identifier
                results.append({
                    "image_id": i + 1,
                    "filename": filename,
                    "data": extraction_result
                })
                
                logging.info(f"Successfully processed image: {filename}")
                
            except Exception as extract_error:
                # Specific error for this image only
                logging.error(f"Error extracting text from image {filename}: {str(extract_error)}")
                results.append({
                    "image_id": i + 1,
                    "filename": filename,
                    "error": f"Failed to process image: {str(extract_error)}"
                })
        
        except Exception as e:
            # Critical error handling for the entire image
            logging.error(f"Critical error with image {i+1}: {str(e)}")
            results.append({
                "image_id": i + 1,
                "filename": os.path.basename(image_path) if image_path else f"unknown-{i+1}",
                "error": f"Processing error: {str(e)}"
            })
    
    # Return whatever results we have managed to collect
    return results
