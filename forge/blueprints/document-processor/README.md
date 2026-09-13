# Document Processor Blueprint

**Difficulty:** Intermediate
**Category:** Analysis
**Estimated Time:** 4-8 hours

---

## Intent

Build an application that analyzes, summarizes, transforms, or extracts information from documents. This pattern leverages Claude's ability to understand complex documents and use tools to structure output.

---

## When to Use This Blueprint

✅ **Good fit:**
- Contract analysis and extraction
- Research paper summarization
- Invoice/receipt processing
- Legal document review
- Report generation from data

❌ **Consider another blueprint:**
- Interactive Q&A → Conversational Assistant
- Code analysis → Code Review Agent
- Real-time chat → Conversational Assistant

---

## Capability Map

```
Required Skills                 Recommended Skills
─────────────────               ──────────────────
[first-message]                 [vision]
       │                              │
       ▼                              ▼
[system-prompts]               [streaming]
       │                              │
       ▼                              ▼
[tool-basics] ───► [tool-execution]  [context-management]
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Processor                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ Document │    │   Processor  │    │     Output       │  │
│  │  Input   │───►│     Core     │───►│    Formatter     │  │
│  └──────────┘    └──────┬───────┘    └──────────────────┘  │
│                         │                                    │
│  ┌──────────────────────┴────────────────────────────────┐  │
│  │                    Tool Registry                       │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │  Extract    │ │  Summarize  │ │    Classify     │  │  │
│  │  │  Entities   │ │   Section   │ │    Document     │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘  │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │   Format    │ │  Validate   │ │     Store       │  │  │
│  │  │   Output    │ │    Data     │ │    Result       │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                         │                                    │
│                         ▼                                    │
│                ┌────────────────┐                           │
│                │  Claude SDK    │                           │
│                │  (Tool Use)    │                           │
│                └────────────────┘                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **Document Input**: Accept various formats (text, PDF, images)
2. **Processor Core**: Orchestrate analysis with Claude
3. **Tool Registry**: Available extraction and transformation tools
4. **Output Formatter**: Structure results for consumption

---

## Decision Points

| Decision | Options | Considerations |
|----------|---------|----------------|
| **Input Format** | Text, PDF, Image, Multiple | Start simple, expand as needed |
| **Processing Mode** | Single-pass, Iterative, Chunked | Depends on document length |
| **Output Format** | JSON, Markdown, Custom Schema | JSON for integration, Markdown for human review |
| **Tool Complexity** | Basic extraction, Advanced analysis | Start basic, add tools incrementally |
| **Error Handling** | Strict, Lenient | Strict for critical data, lenient for best-effort |

---

## Core Tools

The document processor typically uses these tool patterns:

### 1. Entity Extraction
```python
{
    "name": "extract_entities",
    "description": "Extract named entities from the document",
    "input_schema": {
        "type": "object",
        "properties": {
            "entity_type": {"type": "string", "enum": ["person", "organization", "date", "money", "location"]},
            "entities": {"type": "array", "items": {"type": "string"}}
        }
    }
}
```

### 2. Section Summarization
```python
{
    "name": "summarize_section",
    "description": "Provide a summary of a document section",
    "input_schema": {
        "type": "object",
        "properties": {
            "section_name": {"type": "string"},
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}}
        }
    }
}
```

### 3. Classification
```python
{
    "name": "classify_document",
    "description": "Classify the document type and category",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_type": {"type": "string"},
            "confidence": {"type": "number"},
            "categories": {"type": "array", "items": {"type": "string"}}
        }
    }
}
```

---

## Validation Criteria

Your implementation is complete when:

- [ ] Can accept documents in chosen input format(s)
- [ ] Successfully extracts requested information
- [ ] Uses tools to structure output
- [ ] Handles documents exceeding context window
- [ ] Provides confidence indicators where appropriate
- [ ] Gracefully handles malformed or unexpected input
- [ ] Outputs in chosen format consistently

---

## Publication Targets

- **npm/PyPI**: Document processing library
- **Docker**: Containerized processing service
- **API**: REST endpoint for document submission
- **Lambda/Cloud Functions**: Serverless document processor

---

## File Structure

```
my-doc-processor/
├── src/
│   ├── main.py              # Entry point
│   ├── processor.py         # Core processing logic
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── extraction.py    # Entity extraction tools
│   │   ├── summarization.py # Summary tools
│   │   └── classification.py
│   ├── input/
│   │   ├── text.py
│   │   ├── pdf.py           # If PDF support chosen
│   │   └── image.py         # If vision support chosen
│   └── output/
│       ├── json_formatter.py
│       └── markdown_formatter.py
├── tests/
│   └── ...
├── sample_documents/        # Test documents
├── requirements.txt
└── README.md
```

---

## Examples

See the `examples/` directory for:
- `simple_extractor.py`: Basic entity extraction
- `contract_analyzer.py`: Legal contract analysis
- `invoice_processor.py`: Invoice data extraction
