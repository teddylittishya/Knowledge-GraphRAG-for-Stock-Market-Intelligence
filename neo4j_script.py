import yfinance as yf
from neo4j import GraphDatabase

# Neo4j Configuration
NEO4J_URI = "bolt://localhost:7687"  # Replace with your Neo4j URI
NEO4J_USERNAME = "neo4j"             # Replace with your Neo4j username
NEO4J_PASSWORD = "prahar@156"          # Replace with your Neo4j password

# List of Nifty 50 company tickers
nifty_50_tickers = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS", "BEL.NS", "BHARTIARTL.NS",
    "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS",
    "INFY.NS", "ITC.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SHRIRAMFIN.NS",
    "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

def fetch_company_data():
    company_data_list = []

    for ticker in nifty_50_tickers:
        company = yf.Ticker(ticker)
        info = company.info

        # Prepare company details
        company_details = {
            "name": info.get("longName"),
            "short_name": info.get("shortName"),
            "symbol": info.get("symbol"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "address.line_1": info.get("address1"),
            "address.line_2": info.get("address2"),
            "address.city": info.get("city"),
            "address.zip": info.get("zip"),
            "address.country": info.get("country"),
            "contact.phone": info.get("phone"),
            "contact.fax": info.get("fax"),
            "contact.website": info.get("website"),
            "contact.ir_website": info.get("irWebsite"),
            "business_summary": info.get("longBusinessSummary")
        }

        # Prepare executives details
        executives = []
        for officer in info.get("companyOfficers", []):
            if officer.get("name"):
                executives.append({
                    "name": officer.get("name"),
                    "title": officer.get("title"),
                    "age": officer.get("age"),
                    "year_born": officer.get("yearBorn"),
                    "total_pay": officer.get("totalPay")
                })

        # Prepare governance risks
        governance_risks = {
            "audit_risk": info.get("auditRisk"),
            "board_risk": info.get("boardRisk"),
            "compensation_risk": info.get("compensationRisk"),
            "shareholder_rights_risk": info.get("shareHolderRightsRisk"),
            "overall_risk": info.get("overallRisk")
        }

        # Combine all data
        company_data_list.append({
            "details": company_details,
            "executives": executives,
            "risks": governance_risks
        })

    return company_data_list

def create_graph(session, company_data_list):
    for company in company_data_list:
        details = company["details"]
        executives = company["executives"]
        risks = company["risks"]

        # Create or update the Company node
        company_query = """
        MERGE (c:Company {symbol: $symbol})
        SET c.name = $name,
            c.short_name = $short_name,
            c.sector = $sector,
            c.industry = $industry,
            c.address = $address,
            c.phone = $phone,
            c.website = $website,
            c.business_summary = $summary
        """
        session.run(company_query, parameters={
            "symbol": details.get("symbol"),
            "name": details.get("name"),
            "short_name": details.get("short_name"),
            "sector": details.get("sector"),
            "industry": details.get("industry"),
            "address": ", ".join(filter(None, [
                details.get("address.line_1"),
                details.get("address.city"),
                details.get("address.country")
            ])),  # Combine address fields only if they are not empty
            "phone": details.get("contact.phone"),
            "website": details.get("contact.website"),
            "summary": details.get("business_summary")
        })

        # Create Executives and Relationships
        for exec_data in executives:
            # Add non-empty properties dynamically
            exec_query = """
            MERGE (e:Executive {name: $exec_name})
            SET e.title = $exec_title,
                e.age = $exec_age,
                e.year_born = $exec_year_born,
                e.total_pay = $exec_total_pay
            MERGE (c:Company {symbol: $company_symbol})
            MERGE (c)-[:MANAGED_BY]->(e)
            """
            session.run(exec_query, parameters={
                "exec_name": exec_data.get("name"),
                "exec_title": exec_data.get("title"),
                "exec_age": exec_data.get("age") if exec_data.get("age") is not None else None,
                "exec_year_born": exec_data.get("year_born") if exec_data.get("year_born") is not None else None,
                "exec_total_pay": exec_data.get("total_pay") if exec_data.get("total_pay") is not None else None,
                "company_symbol": details.get("symbol")
            })

        # Create Risks and Relationships
        for risk_name, risk_value in risks.items():
            if risk_value is not None:
                risk_query = """
                MERGE (r:Risk {type: $risk_type, value: $risk_value})
                MERGE (c:Company {symbol: $company_symbol})
                MERGE (c)-[:HAS_RISK]->(r)
                """
                session.run(risk_query, parameters={
                    "risk_type": risk_name,
                    "risk_value": risk_value,
                    "company_symbol": details.get("symbol")
                })

        # Insert additional details if available
        if details.get("address.zip"):
            zip_query = """
            MATCH (c:Company {symbol: $company_symbol})
            SET c.zip_code = $zip_code
            """
            session.run(zip_query, parameters={
                "company_symbol": details.get("symbol"),
                "zip_code": details.get("address.zip")
            })

def main():
    company_data_list = fetch_company_data()

    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    with driver.session() as session:
        create_graph(session, company_data_list)

    print("Graph created successfully in Neo4j.")
    driver.close()

if __name__ == "__main__":
    main()
