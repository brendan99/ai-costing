from neo4j import GraphDatabase
import os

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "password")
database = os.getenv("NEO4J_DATABASE", "neo4j")

disbursement_params = {
    "case_id": "f135136b-8cc7-41bc-b8b9-7f29ce82ba67",
    "disbursement_id": "85955fe5-ce05-4c3f-a6b9-d6b980085927",
    "date_incurred": "2025-06-08",
    "disbursement_type": "Other",
    "status": "Pending",
    "description": "Other on 2025-06-08",
    "payee_name": "Blackstone & Partners LLP",
    "amount_net_gbp": 0.0,
    "vat_gbp": 0.0,
    "amount_gross_gbp": 0.0,
    "is_recoverable": True,
    "voucher_document_id": None,
    "bill_item_number": None,
    "disputed": False,
    "dispute_reason": None
}

def main():
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database=database) as session:
        try:
            print("Checking if case exists...")
            case = session.run("MATCH (c:Case {case_id: $case_id}) RETURN c", {"case_id": disbursement_params["case_id"]}).single()
            if not case:
                print("Case not found!")
                return
            print("Case found. Attempting to create disbursement...")
            result = session.run(
                """
                MATCH (c:Case {case_id: $case_id})
                CREATE (d:Disbursement {
                  disbursement_id: $disbursement_id,
                  case_id: $case_id,
                  date_incurred: date($date_incurred),
                  disbursement_type: $disbursement_type,
                  status: $status,
                  description: $description,
                  payee_name: $payee_name,
                  amount_net_gbp: $amount_net_gbp,
                  vat_gbp: $vat_gbp,
                  amount_gross_gbp: $amount_gross_gbp,
                  is_recoverable: $is_recoverable,
                  voucher_document_id: $voucher_document_id,
                  bill_item_number: $bill_item_number,
                  disputed: $disputed,
                  dispute_reason: $dispute_reason
                })
                CREATE (c)-[:HAS_DISBURSEMENT]->(d)
                RETURN d.disbursement_id as disbursement_id
                """,
                disbursement_params
            )
            record = result.single()
            if record:
                print("Disbursement created! ID:", record["disbursement_id"])
            else:
                print("No record returned. Disbursement not created.")
        except Exception as e:
            print("Exception occurred:", e)
        finally:
            driver.close()

if __name__ == "__main__":
    main() 