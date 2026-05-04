"""
Real API integrations for GTM tools.
Each function reads its API key from the database and calls the platform's API.
"""

import json
import urllib.request
import urllib.error
from database import get_setting


def _post(url, data, headers):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "status": e.code}


def _get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "status": e.code}


# ── APOLLO ───────────────────────────────────────────────────────────────────

def apollo_search_people(title: str = "", company: str = "", location: str = "", limit: int = 10) -> str:
    key = get_setting("apollo_api_key")
    if not key:
        return "Apollo API key not configured. Add it in Settings."
    data = {
        "api_key": key,
        "person_titles": [title] if title else [],
        "organization_names": [company] if company else [],
        "person_locations": [location] if location else [],
        "per_page": limit,
    }
    result = _post("https://api.apollo.io/v1/mixed_people/search", data,
                   {"Content-Type": "application/json"})
    if "error" in result:
        return f"Apollo error: {result['error']}"
    people = result.get("people", [])
    if not people:
        return "No prospects found matching those criteria."
    lines = [f"Found {len(people)} prospects:"]
    for p in people[:limit]:
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        org = p.get("organization", {}).get("name", "Unknown company")
        email = p.get("email", "email not revealed")
        title_val = p.get("title", "")
        lines.append(f"- {name} | {title_val} at {org} | {email}")
    return "\n".join(lines)


def apollo_add_to_sequence(email: str, sequence_id: str) -> str:
    key = get_setting("apollo_api_key")
    if not key:
        return "Apollo API key not configured."
    data = {"api_key": key, "contact_email": email, "emailer_campaign_id": sequence_id}
    result = _post("https://api.apollo.io/v1/emailer_campaigns/add_contact_ids", data,
                   {"Content-Type": "application/json"})
    if "error" in result:
        return f"Apollo error: {result['error']}"
    return f"Added {email} to Apollo sequence {sequence_id}."


# ── HUBSPOT ──────────────────────────────────────────────────────────────────

def hubspot_create_contact(email: str, firstname: str = "", lastname: str = "", company: str = "", jobtitle: str = "") -> str:
    key = get_setting("hubspot_api_key")
    if not key:
        return "HubSpot API key not configured. Add it in Settings."
    props = {"email": email}
    if firstname: props["firstname"] = firstname
    if lastname: props["lastname"] = lastname
    if company: props["company"] = company
    if jobtitle: props["jobtitle"] = jobtitle
    result = _post("https://api.hubapi.com/crm/v3/objects/contacts",
                   {"properties": props},
                   {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if "error" in result or result.get("status") == "error":
        return f"HubSpot error: {result.get('message', result)}"
    cid = result.get("id", "")
    return f"Created HubSpot contact: {firstname} {lastname} ({email}) — ID: {cid}"


def hubspot_create_deal(name: str, stage: str = "appointmentscheduled", amount: str = "") -> str:
    key = get_setting("hubspot_api_key")
    if not key:
        return "HubSpot API key not configured."
    props = {"dealname": name, "dealstage": stage}
    if amount: props["amount"] = amount
    result = _post("https://api.hubapi.com/crm/v3/objects/deals",
                   {"properties": props},
                   {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if result.get("status") == "error":
        return f"HubSpot error: {result.get('message', result)}"
    return f"Created HubSpot deal: '{name}' at stage '{stage}' — ID: {result.get('id', '')}"


def hubspot_get_contacts(limit: int = 5) -> str:
    key = get_setting("hubspot_api_key")
    if not key:
        return "HubSpot API key not configured."
    result = _get(f"https://api.hubapi.com/crm/v3/objects/contacts?limit={limit}&properties=email,firstname,lastname,company",
                  {"Authorization": f"Bearer {key}"})
    if "error" in result:
        return f"HubSpot error: {result['error']}"
    contacts = result.get("results", [])
    if not contacts:
        return "No contacts found in HubSpot."
    lines = [f"HubSpot contacts ({len(contacts)}):"]
    for c in contacts:
        p = c.get("properties", {})
        lines.append(f"- {p.get('firstname','')} {p.get('lastname','')} | {p.get('email','')} | {p.get('company','')}")
    return "\n".join(lines)


# ── INSTANTLY ────────────────────────────────────────────────────────────────

def instantly_get_campaigns() -> str:
    key = get_setting("instantly_api_key")
    if not key:
        return "Instantly API key not configured. Add it in Settings."
    result = _get(f"https://api.instantly.ai/api/v1/campaign/list?api_key={key}&limit=10&skip=0",
                  {"Content-Type": "application/json"})
    if "error" in result:
        return f"Instantly error: {result['error']}"
    campaigns = result if isinstance(result, list) else result.get("data", [])
    if not campaigns:
        return "No campaigns found in Instantly."
    lines = [f"Instantly campaigns ({len(campaigns)}):"]
    for c in campaigns:
        lines.append(f"- {c.get('name', 'Unnamed')} | ID: {c.get('id', '')}")
    return "\n".join(lines)


def instantly_add_lead(email: str, first_name: str = "", last_name: str = "", campaign_id: str = "") -> str:
    key = get_setting("instantly_api_key")
    if not key:
        return "Instantly API key not configured."
    data = {
        "api_key": key,
        "campaign_id": campaign_id,
        "leads": [{"email": email, "first_name": first_name, "last_name": last_name}],
    }
    result = _post("https://api.instantly.ai/api/v1/lead/add", data,
                   {"Content-Type": "application/json"})
    if "error" in result:
        return f"Instantly error: {result['error']}"
    return f"Added {email} to Instantly campaign {campaign_id}."


# ── MAILCHIMP ────────────────────────────────────────────────────────────────

def mailchimp_get_lists() -> str:
    key = get_setting("mailchimp_api_key")
    if not key:
        return "Mailchimp API key not configured. Add it in Settings."
    dc = key.split("-")[-1]
    result = _get(f"https://{dc}.api.mailchimp.com/3.0/lists?count=10",
                  {"Authorization": f"Bearer {key}"})
    if "error" in result:
        return f"Mailchimp error: {result['error']}"
    lists = result.get("lists", [])
    if not lists:
        return "No lists found in Mailchimp."
    lines = [f"Mailchimp lists ({len(lists)}):"]
    for l in lists:
        lines.append(f"- {l.get('name')} | ID: {l.get('id')} | Members: {l.get('stats',{}).get('member_count',0)}")
    return "\n".join(lines)


def mailchimp_add_subscriber(email: str, first_name: str = "", last_name: str = "", list_id: str = "") -> str:
    key = get_setting("mailchimp_api_key")
    if not key:
        return "Mailchimp API key not configured."
    dc = key.split("-")[-1]
    data = {
        "email_address": email,
        "status": "subscribed",
        "merge_fields": {"FNAME": first_name, "LNAME": last_name},
    }
    result = _post(f"https://{dc}.api.mailchimp.com/3.0/lists/{list_id}/members",
                   data, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if result.get("status") == "subscribed":
        return f"Added {email} to Mailchimp list {list_id}."
    if "error" in result or result.get("title"):
        return f"Mailchimp error: {result.get('detail', result.get('title', result))}"
    return f"Added {email} to Mailchimp list {list_id}."


# ── ACTIVECAMPAIGN ───────────────────────────────────────────────────────────

def activecampaign_create_contact(email: str, first_name: str = "", last_name: str = "", phone: str = "") -> str:
    key = get_setting("activecampaign_api_key")
    if not key:
        return "ActiveCampaign API key not configured. Add it in Settings."
    base_url = get_setting("activecampaign_base_url") or ""
    if not base_url:
        return "ActiveCampaign base URL not set. Add it in Settings."
    data = {"contact": {"email": email, "firstName": first_name, "lastName": last_name, "phone": phone}}
    result = _post(f"{base_url}/api/3/contacts", data,
                   {"Api-Token": key, "Content-Type": "application/json"})
    if "contact" in result:
        cid = result["contact"].get("id", "")
        return f"Created ActiveCampaign contact: {first_name} {last_name} ({email}) — ID: {cid}"
    return f"ActiveCampaign error: {result}"


# ── PIPEDRIVE ────────────────────────────────────────────────────────────────

def pipedrive_create_person(name: str, email: str = "", phone: str = "") -> str:
    key = get_setting("pipedrive_api_key")
    if not key:
        return "Pipedrive API key not configured. Add it in Settings."
    data = {"name": name, "email": [{"value": email, "primary": True}] if email else []}
    if phone:
        data["phone"] = [{"value": phone, "primary": True}]
    result = _post(f"https://api.pipedrive.com/v1/persons?api_token={key}", data,
                   {"Content-Type": "application/json"})
    if result.get("success"):
        pid = result.get("data", {}).get("id", "")
        return f"Created Pipedrive person: {name} ({email}) — ID: {pid}"
    return f"Pipedrive error: {result.get('error', result)}"


def pipedrive_create_deal(title: str, person_id: str = "", stage_id: str = "") -> str:
    key = get_setting("pipedrive_api_key")
    if not key:
        return "Pipedrive API key not configured."
    data = {"title": title}
    if person_id: data["person_id"] = person_id
    if stage_id: data["stage_id"] = stage_id
    result = _post(f"https://api.pipedrive.com/v1/deals?api_token={key}", data,
                   {"Content-Type": "application/json"})
    if result.get("success"):
        did = result.get("data", {}).get("id", "")
        return f"Created Pipedrive deal: '{title}' — ID: {did}"
    return f"Pipedrive error: {result.get('error', result)}"


# ── INTERCOM ─────────────────────────────────────────────────────────────────

def intercom_create_contact(email: str, name: str = "") -> str:
    key = get_setting("intercom_api_key")
    if not key:
        return "Intercom API key not configured. Add it in Settings."
    data = {"role": "lead", "email": email}
    if name: data["name"] = name
    result = _post("https://api.intercom.io/contacts", data,
                   {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                    "Accept": "application/json"})
    if result.get("id"):
        return f"Created Intercom contact: {name} ({email}) — ID: {result['id']}"
    return f"Intercom error: {result}"


def intercom_send_message(user_id: str, message: str, admin_id: str = "") -> str:
    key = get_setting("intercom_api_key")
    if not key:
        return "Intercom API key not configured."
    data = {"message_type": "email", "subject": "Message from your team",
            "body": message, "template": "plain", "to": {"type": "user", "id": user_id}}
    if admin_id: data["from"] = {"type": "admin", "id": admin_id}
    result = _post("https://api.intercom.io/messages", data,
                   {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                    "Accept": "application/json"})
    if result.get("id"):
        return f"Sent Intercom message to user {user_id}."
    return f"Intercom error: {result}"


# ── KLAVIYO ──────────────────────────────────────────────────────────────────

def klaviyo_add_to_list(email: str, first_name: str = "", last_name: str = "", list_id: str = "") -> str:
    key = get_setting("klaviyo_api_key")
    if not key:
        return "Klaviyo API key not configured. Add it in Settings."
    profile = {"type": "profile", "attributes": {"email": email}}
    if first_name: profile["attributes"]["first_name"] = first_name
    if last_name: profile["attributes"]["last_name"] = last_name
    data = {"data": [profile]}
    result = _post(f"https://a.klaviyo.com/api/lists/{list_id}/relationships/profiles/",
                   data, {"Authorization": f"Klaviyo-API-Key {key}",
                          "Content-Type": "application/json", "revision": "2023-12-15"})
    return f"Added {email} to Klaviyo list {list_id}." if not result.get("errors") else f"Klaviyo error: {result}"


# ── MIXPANEL ─────────────────────────────────────────────────────────────────

def mixpanel_track_event(event: str, distinct_id: str, properties: dict = None) -> str:
    key = get_setting("mixpanel_api_key")
    if not key:
        return "Mixpanel token not configured. Add it in Settings."
    import base64
    props = properties or {}
    props["token"] = key
    props["distinct_id"] = distinct_id
    data = [{"event": event, "properties": props}]
    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    result = _get(f"https://api.mixpanel.com/track?data={encoded}&ip=0", {})
    return f"Tracked Mixpanel event '{event}' for {distinct_id}." if result == 1 else f"Mixpanel response: {result}"


# ── SEGMENT ──────────────────────────────────────────────────────────────────

def segment_identify(user_id: str, traits: dict = None) -> str:
    key = get_setting("segment_api_key")
    if not key:
        return "Segment write key not configured. Add it in Settings."
    import base64
    auth = base64.b64encode(f"{key}:".encode()).decode()
    data = {"userId": user_id, "traits": traits or {}}
    result = _post("https://api.segment.io/v1/identify", data,
                   {"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    return f"Identified Segment user {user_id}." if result.get("success") else f"Segment response: {result}"


def segment_track(user_id: str, event: str, properties: dict = None) -> str:
    key = get_setting("segment_api_key")
    if not key:
        return "Segment write key not configured."
    import base64
    auth = base64.b64encode(f"{key}:".encode()).decode()
    data = {"userId": user_id, "event": event, "properties": properties or {}}
    result = _post("https://api.segment.io/v1/track", data,
                   {"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    return f"Tracked Segment event '{event}' for {user_id}."


# ── NOTION ───────────────────────────────────────────────────────────────────

def notion_create_page(title: str, content: str, database_id: str = "") -> str:
    key = get_setting("notion_api_key")
    if not key:
        return "Notion API key not configured. Add it in Settings."
    parent_id = database_id or get_setting("notion_page_id")
    if not parent_id:
        return "Notion parent page/database ID not set. Add 'notion_page_id' in Settings."
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    blocks = []
    for para in content.split("\n\n"):
        if para.strip():
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": [{"type": "text", "text": {"content": para[:2000]}}]}})
    parent = {"database_id": database_id} if database_id else {"page_id": parent_id}
    data = {"parent": parent,
            "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
            "children": blocks[:50]}
    result = _post("https://api.notion.com/v1/pages", data, headers)
    if result.get("id"):
        return f"Created Notion page: '{title}' — {result.get('url', '')}"
    return f"Notion error: {result.get('message', result)}"


def notion_search(query: str) -> str:
    key = get_setting("notion_api_key")
    if not key:
        return "Notion API key not configured."
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    result = _post("https://api.notion.com/v1/search", {"query": query, "page_size": 8}, headers)
    if "message" in result:
        return f"Notion error: {result['message']}"
    results = result.get("results", [])
    if not results:
        return f"No Notion pages found for '{query}'."
    lines = [f"Found {len(results)} Notion results:"]
    for r in results[:5]:
        props = r.get("properties", {})
        title = ""
        for p in props.values():
            if p.get("type") == "title":
                title = "".join(t.get("plain_text", "") for t in p.get("title", []))
                break
        lines.append(f"- {title or 'Untitled'} | {r.get('url', '')}")
    return "\n".join(lines)


# ── SLACK ─────────────────────────────────────────────────────────────────────

def slack_send_message(channel: str, text: str) -> str:
    token = get_setting("slack_api_key")
    if not token:
        return "Slack bot token not configured. Add it in Settings."
    result = _post("https://slack.com/api/chat.postMessage",
                   {"channel": channel, "text": text},
                   {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if result.get("ok"):
        return f"Sent Slack message to {channel}."
    return f"Slack error: {result.get('error', result)}"


# ── LINEAR ────────────────────────────────────────────────────────────────────

def linear_create_issue(title: str, description: str = "", priority: int = 3) -> str:
    key = get_setting("linear_api_key")
    if not key:
        return "Linear API key not configured. Add it in Settings."
    team_id = get_setting("linear_team_id")
    if not team_id:
        return "Linear team ID not configured. Add 'linear_team_id' in Settings."
    mutation = """mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id title url } } }"""
    variables = {"input": {"teamId": team_id, "title": title, "priority": priority}}
    if description:
        variables["input"]["description"] = description
    req = urllib.request.Request("https://api.linear.app/graphql",
                                  data=json.dumps({"query": mutation, "variables": variables}).encode(),
                                  headers={"Authorization": key, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return f"Linear error: {e.read().decode()}"
    data = result.get("data", {}).get("issueCreate", {})
    if data.get("success"):
        issue = data["issue"]
        return f"Created Linear issue: '{issue['title']}' — {issue.get('url', '')}"
    return f"Linear error: {result.get('errors', result)}"


def linear_get_issues(limit: int = 10) -> str:
    key = get_setting("linear_api_key")
    if not key:
        return "Linear API key not configured."
    query = """query($first: Int) { issues(first: $first, orderBy: updatedAt) { nodes { title state { name } url } } }"""
    req = urllib.request.Request("https://api.linear.app/graphql",
                                  data=json.dumps({"query": query, "variables": {"first": limit}}).encode(),
                                  headers={"Authorization": key, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return f"Linear error: {e.read().decode()}"
    issues = result.get("data", {}).get("issues", {}).get("nodes", [])
    if not issues:
        return "No Linear issues found."
    lines = [f"Linear issues ({len(issues)}):"]
    for i in issues:
        lines.append(f"- [{i.get('state',{}).get('name','')}] {i['title']}")
    return "\n".join(lines)


# ── JIRA ──────────────────────────────────────────────────────────────────────

def jira_create_issue(project_key: str, summary: str, description: str = "", issue_type: str = "Task") -> str:
    import base64
    token = get_setting("jira_api_key")
    email = get_setting("jira_email")
    base_url = get_setting("jira_url", "").rstrip("/")
    if not all([token, email, base_url]):
        return "Jira not fully configured. Add Jira URL, email, and API token in Settings."
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    fields = {"project": {"key": project_key}, "summary": summary, "issuetype": {"name": issue_type}}
    if description:
        fields["description"] = {"type": "doc", "version": 1,
                                  "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]}
    result = _post(f"{base_url}/rest/api/3/issue", {"fields": fields},
                   {"Authorization": f"Basic {auth}", "Content-Type": "application/json", "Accept": "application/json"})
    if result.get("id"):
        return f"Created Jira issue: {result.get('key', result['id'])} — '{summary}' in {project_key}"
    return f"Jira error: {result.get('errors', result.get('errorMessages', result))}"


def jira_get_issues(project_key: str, max_results: int = 10) -> str:
    import base64
    token = get_setting("jira_api_key")
    email = get_setting("jira_email")
    base_url = get_setting("jira_url", "").rstrip("/")
    if not all([token, email, base_url]):
        return "Jira not fully configured."
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    jql = f"project%3D{project_key}+ORDER+BY+updated+DESC"
    result = _get(f"{base_url}/rest/api/3/search?jql={jql}&maxResults={max_results}&fields=summary,status",
                  {"Authorization": f"Basic {auth}", "Accept": "application/json"})
    issues = result.get("issues", [])
    if not issues:
        return f"No issues in Jira project {project_key}."
    lines = [f"Jira {project_key} issues ({len(issues)}):"]
    for i in issues:
        f = i.get("fields", {})
        lines.append(f"- [{f.get('status',{}).get('name','')}] {i['key']}: {f.get('summary','')}")
    return "\n".join(lines)


# ── TOOL REGISTRY ────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "apollo_search_people": apollo_search_people,
    "apollo_add_to_sequence": apollo_add_to_sequence,
    "hubspot_create_contact": hubspot_create_contact,
    "hubspot_create_deal": hubspot_create_deal,
    "hubspot_get_contacts": hubspot_get_contacts,
    "instantly_get_campaigns": instantly_get_campaigns,
    "instantly_add_lead": instantly_add_lead,
    "mailchimp_get_lists": mailchimp_get_lists,
    "mailchimp_add_subscriber": mailchimp_add_subscriber,
    "activecampaign_create_contact": activecampaign_create_contact,
    "pipedrive_create_person": pipedrive_create_person,
    "pipedrive_create_deal": pipedrive_create_deal,
    "intercom_create_contact": intercom_create_contact,
    "intercom_send_message": intercom_send_message,
    "klaviyo_add_to_list": klaviyo_add_to_list,
    "mixpanel_track_event": mixpanel_track_event,
    "segment_identify": segment_identify,
    "segment_track": segment_track,
    "notion_create_page": notion_create_page,
    "notion_search": notion_search,
    "slack_send_message": slack_send_message,
    "linear_create_issue": linear_create_issue,
    "linear_get_issues": linear_get_issues,
    "jira_create_issue": jira_create_issue,
    "jira_get_issues": jira_get_issues,
}

ALL_TOOLS = [
    {"name": "apollo_search_people", "description": "Search for prospects in Apollo.io by job title, company, or location.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "company": {"type": "string"}, "location": {"type": "string"}, "limit": {"type": "integer", "default": 10}}}},
    {"name": "apollo_add_to_sequence", "description": "Add a contact to an Apollo email sequence.", "input_schema": {"type": "object", "properties": {"email": {"type": "string"}, "sequence_id": {"type": "string"}}, "required": ["email", "sequence_id"]}},
    {"name": "hubspot_create_contact", "description": "Create a new contact in HubSpot CRM.", "input_schema": {"type": "object", "properties": {"email": {"type": "string"}, "firstname": {"type": "string"}, "lastname": {"type": "string"}, "company": {"type": "string"}, "jobtitle": {"type": "string"}}, "required": ["email"]}},
    {"name": "hubspot_create_deal", "description": "Create a new deal in HubSpot CRM.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "stage": {"type": "string"}, "amount": {"type": "string"}}, "required": ["name"]}},
    {"name": "hubspot_get_contacts", "description": "Get recent contacts from HubSpot CRM.", "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 5}}}},
    {"name": "instantly_get_campaigns", "description": "List all campaigns in Instantly.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "instantly_add_lead", "description": "Add a lead to an Instantly campaign.", "input_schema": {"type": "object", "properties": {"email": {"type": "string"}, "first_name": {"type": "string"}, "last_name": {"type": "string"}, "campaign_id": {"type": "string"}}, "required": ["email", "campaign_id"]}},
    {"name": "mailchimp_get_lists", "description": "Get all Mailchimp audience lists.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "mailchimp_add_subscriber", "description": "Add a subscriber to a Mailchimp list.", "input_schema": {"type": "object", "properties": {"email": {"type": "string"}, "first_name": {"type": "string"}, "last_name": {"type": "string"}, "list_id": {"type": "string"}}, "required": ["email", "list_id"]}},
    {"name": "activecampaign_create_contact", "description": "Create a contact in ActiveCampaign.", "input_schema": {"type": "object", "properties": {"email": {"type": "string"}, "first_name": {"type": "string"}, "last_name": {"type": "string"}, "phone": {"type": "string"}}, "required": ["email"]}},
    {"name": "pipedrive_create_person", "description": "Create a person in Pipedrive CRM.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}}, "required": ["name"]}},
    {"name": "pipedrive_create_deal", "description": "Create a deal in Pipedrive CRM.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "person_id": {"type": "string"}, "stage_id": {"type": "string"}}, "required": ["title"]}},
    {"name": "intercom_create_contact", "description": "Create a lead/contact in Intercom.", "input_schema": {"type": "object", "properties": {"email": {"type": "string"}, "name": {"type": "string"}}, "required": ["email"]}},
    {"name": "intercom_send_message", "description": "Send a message to a user in Intercom.", "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}, "message": {"type": "string"}, "admin_id": {"type": "string"}}, "required": ["user_id", "message"]}},
    {"name": "klaviyo_add_to_list", "description": "Add a profile to a Klaviyo list.", "input_schema": {"type": "object", "properties": {"email": {"type": "string"}, "first_name": {"type": "string"}, "last_name": {"type": "string"}, "list_id": {"type": "string"}}, "required": ["email", "list_id"]}},
    {"name": "mixpanel_track_event", "description": "Track an event in Mixpanel.", "input_schema": {"type": "object", "properties": {"event": {"type": "string"}, "distinct_id": {"type": "string"}, "properties": {"type": "object"}}, "required": ["event", "distinct_id"]}},
    {"name": "segment_identify", "description": "Identify a user in Segment with traits.", "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}, "traits": {"type": "object"}}, "required": ["user_id"]}},
    {"name": "segment_track", "description": "Track an event in Segment.", "input_schema": {"type": "object", "properties": {"user_id": {"type": "string"}, "event": {"type": "string"}, "properties": {"type": "object"}}, "required": ["user_id", "event"]}},
    {"name": "notion_create_page", "description": "Create a new page in Notion with a title and content.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}, "database_id": {"type": "string", "description": "Optional Notion database ID"}}, "required": ["title", "content"]}},
    {"name": "notion_search", "description": "Search for pages in Notion by keyword.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "slack_send_message", "description": "Send a message to a Slack channel.", "input_schema": {"type": "object", "properties": {"channel": {"type": "string", "description": "Channel name e.g. #general"}, "text": {"type": "string"}}, "required": ["channel", "text"]}},
    {"name": "linear_create_issue", "description": "Create an issue in Linear.", "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "integer", "description": "0=none 1=urgent 2=high 3=medium 4=low"}}, "required": ["title"]}},
    {"name": "linear_get_issues", "description": "List recent issues from Linear.", "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}}},
    {"name": "jira_create_issue", "description": "Create an issue in Jira.", "input_schema": {"type": "object", "properties": {"project_key": {"type": "string"}, "summary": {"type": "string"}, "description": {"type": "string"}, "issue_type": {"type": "string", "default": "Task"}}, "required": ["project_key", "summary"]}},
    {"name": "jira_get_issues", "description": "List recent issues from a Jira project.", "input_schema": {"type": "object", "properties": {"project_key": {"type": "string"}, "max_results": {"type": "integer", "default": 10}}, "required": ["project_key"]}},
]
