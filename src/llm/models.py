import os
from langchain_openai import ChatOpenAI
from enum import Enum
from pydantic import BaseModel
from typing import Tuple


class ModelProvider(str, Enum):
    """Enum for supported LLM providers"""
    OPENAI = "OpenAI"


class LLMModel(BaseModel):
    """Represents an LLM model configuration"""
    display_name: str
    model_name: str
    provider: ModelProvider

    def to_choice_tuple(self) -> Tuple[str, str, str]:
        """Convert to format needed for questionary choices"""
        return (self.display_name, self.model_name, self.provider.value)
    
    def has_json_mode(self) -> bool:
        """Check if the model supports JSON mode"""
        return True


# Define available models
AVAILABLE_MODELS = [
    LLMModel(
        display_name="4o(用这个刚刚好)",
        model_name="gpt-4o",
        provider=ModelProvider.OPENAI
    ),
    LLMModel(
        display_name="4.5(太花钱)",
        model_name="gpt-4.5-preview",
        provider=ModelProvider.OPENAI
    ),
]

# Create LLM_ORDER in the format expected by the UI
LLM_ORDER = [model.to_choice_tuple() for model in AVAILABLE_MODELS]
LLM_NAME_ORDER = [model.model_name for model in AVAILABLE_MODELS]
LLM_LIST_ORDER = [{
    "model_name": model.model_name,
    "display_name": model.display_name,
    "provider": model.provider.value
} for model in AVAILABLE_MODELS]

def get_model_info(model_name: str) -> LLMModel | None:
    """Get model information by model_name"""
    return next((model for model in AVAILABLE_MODELS if model.model_name == model_name), None)

def get_model(model_name: str, model_provider: ModelProvider) -> ChatOpenAI | None:
    if model_provider == ModelProvider.OPENAI:
        # Get and validate API key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Print error to console
            print(f"API Key Error: Please make sure OPENAI_API_KEY is set in your .env file.")
            raise ValueError("OpenAI API key not found.  Please make sure OPENAI_API_KEY is set in your .env file.")
        return ChatOpenAI(model=model_name, api_key=api_key)
    return None