import azure.functions as func
import logging
import json
import os
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient
from datetime import timedelta

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="query", methods=["POST"])
def query_sentinel(req: func.HttpRequest) -> func.HttpResponse:
    """Execute a KQL query against a specified Log Analytics workspace."""
    logging.info("Sentinel proxy query received")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    workspace_id = body.get("workspace_id")
    query = body.get("query")
    timespan_hours = body.get("timespan_hours", 168)  # default 7 days

    if not workspace_id or not query:
        return func.HttpResponse(
            json.dumps({"error": "workspace_id and query are required"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        credential = DefaultAzureCredential(additionally_allowed_tenants=["*"])
        # Use ARM-based query endpoint for cross-tenant Lighthouse access
        import requests as http_requests
        token = credential.get_token("https://api.loganalytics.io/.default")
        api_url = f"https://api.loganalytics.io/v1/workspaces/{workspace_id}/query"
        headers = {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}
        api_body = {"query": query, "timespan": f"PT{timespan_hours}H"}
        api_resp = http_requests.post(api_url, json=api_body, headers=headers, timeout=120)

        if api_resp.status_code == 403 or api_resp.status_code == 401:
            # Try with cross-tenant token via ARM endpoint (for Lighthouse cross-tenant access)
            subscription_id = body.get("subscription_id", os.environ.get("CUSTOMER_SUBSCRIPTION_ID", ""))
            resource_group = body.get("resource_group", os.environ.get("CUSTOMER_RESOURCE_GROUP", ""))
            workspace_name = body.get("workspace_name", os.environ.get("CUSTOMER_WORKSPACE_NAME", ""))
            if not subscription_id or not resource_group or not workspace_name:
                return func.HttpResponse(
                    json.dumps({"error": "ARM fallback requires subscription_id, resource_group, and workspace_name"}),
                    status_code=400,
                    mimetype="application/json",
                )
            arm_token = credential.get_token("https://management.azure.com/.default")
            arm_url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.OperationalInsights/workspaces/{workspace_name}/query?api-version=2022-10-27"
            headers = {"Authorization": f"Bearer {arm_token.token}", "Content-Type": "application/json"}
            api_resp = http_requests.post(arm_url, json={"query": query, "timespan": f"PT{timespan_hours}H"}, headers=headers, timeout=120)

        if api_resp.status_code != 200:
            return func.HttpResponse(
                json.dumps({"error": f"Query API returned {api_resp.status_code}: {api_resp.text[:500]}"}),
                status_code=api_resp.status_code,
                mimetype="application/json",
            )

        data = api_resp.json()
        results = []
        for table in data.get("tables", []):
            columns = [col["name"] for col in table.get("columns", [])]
            for row in table.get("rows", []):
                results.append(dict(zip(columns, [str(v) for v in row])))

        response = None  # signal success path below

        return func.HttpResponse(
            json.dumps({"status": "success", "count": len(results), "results": results[:100]}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        logging.error(f"Query failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({"status": "healthy", "service": "sentinel-proxy"}),
        status_code=200,
        mimetype="application/json",
    )
