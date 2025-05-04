import PyPDF2
import sys

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file"""
    try:
        with open(pdf_path, "rb") as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pages = len(pdf_reader.pages)
            print(f"PDF has {total_pages} pages")
            
            for page_num in range(min(3, total_pages)):  # Extract only first 3 pages for test
                try:
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    print(f"Page {page_num+1} extracted successfully ({len(text)} characters)")
                    print(f"Sample text: {text[:100]}...\n")
                except Exception as page_error:
                    print(f"Error extracting page {page_num+1}: {str(page_error)}")
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "attached_assets/Standard-9.pdf"
    print(f"Testing PDF extraction on: {pdf_path}")
    extract_text_from_pdf(pdf_path)