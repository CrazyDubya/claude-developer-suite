"""
Simple Document Extractor

A minimal example of the document-processor blueprint.
Demonstrates entity extraction using Claude's tool use.
"""

import json
import os
from anthropic import Anthropic


# Define extraction tools
EXTRACTION_TOOLS = [
    {
        "name": "extract_entities",
        "description": "Extract named entities found in the document. Call this tool to report each type of entity found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["person", "organization", "date", "money", "location"],
                    "description": "The type of entity being extracted"
                },
                "entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of entities of this type found in the document"
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence score for this extraction"
                }
            },
            "required": ["entity_type", "entities", "confidence"]
        }
    },
    {
        "name": "extraction_complete",
        "description": "Call this when all entities have been extracted from the document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what was extracted"
                }
            },
            "required": ["summary"]
        }
    }
]


class SimpleExtractor:
    """A simple document entity extractor."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic()
        self.model = model

    def extract(self, document: str) -> dict:
        """Extract entities from a document."""
        extracted = {
            "person": [],
            "organization": [],
            "date": [],
            "money": [],
            "location": []
        }

        messages = [
            {
                "role": "user",
                "content": f"""Analyze this document and extract all named entities.
Use the extract_entities tool for each type of entity you find.
When finished, call extraction_complete.

Document:
---
{document}
---"""
            }
        ]

        # Process tool calls until complete
        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system="""You are a document analysis assistant. Extract all named entities
from the provided document using the available tools. Be thorough but precise.
Only extract entities that are clearly present in the text.""",
                tools=EXTRACTION_TOOLS,
                messages=messages,
            )

            # Check if we're done
            if response.stop_reason == "end_turn":
                break

            # Process tool uses
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if block.name == "extract_entities":
                        # Store extracted entities
                        entity_type = block.input["entity_type"]
                        entities = block.input["entities"]
                        extracted[entity_type].extend(entities)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Recorded {len(entities)} {entity_type} entities"
                        })

                    elif block.name == "extraction_complete":
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Extraction complete"
                        })
                        # Return results
                        return {
                            "extracted": extracted,
                            "summary": block.input["summary"]
                        }

            # Continue the conversation with tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return {"extracted": extracted, "summary": "Extraction completed"}


def main():
    """Demo the extractor with a sample document."""
    sample_document = """
    MEETING NOTES - Q4 Planning Session
    Date: December 15, 2024
    Location: San Francisco, CA

    Attendees:
    - Sarah Johnson (CEO)
    - Michael Chen (CFO)
    - Emily Rodriguez (VP Engineering)

    Discussion Points:

    1. Budget Review
       The Q3 results showed revenue of $2.4 million, exceeding our target of $2.1 million.
       Michael presented the Q4 budget proposal of $850,000 for operations.

    2. Expansion Plans
       Sarah announced plans to open a new office in Austin, Texas by March 2025.
       Partnership discussions with Acme Corporation are progressing well.

    3. Product Roadmap
       Emily outlined the engineering timeline for the new features.
       Target launch date: February 1, 2025.

    Next meeting scheduled for January 10, 2025 in New York.
    """

    print("Document Extractor Demo")
    print("=" * 50)

    extractor = SimpleExtractor()
    results = extractor.extract(sample_document)

    print("\nExtracted Entities:")
    print("-" * 30)

    for entity_type, entities in results["extracted"].items():
        if entities:
            print(f"\n{entity_type.upper()}:")
            for entity in set(entities):  # Deduplicate
                print(f"  - {entity}")

    print(f"\n{'-' * 30}")
    print(f"Summary: {results['summary']}")


if __name__ == "__main__":
    if os.environ.get("FORGE_VALIDATION_MODE"):
        print("✓ Example validated (syntax check only)")
    else:
        main()
