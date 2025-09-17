import re
import requests
from openai import OpenAI
import markdown
import bleach
import json
import traceback
from utils import *


citation_guide = (
    "When providing your final answer, follow these strict citation guidelines to ensure clarity, professionalism, and factual accuracy:\n\n"

    "Inline, Contextual Citation:\n"
    "- Always cite sources **inline**, immediately **after the sentence or fact** they support.\n"
    "- Use clean **markdown hyperlinks** in this format: `[domain.name](https://example.com/article)` — the visible link text should be the domain name of the source.\n"

    "Clear and Concise Style:\n"
    "- Use the **domain name** as the source name: e.g., `[nasa.gov](https://www.nasa.gov/...)`, `[who.int](https://www.who.int/...)`, `[mayoclinic.org](https://www.mayoclinic.org/...)`, not full URLs or site titles.\n"
    "- Example:\n"
    "*The James Webb Telescope is capable of detecting infrared light from 13.6 billion years ago* [nasa.gov](https://www.nasa.gov/feature/goddard/2022/nasa-s-webb-reaches-alignment-milestone-optics-working-successfully).\n\n"

    "Do NOT:\n"
    "- Do **not** list all sources at the end of the answer.\n"
    "- Do **not** cite to sources that were never mentioned in the tool outputs."
)



def simple_search(query: str, api_key: str, base_url: str, language_model: str):

    yield {"type": "log", "content": f"Searching for \"{query}\"..."}

    top_urls = get_top_urls(query)
    if not top_urls:
        yield {"type": "output", "content": "Error searching. Try turning off VPN."}

    chunks = get_chunks_from_urls(top_urls, number_of_urls=15)
    if not chunks:
        yield {"type": "output", "content": "bug in fetching logic"}

    top_chunks = get_top_chunks(query, chunks, number_of_top_chunks=5)

    chunks_str = ""
    for i, chunk in enumerate(top_chunks, 1):
        chunks_str += f"--- Top Chunk #{i} ---\n{chunk}\n\n"

    system_prompt = (
        gather_contextual_info() +
        "You answer questions based on search results. But you never mention the search results themselves.\n\n" +
        citation_guide +
        "\n\nMake your Answer detailed."
    )

    prompt = (
        "Search Results:\n" + chunks_str + "\n\n---\n\n"
        "Question:\n" + query + " \n\n---\n\n"
        "Answer:"
    )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    yield {"type": "log", "content": "Generating output..."}

    response = client.chat.completions.create(
        model=language_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
    )

    if response.usage:
        yield {
            "type": "token_usage",
            "content": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    reply = response.choices[0].message.content

    reply = escape_outside_code_blocks(reply)
    reply = reply.replace("\n- ", "\n\n- ")
    reply = reply.replace("\n* ", "\n\n* ")
    reply = markdown.markdown(reply, extensions=['fenced_code'])


    yield {"type": "output", "content": reply}


def agentic_search(query: str, api_key: str, base_url: str, language_model: str):
    yield {"type": "log", "content": f"Research Initiated..."}

    
    
    # tools
    tools = [
        {
            "function": {
                "name": "internet_search",
                "description": "Use this tool to perform real-time internet searches and retrieve up-to-date, factual information from the web.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A specific query to search."
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Explain in a short one sentence what are you doing. End the explanation with elipses. E.g., \"Validating if that exists...\""
                        }
                    },
                    "required": ["query", "explanation"]
                }
            }
        }
    ]
    
    # prompt injection
    tools_list = []
    for tool_dis in tools:
        tools_list.append(tool_dis["function"])
    
    tools_instructions = ""
    for tool in tools_list:
        tools_instructions += (
            str(tool["name"])
            + ": "
            + "Call this tool to interact with the "
            + str(tool["name"])
            + " API. What is the "
            + str(tool["name"])
            + " API useful for? "
            + str(tool["description"])
            + ". Parameters: "
            + str(tool["parameters"])
            + " Required parameters: "
            + str(tool["parameters"]["required"])
            + "\n"
        )
    
    # tool example
    TOOL_EXAMPLE = """You will receive a JSON string containing a list of callable tools. Please parse this JSON string and return a JSON object containing the tool name and tool parameters. Here is an example of the tool list:

{"tools": [{"name": "add_numbers", "description": "Add two numbers together", "parameters": {"type": "object","properties": {"num1": {"type": "string","description": "First number, for example: 5","default": "0"},"num2": {"type": "string","description": "Second number, for example: 3","default": "0"}},"required": ["num1", "num2"]}},{"name": "multiply_numbers", "description": "Multiply two numbers", "parameters": {"type": "object","properties": {"num1": {"type": "string","description": "First number, for example: 4","default": "1"},"num2": {"type": "string","description": "Second number, for example: 6","default": "1"}},"required": ["num1", "num2"]}}]}

Based on this tool list, generate a JSON object to call a tool. For example, if you need to add 5 and 3, return:

{"tool": "add_numbers", "parameters": {"num1": "5", "num2": "3"}}

Please note that the above is just an example and does not mean that the add_numbers and multiply_numbers tools are currently available."""

    RETURN_FORMAT = '{"tool": "tool name", "parameters": {"parameter name": "parameter value"}}'
    
    INSTRUCTION = f"""
{TOOL_EXAMPLE}

Answer the following questions as best you can. You have access to the following APIs:
{tools_instructions}

Use the following format:
'''tool_json
{RETURN_FORMAT}
'''

Hint: To gather information comprehensively, tools can be used iteratively before responding to the user.
Include the detailed final answer only after you have thoroughly gathered all information.
Make your final response detailed. A detailed markdown formatted response to the user's query.
Do not make up information that you never saw in the tool results.

{citation_guide}

{gather_contextual_info()}

User query: {query}
"""
    
    conversation_history = [{"role": "system", "content": INSTRUCTION}]
    
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)

        social = True
        
        while True:
            response = client.chat.completions.create(
                model=language_model,
                messages=conversation_history,
                temperature=0.5,
            )
            
            if response.usage:
                yield {
                    "type": "token_usage",
                    "content": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                }
            
            response_content = response.choices[0].message.content
            
            pattern = r'\{\s*"tool":\s*"(.*?)",\s*"parameters":\s*\{(.*?)\}\s*\}'
            match = re.search(pattern, response_content, re.DOTALL)
            
            if match:
                tool = match.group(1)
                parameters = match.group(2)
                json_str = '{"tool": "' + tool + '", "parameters": {' + parameters + '}}'
                
                try:
                    parameters_dict = json.loads('{' + parameters + '}')
                    
                    if tool == "internet_search":
                        search_query = parameters_dict.get("query", "")

                        if social:
                            full_query = search_query + " reddit"
                        else:
                            full_query = search_query

                        explanation = parameters_dict.get("explanation", f"Searching for: {search_query}")
                        
                        yield {"type": "log", "content": {
                            "explanation": explanation,
                            "query": search_query
                        }}
                        
                        # search
                        top_urls = get_top_urls(full_query)
                        if not top_urls:
                            results = "No search results found."
                        else:
                            chunks = get_chunks_from_urls(top_urls, number_of_urls=8)
                            if not chunks:
                                results = "No content could be extracted from search results."
                            else:
                                top_chunks = get_top_chunks(search_query, chunks, number_of_top_chunks=5)
                                results = f"Results for \"{search_query}\":\n\n"
                                for i, chunk in enumerate(top_chunks, 1):
                                    results += f"--- Top Chunk #{i} ---\n{chunk}\n\n"
                        
                        # appending to history
                        conversation_history.append({"role": "assistant", "content": json_str})
                        conversation_history.append({"role": "user", "content": f"Tool {tool} returned:\n{results}"})

                        social = not social
                        
                        continue
                        
                except json.JSONDecodeError:
                    continue
            
            # no tool call. final response
            conversation_history.append({"role": "assistant", "content": response_content})
            
            # md to html
            formatted_response = escape_outside_code_blocks(response_content)
            formatted_response = formatted_response.replace("\n- ", "\n\n- ")
            formatted_response = formatted_response.replace("\n* ", "\n\n* ")
            formatted_response = markdown.markdown(formatted_response, extensions=['fenced_code'])
            
            yield {"type": "output", "content": formatted_response}
            break
            
    except Exception as e:
        traceback.print_exc()
        yield {"type": "error", "content": str(e)}
