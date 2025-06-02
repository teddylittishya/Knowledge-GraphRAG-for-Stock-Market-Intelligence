import sys
import datetime
import hashlib
import hmac
import requests
import json
import os
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import ReadOnlyCredentials
from types import SimpleNamespace
import yfinance as yf

# Configuration. https is required.
protocol = 'https'

# AWS Credentials
access_key = os.getenv('AWS_ACCESS_KEY_ID', '')
secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
region = os.getenv('SERVICE_REGION', '')

# AWS_SESSION_TOKEN is optional
session_token = os.getenv('AWS_SESSION_TOKEN', '')

# Specific hostname for Amazon Neptune
DEFAULT_HOSTNAME = "db-neptune-1-instance-1.chccae2wwzh9.us-east-1.neptune.amazonaws.com:8182"  # Replace with your Neptune hostname

# Predefined Neptune query parameters
DEFAULT_METHOD = "POST"
DEFAULT_QUERY_TYPE = "gremlin"

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

def validate_input(method, query_type):
    if method not in ['GET', 'POST']:
        print('Method must be "GET" or "POST", but is "' + method + '".')
        sys.exit()

def get_canonical_uri_and_payload(query_type, query, method):
    if query_type == 'gremlin':
        canonical_uri = '/gremlin/'
        payload = {'gremlin': query}
        if method == 'POST':
            payload = json.dumps(payload)
    else:
        print('Invalid query_type: "' + query_type + '".')
        sys.exit()
    return canonical_uri, payload

def make_signed_request(host, method, query_type, query):
    service = 'neptune-db'
    endpoint = protocol + '://' + host

    print('+++++ REQUEST DETAILS +++++')
    print(f'Host: {host}')
    print(f'Method: {method}')
    print(f'Query Type: {query_type}')
    print(f'Query: {query}')

    validate_input(method, query_type)

    canonical_uri, payload = get_canonical_uri_and_payload(query_type, query, method)
    data = payload if method == 'POST' else None
    params = payload if method == 'GET' else None

    request_url = endpoint + canonical_uri
    creds = SimpleNamespace(
        access_key=access_key, secret_key=secret_key, token=session_token, region=region,
    )

    request = AWSRequest(method=method, url=request_url, data=data, params=params)
    SigV4Auth(creds, service, region).add_auth(request)

    if method == 'POST':
        print('++++ BEGIN POST REQUEST +++++')
        print('Request URL = ' + request_url)
        request.headers['Content-type'] = 'application/json'
        r = requests.post(request_url, headers=request.headers, verify=False, data=data)
    else:
        print('Invalid method.')

    if r:
        print('+++++ RESPONSE +++++')
        print(f'Response Code: {r.status_code}')
        print(r.text)
        r.close()
        return r.text

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
        for i, officer in enumerate(info.get("companyOfficers", [])):
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

def generate_gremlin_queries(company_data_list):
    queries = []
    for company in company_data_list:
        details = company["details"]
        executives = company["executives"]
        risks = company["risks"]

        # Start building the query with the company vertex
        query = f"g.addV('Company').property('name', '{details['name']}')"

        # Add sector and industry
        if details.get("sector"):
            query += f".addV('Sector').property('name', '{details['sector']}')" \
                     f".addE('belongs_to').from(__.V().has('name', '{details['name']}'))"
        if details.get("industry"):
            query += f".addV('Industry').property('name', '{details['industry']}')" \
                     f".addE('classified_as').from(__.V().has('name', '{details['name']}'))"

        # Add executives
        for executive in executives:
            exec_name = executive.get('name')
            exec_title = executive.get('title')
            exec_age = executive.get('age')
            exec_pay = executive.get('total_pay')

            if exec_name and exec_title:
                exec_query = f".addV('Executive').property('name', '{exec_name}').property('title', '{exec_title}')"
                if exec_age is not None:  # Only add age if it has a value
                    exec_query += f".property('age', {exec_age})"
                if exec_pay is not None:  # Only add total_pay if it has a value
                    exec_query += f".property('total_pay', {exec_pay})"
                exec_query += f".addE('managed_by').from(__.V().has('name', '{details['name']}'))"
                query += exec_query

        # Add governance risks
        for risk_name, risk_value in risks.items():
            if risk_value is not None:  # Only add risks with valid values
                query += f".addV('Risk').property('type', '{risk_name}').property('value', {risk_value})" \
                         f".addE('has_risk').from(__.V().has('name', '{details['name']}'))"

        queries.append(query.strip())

    return queries

def main():
    # Validate AWS credentials
    if not access_key or not secret_key or not region:
        print("AWS credentials or region not set. Ensure environment variables are properly configured.")
        sys.exit()

    # Fetch company data
    company_data_list = fetch_company_data()

    # Generate Gremlin queries
    gremlin_queries = generate_gremlin_queries(company_data_list)

    # print(f"Generated Gremlin Queries: {gremlin_queries}")

    # # Push data to Neptune
    for query in gremlin_queries:
        print("Executing Gremlin Query:")
        print(query)
        response = make_signed_request(DEFAULT_HOSTNAME, DEFAULT_METHOD, DEFAULT_QUERY_TYPE, query)
        print("Query Response:")
        print(response)

if __name__ == "__main__":
    main()
