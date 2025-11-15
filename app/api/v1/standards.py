"""
Standards API endpoints

Handles listing available Care Certificate standards
"""

import os
import logging
from flask import jsonify, current_app

from app.api.v1 import api_v1_bp

logger = logging.getLogger(__name__)


@api_v1_bp.route('/standards', methods=['GET'])
def get_standards():
    """
    Get list of available Care Certificate standards

    Response JSON:
        {
            "success": true,
            "data": [
                {
                    "id": int,
                    "name": "string",
                    "file": "string"
                }
            ]
        }
    """
    try:
        reference_pdf_dir = current_app.config.get('REFERENCE_PDF_DIR', 'attached_assets')
        available_standards = []

        # Look for files matching the pattern "Standard-*.pdf"
        if os.path.exists(reference_pdf_dir):
            for file in os.listdir(reference_pdf_dir):
                if file.startswith("Standard-") and file.endswith(".pdf"):
                    # Extract the standard number from the filename
                    standard_num = file.replace("Standard-", "").replace(".pdf", "")
                    try:
                        standard_num = int(standard_num)
                        available_standards.append({
                            "id": standard_num,
                            "name": f"Standard {standard_num}",
                            "file": file
                        })
                    except ValueError:
                        # Skip files if the numbering isn't an integer
                        logger.warning(f"Skipping non-integer standard file: {file}")
                        continue

            # Sort standards by their number
            available_standards.sort(key=lambda s: s["id"])

            logger.info(f"Found {len(available_standards)} available standards")

            return jsonify({
                "success": True,
                "data": available_standards
            }), 200
        else:
            logger.error(f"Reference PDF directory not found: {reference_pdf_dir}")
            return jsonify({
                "success": False,
                "error": "Standards directory not found",
                "code": "DIRECTORY_NOT_FOUND"
            }), 500

    except Exception as e:
        logger.error(f"Error getting standards: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Failed to get standards",
            "code": "STANDARDS_ERROR"
        }), 500
