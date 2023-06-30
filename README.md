# OpenAI with SAP

## Use cases
* [Use case #1: Text to SQL](https://github.com/thzandvl/sap-ai-sql)
* Use case #2: Use your own data with Azure OpenAI service

## Use case #2: Use your own data with Azure OpenAI service
This is a simplified version of the the example code provided by Microsoft that can be found [here](https://github.com/microsoft/sample-app-aoai-chatGPT). As the Python OpenAI library does not yet provide a method to use your own data, I used the REST API just like in the example code. You will get a JSON response with the brief answer and the citations from the Azure OpenAI service which you can use for your own purposes.


### Prerequisites
* `OpenAI deployment`: An OpenAI deployment on Azure is required. For more information on how to create an OpenAI deployment please visit the [documentation](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal). For this test I used the GPT-3.5 Turbo model as the GPT-4 model is still in private preview.
* `Search index`: Create a search index in Azure Cognitive Search. You can use the Azure AI Studio to create a search index based on document files in Azure blob storage, I provided my sample documents in the [data](https://github.com/thzandvl/sap-ai-docs/tree/main/data) folder. The search index should contain the following fields:
    * `content`: The content of the document
    * `filename`: The name of the document
    * `title`: The title of the document
    * `url`: The url of the document
* `Azure Functions`: For the code I will use the Python programming model v2. For more information on Azure Functions please visit the [documentation](https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-vs-code-python?pivots=python-mode-decorators).


## The code
The code exists of three functions, one to prepare the body and headers for the REST call, one to call the OpenAI endpoint and extract the data and one for the HTTP trigger. The HTTP trigger function is the main function that will be called from the client. The HTTP trigger function will call the function that retrieves data from the Azure OpenAI service endpoint and uses the prepare function to generate the body and headers. The HTTP trigger function will return the answer to the client.


### The prompt
This is mainly the default function generated while creating the Azure Function. The only thing I changed is the route and the name of the function.

```python
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
```

### Setting the environment variables
There is quiet a list of environment variables that are required to define the search index and Azure OpenAI service. For the search index you need the following:
```json
    "AZURE_SEARCH_SERVICE": "<name of the Azure Cognitive Search service>",
    "AZURE_SEARCH_KEY": "<Azure Cognitive Search service API key>",
    "AZURE_SEARCH_INDEX": "<name of the search index>",
    "AZURE_SEARCH_USE_SEMANTIC_SEARCH": "false",
    "AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG": "default",
    "AZURE_SEARCH_TOP_K": 5,
    "AZURE_SEARCH_ENABLE_IN_DOMAIN": "true",
    "AZURE_SEARCH_CONTENT_COLUMNS": "<column name for the content>",
    "AZURE_SEARCH_FILENAME_COLUMN": "<column name for the filename>",
    "AZURE_SEARCH_TITLE_COLUMN": "<column name for the title>",
    "AZURE_SEARCH_URL_COLUMN": "<column name for the file url>"
```


And for the Azure OpenAI service you need the following:
```json
    "AZURE_OPENAI_PREVIEW_API_VERSION": "2023-06-01-preview",
    "AZURE_OPENAI_RESOURCE": "<Azure OpenAI service name>",
    "AZURE_OPENAI_KEY": "<Azure OpenAI API key>",
    "AZURE_OPENAI_MODEL": "<provided model name for deployment>",
    "AZURE_OPENAI_SYSTEM_MESSAGE": "<optional: to define how the chatbot behaves>",
    "AZURE_OPENAI_STOP_SEQUENCE": "None"
```

Make sure to set the OS environment variables in `local.settings.json` for local testing and in the Azure Function App settings for the deployment.


### Preparing the body and headers
This function prepares the body and headers for the REST call to the Azure OpenAI service. The body contains the prompt, the system message and the datasource information that refers to the search index. The headers contain the API key and the content type.

```python
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
```

### Calling the Azure OpenAI service
This function calls the Azure OpenAI service and returns the answer to the HTTP trigger function. The function uses the prepare function to generate the body and headers for the REST call.

```python
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
```

Based on the role of the message the function extracts the citations and the answer from the response. Both values are returned as a JSON object to the HTTP trigger function.


### Testing the code
In my local deployment I used the following REST query:

```http
POST http://localhost:7071/api/prompt
content-type: application/json

{ "prompt": "How do I clean the espresso machine?" }
```

The result from OpenAI is:

```json
{
  "citations": [
    {
      "content": "The arrow on the yellow cylinder on the side of the\nbrew group has to be aligned with the black arrow and N (Fig. 24). \n- If they are not aligned, push down the lever until it is in contact with the base of the brew group (Fig.\n25).\n2 Slide the brew group back into the machine along the guiding rails on the sides (Fig. 26) until it locks into\nposition with a click (Fig. 27). Do not press the PUSH button.\n3 Close the service door and place back the water tank.\nCleaning and maintenance\nRegular cleaning and maintenance keeps your machine in top condition and ensures good-tasting coffee\nfor a long time with a steady coffee flow. \nConsult the table below for a detailed description on when and how to clean all detachable parts of the\nmachine. You can find more detailed information and video instructions on www.philips.com/coffee-care.\nSee figure D for an overview of which parts can be cleaned in the dishwasher.\n13English\nEn\ngl\nish\nDetachable\nparts\nWhen to clean How to clean\nBrew group Weekly Remove the brew group from the machine (see\n'Removing and inserting the brew group'). Rinse it\nunder the tap (see 'Cleaning the brew group under\nthe tap').\nClassic milk frother After every use First dispense hot water with the milk frother\nattached to the machine for thorough cleaning.\nThen remove the milk frother from the machine and\ndisassemble it. Clean all parts under the tap or in the\ndishwasher.\nPre-ground coffee\ncompartment\nCheck the pre-ground coffee\ncompartment weekly to see if\nit is clogged.\nUnplug the machine and remove the brew group.\nOpen the lid of the pre-ground coffee compartment\nand insert the spoon handle into it. Move the\nhandle up and down until the clogged ground\ncoffee falls down (Fig. 28). Go to\nwww.philips.com/coffee-care for detailed video\ninstructions.\nCoffee grounds\ncontainer\nEmpty the coffee grounds\ncontainer when prompted by\nthe machine. Clean it weekly.\nRemove the coffee grounds container while the\nmachine is switched on. Rinse it under the tap with\nsome washing-up liquid or clean it in the\ndishwasher. The front panel of the coffee grounds\ncontainer is not dishwasher-safe.\nDrip tray Empty the drip tray daily or as\nsoon as the red 'drip tray full'\nindicator pops up through the\ndrip tray (Fig. 29). Clean the\ndrip tray weekly.\nRemove the drip tray (Fig. 30) and rinse it under the\ntap with some washing-up liquid. You can also clean\nthe drip tray in the dishwasher. The front panel of\nthe coffee grounds container (fig. A15) is not\ndishwasher-safe.\nLatteGo After every use Rinse LatteGo under the tap or clean it in the\ndishwasher.\nLubrication of the\nbrew group\nEvery 2 months Consult the lubrication table and lubricate the brew\ngroup with the Philips grease (see 'Lubricating the\nbrew group').\nWater tank Weekly Rinse the water tank under the tap \nCleaning the brew group\nRegular cleaning of the brew group prevents coffee residues from clogging up the internal circuits. Visit\nwww.philips.com/coffee-care for support videos on how to remove, insert and clean the brew group.\nCleaning the brew group under the tap\n1 Remove the brew group (see 'Removing and inserting the brew group').\n2 Rinse the brew group thoroughly with water. Carefully clean the upper filter (Fig. 31) of the brew group.\n3 Let the brew group air-dry before you place it back. Do not dry the brew group with a cloth to prevent\nfibers from collecting inside the brew group.\n14 English\nLubricating the brew group\nLubricate the brew group every 2 months, to ensure that the moving parts continue to move smoothly.\n1 Apply a thin layer of grease on the piston (grey part) of the brew group (Fig. 32).\n2 Apply a thin layer of grease around the shaft (grey part) in the bottom of the brew group (Fig. 33).\n3 Apply a thin layer of grease to the rails on both sides (Fig. 34).\nCleaning LatteGo (milk container)\nCleaning LatteGo after every use\n1 Remove LatteGo from the machine (Fig. 35).\n2 Pour out any remaining milk",
      "id": null,
      "title": "Fully automatic",
      "filepath": "11d43c39993c4c958a30ad1f011465b4.pdf",
      "url": "https://<blobname>.blob.core.windows.net/usermanuals/11d43c39993c4c958a30ad1f011465b4.pdf",
      "metadata": {
        "chunking": "orignal document size=991. Scores=15.81736 and None.Org Highlight count=115."
      },
      "chunk_id": "0"
    },
    {
      "content": "Fully automatic\nespresso machine\n1200 series\n2200 series \n3200 series\nEN USER MANUAL\nFR MODE D\u2019EMPLOI\nES MANUAL DEL USUARIO\nwww.philips.com/co\ufffdee-care\nMy Coffee Choice \nA2A1 A3 A4\nA14\nA6 A8A7\nA9\nA12\nA13\nA10\nA11\nA5\nA17\nA15\nA\nB1 B2 B3 B4 B5\nB10B11\nB7B6 B8 B9\nB\nA19A18\nA16\nA20 A21 A22 A23 A24\nClassic Milk Frother\nEP2121\nEP2124\nEP2220\nEP2221\nEP2224\nEP3221\nEP2131\nEP2136\nEP2230\nEP2231\nEP2235\nEP3241\nEP3243\nEP3246\nEP3249\nLatteGo\nClassic Milk Frother\nEP1220\n1200 series\n2200 series\n3200 series\nA19 A20 A21 A22 A23 A24\nA17A18 A16 A14 A24 A23 A21 A15 A9 A4 A12\nC\nD\nEnglish\n5English\nEn\ngl\nish\nContents\nMachine overview (Fig. A) __________________________________________________________________ 5\nControl panel (Fig. B) ______________________________________________________________________ 5\nIntroduction _____________________________________________________________________________ 6\nBefore first use ___________________________________________________________________________ 6\nBrewing drinks ___________________________________________________________________________ 8\nAdjusting machine settings_________________________________________________________________ 10\nRemoving and inserting the brew group _____________________________________________________ 12\nCleaning and maintenance _________________________________________________________________ 12\nAquaClean water filter ____________________________________________________________________ 14\nSetting the water hardness ________________________________________________________________ 16\nDescaling procedure (30 min.) ______________________________________________________________ 16\nOrdering accessories ______________________________________________________________________ 17\nTroubleshooting __________________________________________________________________________ 17\nTechnical specifications ____________________________________________________________________ 23\nMachine overview (Fig. A)\nA1 Control panel A10 Service door\nA2 Cup holder A11 Data label with type number\nA3 Pre-ground coffee compartment A12 Water tank\nA4 Lid of bean hopper A13 Hot water spout\nA5 Adjustable coffee spout A14 Coffee grounds container\nA6 Mains plug A15 Front panel of coffee grounds container\nA7 Grind setting knob A16 Drip tray cover\nA8 Coffee bean hopper A17 Drip tray\nA9 Brew group A18 'Drip tray full' indicator\nAccessories\nA19 Grease tube A22 Water hardness test strip\nA20 AquaClean water filter A23 Classic milk frother (specific types only)\nA21 Measuring scoop A24 LatteGo (milk container) (specific types\nonly)\nControl panel (Fig. B)\nRefer to figure B for an overview of all buttons and icons. Below you find the description.\n Some of the buttons/icons are for specific types only.\n6 English\nB1 On/off button B7 Warning icons\nB2 Drink icons* B8 Start light \nB3 Aroma strength/pre-ground coffee icon B9 Start/stop button\nB4 Drink quantity icon B10 Calc / Clean icon\nB5 Milk quantity icon (specific types only) B11 AquaClean icon\nB6 Coffee temperature icon (specific types only)\n* Drink icons: espresso, espresso lungo, coffee, americano, cappuccino, latte macchiato, hot water, steam,\niced coffee (specific types only)\nIntroduction\nCongratulations on your purchase of a Philips fully automatic coffee machine! To fully benefit from the\nsupport that Philips offers, please register your product at www.philips.com/welcome. \nRead the separate safety booklet carefully before you use the machine for the first time and save it for\nfuture reference.\nTo help you get started and to get the best out of your machine, Philips offers support in multiple ways. In\nthe box you find:\n1 This user manual with picture-based usage instructions and more detailed information on cleaning and\nmaintenance. \nThere are multiple versions of this espresso machine, which all have different features. Each version\nhas its own type number. You can find the type number on the data label on the inside of the service\ndoor (see fig A11).\n2 The separate safety booklet with instructions on how to use the machine in a safe way.\n3 For online support (frequently asked questions, movies etc.), scan the QR code on the cover of this\nbooklet or visit www.philips.com/coffee-care\nThis machine has been tested with coffee. Although it has been carefully cleaned, there may be some\ncoffee residues left",
      "id": null,
      "title": "Fully automatic",
      "filepath": "11d43c39993c4c958a30ad1f011465b4.pdf",
      "url": "https://<blobname>.blob.core.windows.net/usermanuals/11d43c39993c4c958a30ad1f011465b4.pdf",
      "metadata": {
        "chunking": "orignal document size=1021. Scores=15.441555 and None.Org Highlight count=34."
      },
      "chunk_id": "1"
    },
    {
      "content": "A)2true12 cmfalsefalseIn This Chapter00truefalsetruefalse0falsefalsefalse3falseIn This Chapter|582false2false18 pxfalsetruePrevious1254falsefalsetruefalse0falsefalsefalse1truePrevious|583false2false18 pxfalsetrueNext1244falsefalsetruefalse0truefalsefalse1falseNext|584false2false48 pxtruetrueContents1224falsefalsetruefalse0falsefalsefalse1falseContents|585false2false48 pxfalsetrueIndex1234falsefalsetruetrue0falsefalsefalse1falseIndex|586false03false10036 08true0243truetrue036true(auto)\n63Janette Weishaupt2018-01-11T14:05:04Removing the brew group from the machine Xelsis ROW1304abf8a6b67467412db680b35f4be4656d360961truetruetruefalse01102899Janette Weishaupt2018-04-23T09:03:186Topic10360961-11Removing the brew group from the machine2true6 cmfalsefalseIn This Section00truefalsetruefalse0falsefalsefalse3falseIn This Section|631false2false6 cmfalsefalseSee Also00truefalsetruefalse0falsetruefalse3falseSee Also|632true2false18 pxfalsetruePrevious1254falsefalsetruefalse0falsefalsefalse1truePrevious|633false2false18 pxfalsetrueNext1244falsefalsetruefalse0truefalsefalse1falseNext|634false2false48 pxtruetrueContents1224falsefalsetruefalse0falsefalsefalse1falseContents|635false2false48 pxfalsetrueIndex1234falsefalsetruetrue0falsefalsefalse1falseIndex|636falseSwitch off the machine by pressing the main switch on the back of the machine.\nRemove the coffee residues drawer.\nPress the PUSH button and pull at the grip of the brew group to remove it from the machine.\n00false1000 08true0243falsetrue044true(auto)\n3430Janette Weishaupt2017-09-26T14:29:38140416531e2dc047e338453eba9322bbbe209c7e319332truetruetruefalse0902357Janette Weishaupt2017-09-28T14:08:1611Topic1031933201 \n00false1000 012true050falsefalse00false(auto)\n3430Janette Weishaupt2017-05-15T13:36:09139911015e2f6ae5f2cbd4dd08dfd1fe28846ec05284107truetruetruefalse0813724Janette Weishaupt2017-06-13T12:32:0711Topic1028410701 \n00false1000 012true050falsefalse00false(auto)\n62Janette Weishaupt2017-05-11T11:31:43Handling the brew group PH3100 OTC Glossy10159027082724b14cc1a6d086ffe5e05a06283402truetruetruefalse0813764Janette Weishaupt2017-06-13T12:32:556Topic10283402-11 Go to www.philips.com/coffee-care for detailed video instructions on how to remove, insert and clean the brew group.\n00false1000 012true0543falsefalse044true(auto)\n62Janette Weishaupt2017-05-03T10:43:48Cleaning the brew group PH310010155209a6b559f1475985242411772bee7e282011truetruetruefalse0813748Janette Weishaupt2017-06-13T12:32:506Topic10282011-11 Regular cleaning of the brew group prevents coffee residues from clogging up the internal circuits. Visit www.philips.com/coffee-care for support videos on how to remove, insert and clean the brew group",
      "id": null,
      "title": "Fully automatic",
      "filepath": "11d43c39993c4c958a30ad1f011465b4.pdf",
      "url": "https://<blobname>.blob.core.windows.net/usermanuals/11d43c39993c4c958a30ad1f011465b4.pdf",
      "metadata": {
        "chunking": "orignal document size=932. Scores=15.421179 and None.Org Highlight count=27."
      },
      "chunk_id": "2"
    },
    {
      "content": "Push it into the machine as far as possible to make sure it is in the right position. \nOpen the lid of the pre-ground coffee compartment and check if this is clogged with coffee powder. To clean it, insert a spoon handle into the pre-ground coffee compartment and move the handle up and down until the clogged ground coffee falls down. Remove the brew group and remove all ground coffee that has fallen down. Place back the clean brew group.\nSwitch the machine back on.\nIf the problem is solved the AquaClean filter was not prepared well. Prepare the AquaClean filter before placing it back by following steps 1 and 2 in chapter 'Activating the AquaClean water filter (5 min).\nIf the lights continue to flash, the machine could be overheated. Switch the machine off, wait 30 minutes and switch it on again. If the lights are still flashing, contact the Consumer Care Center in your country. For contact details, see the international warranty leaflet.\n28HISTCOMMENTchanga 'MAX indication' to 'maximum indication'0falsefalse00false1000 012true0543falsefalse044true(auto)\n62Janette Weishaupt2019-02-25T14:25:1814307164968a5ea584d5b4dc3bdae86a1a8d06442424073truetruetruefalse01306763Janette Weishaupt2019-03-19T15:00:1811Topic1042407301 \n00false1000 012true050falsefalse00false(auto)\n3430Janette Weishaupt2019-02-25T14:25:51143091649bf38178d510145af9310f1f0b810c115424074truetruetruefalse01306765Janette Weishaupt2019-03-19T15:00:1811Topic1042407401 \n00false1000 012true050falsefalse00false(auto)\n63Janette Weishaupt2019-03-28T08:27:301. Rinsing the machine - US136768e9273913fd462e946df654ad51356a427985truetruetruefalse01314426Janette Weishaupt2019-03-28T08:38:506Topic10427985-111. Rinsing the machine2true6 cmfalsefalseIn This Section00truefalsetruefalse0falsefalsefalse3falseIn This Section|631false2false6 cmfalsefalseSee Also00truefalsetruefalse0falsetruefalse3falseSee Also|632true2false18 pxfalsetruePrevious1254falsefalsetruefalse0falsefalsefalse1truePrevious|633false2false18 pxfalsetrueNext1244falsefalsetruefalse0truefalsefalse1falseNext|634false2false48 pxtruetrueContents1224falsefalsetruefalse0falsefalsefalse1falseContents|635false2false48 pxfalsetrueIndex1234falsefalsetruetrue0falsefalsefalse1falseIndex|636false\n00false1000 08true0243falsetrue044true(auto)\n62Janette Weishaupt2019-03-28T08:30:35Cleaning table - OMNIA US1367703f635ea3a44d4e989ec041adabc402427987truetruetruefalse01314418Janette Weishaupt2019-03-28T08:32:216Topic10427987-11 Detachable parts\n When to clean\n How to clean\n Brew group\n Weekly\n Remove the brew group from the machine. Rinse it under the tap. \n Classic milk frother\n After every use\n First dispense hot water with the milk frother attached to the machine for thorough cleaning. Then remove the milk frother from the machine and disassemble it. Clean all parts under the tap or in the dishwasher.\n Pre-ground coffee compartment\n Check the pre-ground coffee compartment weekly to see if it is clogged.\n Unplug the machine and remove the brew group. Open the lid of the pre-ground coffee compartment and insert the spoon handle into it. Move the handle up and down until the clogged ground coffee falls down. Go to www.philips.com/coffee-care for detailed video instructions.\n Coffee grounds container\n Empty the coffee grounds container when prompted by the machine. Clean it weekly.\n Remove the coffee grounds container while the machine is switched on. Rinse it under the tap with some washing-up liquid or clean it in the dishwasher",
      "id": null,
      "title": "Fully automatic",
      "filepath": "11d43c39993c4c958a30ad1f011465b4.pdf",
      "url": "https://<blobname>.blob.core.windows.net/usermanuals/11d43c39993c4c958a30ad1f011465b4.pdf",
      "metadata": {
        "chunking": "orignal document size=1011. Scores=15.1114855 and None.Org Highlight count=64."
      },
      "chunk_id": "3"
    },
    {
      "content": "Remove flecks of limescale, grease, starch and \nalbumin (e.g. egg white) immediately. Corrosion \ncan form under such flecks.\nSpecial stainless steel cleaning products suitable \nfor hot surfaces are available from our after-sales \nservice or from specialist retailers. Apply a very \nthin layer of the cleaning product with a soft cloth.\nPlastic Hot soapy water: \nClean with a dish cloth and then dry with a soft \ncloth.\nDo not use glass cleaner or a glass scraper.\nPainted surfaces Hot soapy water: \nClean with a dish cloth and then dry with a soft \ncloth.\nControl panel Hot soapy water: \nClean with a dish cloth and then dry with a soft \ncloth.\nDo not use glass cleaner or a glass scraper.\nDoor panels Hot soapy water: \nClean with a dish cloth and then dry with a soft \ncloth.\nDo not use a glass scraper or a stainless steel \nscouring pad.\nDoor handle Hot soapy water: \nClean with a dish cloth and then dry with a soft \ncloth.\nIf descaler comes into contact with the door han-\ndle, wipe it off immediately. Otherwise, any stains \nwill not be able to be removed.\nAppliance exterior\nEnamel surfaces Hot soapy water or a vinegar solution: \nClean with a dish cloth and then dry with a soft \ncloth.\nSoften baked-on food residues with a damp cloth \nand soapy water. If there are heavy deposits of \ndirt, use a stainless steel scouring pad or oven \ncleaner.\nLeave the cooking compartment open to dry after \ncleaning.\nGlass cover for \nthe interior light-\ning\nHot soapy water: \nClean with a dish cloth and then dry with a soft \ncloth.\nIf the cooking compartment is heavily soiled, use \noven cleaner.\nDoor seal\nDo not remove.\nHot soapy water: \nClean with a dish cloth.\nDo not scour.\nStainless steel \ndoor cover\nStainless steel cleaner: \nObserve the manufacturer's instructions.\nDo not use stainless steel care products.\nRemove the door cover for cleaning.\nStainless steel \ninterior door \nframe\nStainless steel cleaner: \nObserve the manufacturer's instructions.\nThis can be used to remove discolouration.\nDo not use stainless steel care products.\nRails Hot soapy water: \nSoak and clean with a dish cloth or brush.\nPull-out system Hot soapy water: \nClean with a dish cloth or a brush.\nDo not remove the lubricant while the pull-out rails \nare pulled out \u2013 it is best to clean them when they \nare pushed in. Do not clean in the dishwasher.\nAccessories Hot soapy water: \nSoak and clean with a dish cloth or brush.\nIf there are heavy deposits of dirt, use a stainless \nsteel scouring pad.\n21\nen Rails\nNotes\n\u25a0 Slight differences in colour on the front of the \nappliance are caused by the use of different \nmaterials, such as glass, plastic and metal.\n\u25a0 Shadows on the door panels, which look like \nstreaks, are caused by reflections made by the \ninterior lighting.\n\u25a0 Enamel is baked on at very high temperatures.This \ncan cause some slight colour variation. This is \nnormal and does not affect operation.\nThe edges of thin trays cannot be completely \nenamelled. As a result, these edges can be rough. \nThis does not impair the anti-corrosion protection.\nKeeping the appliance clean\nAlways keep the appliance clean and remove dirt \nimmediately so that stubborn deposits of dirt do not \nbuild up.\nTips\n\u25a0 Clean the cooking compartment after each use. This \nwill ensure that dirt cannot be baked on.\n\u25a0 Always remove flecks of limescale, grease, starch \nand albumin (e.g. egg white) immediately.\n\u25a0 Use the universal pan for baking very moist cakes.\n\u25a0 Use suitable ovenware for roasting, e.g. a roasting \ndish.\npRails\nRailsWith good care and cleaning, your appliance will retain \nits appearance and remain fully functional for a long \ntime to come. This will tell you how to remove the \nshelves and clean them.\nDetaching and refitting the rails\n:Warning \u2013 Risk of burns! \nThe rails become very hot. Never touch the hot rails",
      "id": null,
      "title": "[en] Instruction manual",
      "filepath": "9001066094_B.pdf",
      "url": "https://<blobname>.blob.core.windows.net/usermanuals/9001066094_B.pdf",
      "metadata": {
        "chunking": "orignal document size=1019. Scores=14.332682 and None.Org Highlight count=54."
      },
      "chunk_id": "0"
    }
  ],
  "answer": "To clean the espresso machine, you need to remove the brew group from the machine and rinse it under the tap [doc1]. You should also clean the classic milk frother after every use by first dispensing hot water with the milk frother attached to the machine for thorough cleaning, then removing the milk frother from the machine and disassembling it. Clean all parts under the tap or in the dishwasher [doc1]. You can find more detailed information and video instructions on www.philips.com/coffee-care [doc1][doc2][doc3]. "
}
```


### Next steps
A good next step would be to create a Power Virtual Agents bot that uses this Azure Function to answer questions about your own data. You can integrate this PVA bot into your Microsoft Teams environment and make it available to your colleagues.