# Model Configuration

## Overview

The subtitle translation service now uses a centralized model configuration system. The AI model is defined in only one place - the configuration file - and all components read from this single source of truth.

## Configuration Location

The model is configured in `config/config.yaml`:

```yaml
api:
  openai:
    api_key: ${OPENAI_API_KEY}
    model: gpt-4o-mini  # Model defined in config only
    temperature: 0.3
    max_tokens: 4000
```

## How It Works

### 1. Centralized Configuration
- **Single Source**: Model is defined only in `config/config.yaml`
- **No Hardcoding**: No model names are hardcoded in source files
- **Easy Changes**: Change the model in one place to affect the entire system

### 2. Priority Order
The system uses this priority order to determine which model to use:

1. **Configuration File**: `config/config.yaml` (highest priority)
2. **Environment Variable**: `OPENAI_MODEL` (fallback)
3. **Default**: `gpt-4o-mini` (final fallback)

### 3. Model Validation
The system validates that the configured model is supported before using it.

## Available Models

### GPT-4o-mini (Default)
- **Cost**: $0.00075/1K tokens
- **Quality**: Excellent
- **Speed**: Fast
- **Best for**: Most use cases

### GPT-3.5-turbo
- **Cost**: $0.0035/1K tokens
- **Quality**: Very Good
- **Speed**: Fast
- **Best for**: Budget-conscious users

### GPT-3.5-turbo-instruct
- **Cost**: $0.0035/1K tokens
- **Quality**: Very Good
- **Speed**: Fast
- **Best for**: Most affordable option

### GPT-3.5-turbo-16k
- **Cost**: $0.007/1K tokens
- **Quality**: Excellent
- **Speed**: Fast
- **Best for**: Larger context windows

## Changing the Model

### Option 1: Edit Configuration File
Edit `config/config.yaml`:
```yaml
api:
  openai:
    model: gpt-3.5-turbo  # Change to desired model
```

### Option 2: Environment Variable
Set in your `.env` file:
```bash
OPENAI_MODEL=gpt-3.5-turbo
```

### Option 3: Command Line
```bash
OPENAI_MODEL=gpt-3.5-turbo python run_background_service.py
```

## Code Structure

### ModelConfig Class
The `src/config/model_config.py` module provides:

- **Model validation**: Ensures only supported models are used
- **Cost estimation**: Calculate costs for different models
- **Model information**: Get details about each model
- **Centralized access**: Single point to get the current model

### Usage in Code
```python
from config.model_config import ModelConfig

# Get the configured model
model = ModelConfig.get_model(config_manager)

# Get model information
info = ModelConfig.get_model_info(model)

# Estimate cost
cost = ModelConfig.get_cost_estimate(model, token_count)
```

## Benefits

### 1. Maintainability
- **Single Point of Change**: Update model in one place
- **No Scattered Configuration**: All model settings centralized
- **Easy Testing**: Change models for testing without code changes

### 2. Flexibility
- **Environment Override**: Override config with environment variables
- **Runtime Changes**: Change models without restarting services
- **Validation**: Automatic validation of model names

### 3. Cost Management
- **Cost Estimation**: Built-in cost calculation
- **Model Comparison**: Easy comparison of different models
- **Budget Control**: Choose models based on cost requirements

## Migration from Old System

If you were previously using hardcoded models:

1. **Remove hardcoded models** from source files
2. **Add model to config** in `config/config.yaml`
3. **Use ModelConfig.get_model()** instead of hardcoded strings

### Before (Old Way)
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",  # Hardcoded
    messages=messages
)
```

### After (New Way)
```python
model = ModelConfig.get_model(config_manager)
response = client.chat.completions.create(
    model=model,  # From configuration
    messages=messages
)
```

## Troubleshooting

### Model Not Found
If you get an error about an unsupported model:

1. Check `config/config.yaml` for valid model name
2. Verify the model is in `ModelConfig.AVAILABLE_MODELS`
3. Use `ModelConfig.list_available_models()` to see all options

### Configuration Not Loading
If the model configuration isn't being read:

1. Check that `config/config.yaml` exists
2. Verify the file format is valid YAML
3. Ensure the config manager is properly initialized

### Environment Variable Override
To test with a different model temporarily:

```bash
OPENAI_MODEL=gpt-3.5-turbo python your_script.py
```

This will override the configuration file setting for this run only.
