import azure.functions as func
import logging
import os
import requests
import json

# ACS Integration Settings
AZURE_SEARCH_SERVICE = os.environ.get("AZURE_SEARCH_SERVICE")
AZURE_SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX")
AZURE_SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY")
AZURE_SEARCH_USE_SEMANTIC_SEARCH = os.environ.get("AZURE_SEARCH_USE_SEMANTIC_SEARCH", "false")
AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG = os.environ.get("AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG", "default")
AZURE_SEARCH_TOP_K = os.environ.get("AZURE_SEARCH_TOP_K", 5)
AZURE_SEARCH_ENABLE_IN_DOMAIN = os.environ.get("AZURE_SEARCH_ENABLE_IN_DOMAIN", "true")
AZURE_SEARCH_CONTENT_COLUMNS = os.environ.get("AZURE_SEARCH_CONTENT_COLUMNS")
AZURE_SEARCH_FILENAME_COLUMN = os.environ.get("AZURE_SEARCH_FILENAME_COLUMN")
AZURE_SEARCH_TITLE_COLUMN = os.environ.get("AZURE_SEARCH_TITLE_COLUMN")
AZURE_SEARCH_URL_COLUMN = os.environ.get("AZURE_SEARCH_URL_COLUMN")

# AOAI Integration Settings
AZURE_OPENAI_RESOURCE = os.environ.get("AZURE_OPENAI_RESOURCE")
AZURE_OPENAI_MODEL = os.environ.get("AZURE_OPENAI_MODEL")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY")
AZURE_OPENAI_TEMPERATURE = os.environ.get("AZURE_OPENAI_TEMPERATURE", 0)
AZURE_OPENAI_TOP_P = os.environ.get("AZURE_OPENAI_TOP_P", 1)
AZURE_OPENAI_MAX_TOKENS = os.environ.get("AZURE_OPENAI_MAX_TOKENS", 1000)
AZURE_OPENAI_STOP_SEQUENCE = os.environ.get("AZURE_OPENAI_STOP_SEQUENCE")
AZURE_OPENAI_SYSTEM_MESSAGE = os.environ.get("AZURE_OPENAI_SYSTEM_MESSAGE", "You are an AI assistant that helps people find information.")
AZURE_OPENAI_PREVIEW_API_VERSION = os.environ.get("AZURE_OPENAI_PREVIEW_API_VERSION", "2023-06-01-preview")
AZURE_OPENAI_MODEL_NAME = os.environ.get("AZURE_OPENAI_MODEL_NAME", "gpt-35-turbo") # Name of the model, e.g. 'gpt-35-turbo' or 'gpt-4'

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="prompt")
def ProcessPrompt(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    prompt = req.params.get('prompt')
    if not prompt:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            prompt = req_body.get('prompt')

    if prompt:
        logging.info('Returning the response from OpenAI')
        return conversation_with_data(prompt)
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a prompt in the query string or in the request body.",
             status_code=200
        )


# Prepare the body and headers for the request
def prepare_body_headers_with_data(prompt):
    logging.info('Preparing the body for the request')
    body = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            },
            {
                "role": "system",
                "content": AZURE_OPENAI_SYSTEM_MESSAGE
            }
        ],
        "temperature": float(AZURE_OPENAI_TEMPERATURE),
        "max_tokens": int(AZURE_OPENAI_MAX_TOKENS),
        "top_p": float(AZURE_OPENAI_TOP_P),
        "stop": AZURE_OPENAI_STOP_SEQUENCE.split("|") if AZURE_OPENAI_STOP_SEQUENCE else None,
        "stream": False,
        "dataSources": [
            {
                "type": "AzureCognitiveSearch",
                "parameters": {
                    "endpoint": f"https://{AZURE_SEARCH_SERVICE}.search.windows.net",
                    "key": AZURE_SEARCH_KEY,
                    "indexName": AZURE_SEARCH_INDEX,
                    "fieldsMapping": {
                        "contentField": AZURE_SEARCH_CONTENT_COLUMNS.split("|") if AZURE_SEARCH_CONTENT_COLUMNS else [],
                        "titleField": AZURE_SEARCH_TITLE_COLUMN if AZURE_SEARCH_TITLE_COLUMN else None,
                        "urlField": AZURE_SEARCH_URL_COLUMN if AZURE_SEARCH_URL_COLUMN else None,
                        "filepathField": AZURE_SEARCH_FILENAME_COLUMN if AZURE_SEARCH_FILENAME_COLUMN else None
                    },
                    "inScope": True if AZURE_SEARCH_ENABLE_IN_DOMAIN.lower() == "true" else False,
                    "topNDocuments": AZURE_SEARCH_TOP_K,
                    "queryType": "semantic" if AZURE_SEARCH_USE_SEMANTIC_SEARCH.lower() == "true" else "simple",
                    "semanticConfiguration": AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG if AZURE_SEARCH_USE_SEMANTIC_SEARCH.lower() == "true" and AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG else ""
                }
            }
        ]
    }
    logging.info(f"body: {body}")

    chatgpt_url = f"https://{AZURE_OPENAI_RESOURCE}.openai.azure.com/openai/deployments/{AZURE_OPENAI_MODEL}/chat/completions?api-version={AZURE_OPENAI_PREVIEW_API_VERSION}"

    logging.info('Preparing the headers for the request')
    headers = {
        'Content-Type': 'application/json',
        'api-key': AZURE_OPENAI_KEY,
        'chatgpt_url': chatgpt_url,
        'chatgpt_key': AZURE_OPENAI_KEY
    }
    logging.info(f"headers: {headers}")

    return body, headers


# Call the OpenAI endpoint
def conversation_with_data(prompt):
    logging.info('Preparing the body and headers for the request')
    body, headers = prepare_body_headers_with_data(prompt)

    logging.info('Calling the OpenAI endpoint')
    endpoint = f"https://{AZURE_OPENAI_RESOURCE}.openai.azure.com/openai/deployments/{AZURE_OPENAI_MODEL}/extensions/chat/completions?api-version={AZURE_OPENAI_PREVIEW_API_VERSION}"
    logging.info(f"endpoint: {endpoint}")

    r = requests.post(endpoint, headers=headers, json=body)
    status_code = r.status_code
    r = r.json()

    # Extract the citations and answer from the response
    answer = { "citations": "", "answer": "" }
    for message in r['choices'][0]['messages']:
        if message['role'] == 'tool':
            content = json.loads(message['content'])
            answer['citations'] = content['citations']
        elif message['role'] == 'assistant':
            answer['answer'] = message['content']

    logging.info(f"status_code: {status_code}")
    return func.HttpResponse(json.dumps(answer), status_code=status_code)