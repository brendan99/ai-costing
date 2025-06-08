import os
import sys
import logging
import argparse

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from src.graph.operations import Neo4jGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_all_cases():
    """List all cases in the database with their details."""
    graph_ops = Neo4jGraph()
    
    # Query to get all cases with their basic information
    query = """
    MATCH (c:Case)
    RETURN c.case_id as case_id,
           c.case_name as case_name,
           c.case_type as case_type,
           c.status as status,
           c.created_at as created_at,
           c.updated_at as updated_at
    ORDER BY c.created_at DESC
    """
    
    try:
        results = graph_ops.run_query(query)
        results = results.data() if hasattr(results, 'data') else list(results)
        logger.debug(f"Processed results: {results}")  # Log after processing
        if not results:
            logger.info("No cases found in the database.")
            return
            
        logger.info(f"Found {len(results)} cases in the database:")
        for case in results:
            logger.info("\nCase Details:")
            logger.info(f"ID: {case['case_id']}")
            logger.info(f"Name: {case['case_name']}")
            logger.info(f"Type: {case['case_type']}")
            logger.info(f"Status: {case['status']}")
            logger.info(f"Created: {case['created_at']}")
            logger.info(f"Updated: {case['updated_at']}")
            logger.info("-" * 50)
            
    except Exception as e:
        logger.error(f"Error listing cases: {str(e)}")

def get_case_by_reference(reference_number: str):
    """Retrieve and print a case by its reference number."""
    graph_ops = Neo4jGraph()
    query = """
    MATCH (c:Case {case_reference_number: $reference_number})
    RETURN c.case_id as case_id,
           c.case_name as case_name,
           c.case_type as case_type,
           c.status as status,
           c.created_at as created_at,
           c.updated_at as updated_at,
           c.case_reference_number as reference_number
    """
    results = graph_ops.run_query(query, {"reference_number": reference_number})
    results = results.data() if hasattr(results, 'data') else list(results)
    logger.debug(f"Processed results: {results}")  # Log after processing
    if not results:
        logger.info(f"No case found with reference number: {reference_number}")
        return
    case = results[0]
    logger.info("Case found:")
    logger.info(f"Reference: {case['reference_number']}")
    logger.info(f"ID: {case['case_id']}")
    logger.info(f"Name: {case['case_name']}")
    logger.info(f"Type: {case['case_type']}")
    logger.info(f"Status: {case['status']}")
    logger.info(f"Created: {case['created_at']}")
    logger.info(f"Updated: {case['updated_at']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List or retrieve cases from the database.")
    parser.add_argument('--reference', type=str, help='Case reference number to search for')
    args = parser.parse_args()
    if args.reference:
        get_case_by_reference(args.reference)
    else:
        list_all_cases() 