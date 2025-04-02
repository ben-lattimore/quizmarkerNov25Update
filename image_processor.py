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
        
        # Parse and return the response
        result = json.loads(response.choices[0].message.content)
        return result
    
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
            
            # Extract text from the image
            extraction_result = extract_text_from_image(image_path)
            
            # Add to results with image identifier
            results.append({
                "image_id": i + 1,
                "filename": filename,
                "data": extraction_result
            })
            
        except Exception as e:
            # Log the error and add failed result
            logging.error(f"Error processing image {image_path}: {e}")
            results.append({
                "image_id": i + 1,
                "filename": os.path.basename(image_path),
                "error": str(e)
            })
    
    return results
