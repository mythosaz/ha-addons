#!/usr/bin/env python3
"""
Test script for OpenAI Responses API
"""

import os
from openai import OpenAI

# Get API key from environment
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY environment variable not set")
    exit(1)

client = OpenAI(api_key=api_key)

print("Testing Responses API...")
print("=" * 60)

try:
    response = client.responses.create(
        model="gpt-5.2",
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You are a creative assistant that helps generate image prompts."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Create a short test prompt for a sunset scene."
                    }
                ]
            }
        ],
        text={
            "format": {"type": "text"},
            "verbosity": "medium"
        },
        reasoning={
            "effort": "medium",
            "summary": "auto"
        },
        tools=[
            {
                "type": "web_search",
                "user_location": {
                    "type": "approximate"
                },
                "search_context_size": "medium"
            }
        ],
        store=True
    )

    print("Response received!")
    print("=" * 60)
    print(f"Response type: {type(response)}")
    print(f"Response attributes: {dir(response)}")
    print("=" * 60)

    # Check if response has output
    if hasattr(response, 'output'):
        print(f"Output type: {type(response.output)}")
        print(f"Output value: {response.output}")
        print("=" * 60)

        # Try to extract text
        if response.output:
            for idx, item in enumerate(response.output):
                print(f"Output item {idx}: {type(item)}")
                print(f"  Attributes: {dir(item)}")
                if hasattr(item, 'content'):
                    print(f"  Content: {item.content}")
                    for cidx, content_item in enumerate(item.content):
                        print(f"    Content item {cidx}: {type(content_item)}")
                        print(f"      Type: {getattr(content_item, 'type', 'N/A')}")
                        if hasattr(content_item, 'text'):
                            print(f"      Text: {content_item.text}")

    # Check for usage/tokens
    if hasattr(response, 'usage'):
        print("=" * 60)
        print(f"Usage: {response.usage}")
        if hasattr(response.usage, 'input_tokens'):
            print(f"  Input tokens: {response.usage.input_tokens}")
        if hasattr(response.usage, 'output_tokens'):
            print(f"  Output tokens: {response.usage.output_tokens}")
        if hasattr(response.usage, 'total_tokens'):
            print(f"  Total tokens: {response.usage.total_tokens}")

    print("=" * 60)
    print("\nFull response object:")
    print(response)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
