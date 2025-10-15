# AI-Init Architecture Design

## Overview

The `ml_server ainit` command will provide an intelligent, interactive workflow to automatically generate MLServer configuration files and predictor classes from Jupyter notebooks. This eliminates the manual setup process and makes ML model deployment accessible to users without deep MLOps knowledge.

## Core Concept

```bash
ml_server ainit --file inference_example.ipynb
```

This command will:
1. **Analyze** the notebook to extract ML patterns, models, and data flow
2. **Generate** `mlserver.yaml`, predictor class, and other configuration files
3. **Validate** the generated configuration
4. **Provide** an interactive setup experience

## Architecture Components

### 1. Notebook Analysis Engine

**Purpose**: Extract meaningful ML patterns from Jupyter notebooks

**Key Features**:
- **AST Parser**: Parse Python code cells to extract imports, function definitions, class definitions
- **Pattern Recognition**: Identify ML frameworks (sklearn, catboost, pytorch, etc.)
- **Data Flow Analysis**: Track model loading, preprocessing pipelines, prediction functions
- **Artifact Detection**: Find model files, preprocessors, feature configurations
- **API Pattern Extraction**: Identify predict/predict_proba methods and their signatures

**Implementation**:
```python
class NotebookAnalyzer:
    def analyze(self, notebook_path: str) -> AnalysisResult:
        # Parse notebook cells
        # Extract code patterns
        # Identify ML frameworks and patterns
        # Return structured analysis
```

### 2. Template Generation System

**Purpose**: Generate MLServer configuration files based on analysis

**Templates**:
- **mlserver.yaml**: Server configuration with auto-detected settings
- **predictor_*.py**: Predictor class with extracted logic
- **requirements.txt**: Dependencies based on detected frameworks
- **Dockerfile**: Container configuration
- **.dockerignore**: Standard exclusions

**Implementation**:
```python
class TemplateGenerator:
    def generate_mlserver_config(self, analysis: AnalysisResult) -> dict
    def generate_predictor_class(self, analysis: AnalysisResult) -> str
    def generate_requirements(self, analysis: AnalysisResult) -> list
```

### 3. LLM Integration Layer

**Purpose**: Leverage public LLM APIs to enhance code analysis and generation

**Strategy**: Use **no-API-key required** services:
- **Hugging Face Inference API**: Free tier for code analysis models
- **Together AI**: Community models with free quotas
- **Replicate**: Public models for code understanding
- **Local Models**: Fallback to local code analysis

**Use Cases**:
- **Code Understanding**: Enhance pattern recognition with LLM insights
- **Documentation Generation**: Create comments and docstrings
- **Configuration Refinement**: Suggest optimal MLServer settings
- **Error Resolution**: Help fix common configuration issues

**Implementation**:
```python
class LLMClient:
    def analyze_code_patterns(self, code: str) -> dict
    def suggest_configuration(self, context: dict) -> dict
    def generate_documentation(self, code: str) -> str
```

### 4. Interactive CLI Workflow

**Purpose**: Provide guided, user-friendly setup experience

**Workflow Steps**:

#### Phase 1: Discovery
```
🔍 Analyzing notebook: inference_example.ipynb
✅ Detected: CatBoost classifier
✅ Found: Preprocessing pipeline
✅ Identified: Feature engineering logic
```

#### Phase 2: Configuration
```
🎯 Configuring MLServer...

Classifier Name: [titanic-survival-predictor]
API Version: [v1]
Port: [8000]
Enable Metrics: [Y/n]
```

#### Phase 3: Generation
```
🚀 Generating files...
✅ mlserver.yaml
✅ predictor_catboost.py
✅ requirements.txt
✅ Dockerfile
```

#### Phase 4: Validation
```
🔧 Validating configuration...
✅ Predictor class syntax
✅ MLServer config schema
⚠️  Missing: artifacts/model.pkl (run training first)
```

### 5. Configuration Validator

**Purpose**: Ensure generated configurations are valid and complete

**Validation Checks**:
- **Syntax**: Python syntax validation for generated predictor
- **Schema**: MLServer YAML schema compliance
- **Dependencies**: Required packages availability
- **Artifacts**: Model files and preprocessors existence
- **Integration**: Predictor class compatibility with MLServer

### 6. Code Pattern Library

**Purpose**: Maintain patterns for different ML frameworks and use cases

**Patterns**:
```python
PATTERNS = {
    "catboost": {
        "imports": ["catboost", "CatBoostClassifier"],
        "model_load": "pickle.load",
        "predict_method": "predict_proba",
        "preprocessing": "sklearn.preprocessing"
    },
    "sklearn": {
        "imports": ["sklearn"],
        "model_load": ["pickle.load", "joblib.load"],
        "predict_method": ["predict", "predict_proba"],
    },
    "pytorch": {
        "imports": ["torch", "pytorch"],
        "model_load": "torch.load",
        "predict_method": "forward"
    }
}
```

## Implementation Plan

### Phase 1: Core Analysis Engine
1. **Notebook Parser**: Parse .ipynb files and extract code cells
2. **AST Analysis**: Extract imports, functions, classes, variables
3. **Pattern Matching**: Identify ML frameworks and common patterns
4. **Basic Template Generation**: Generate simple mlserver.yaml and predictor

### Phase 2: LLM Integration
1. **LLM Client**: Integrate with public LLM APIs (no API keys)
2. **Code Analysis Enhancement**: Use LLM for better pattern recognition
3. **Configuration Suggestions**: LLM-powered configuration optimization
4. **Documentation**: Auto-generate comments and documentation

### Phase 3: Interactive Experience
1. **CLI Interface**: Interactive prompts and user guidance
2. **Validation System**: Comprehensive validation and error checking
3. **Error Recovery**: Help users fix common issues
4. **Testing Integration**: Validate generated configurations

### Phase 4: Advanced Features
1. **Multi-Framework Support**: Support for PyTorch, TensorFlow, etc.
2. **Complex Patterns**: Handle ensemble models, pipelines, etc.
3. **Deployment Optimization**: Performance tuning suggestions
4. **Monitoring Integration**: Metrics and observability setup

## Example Workflow

```bash
# User starts with just a notebook
$ ls
inference_example.ipynb

# Run AI-init
$ ml_server ainit --file inference_example.ipynb

🔍 Analyzing notebook...
✅ Detected CatBoost classifier with preprocessing pipeline
✅ Found feature engineering: alone, adult_male, who

🎯 Configuration:
   Classifier: titanic-survival-predictor
   Framework: CatBoost + sklearn preprocessing
   Features: 10 input features detected

📝 Generating files...
✅ mlserver.yaml (server config)
✅ predictor_catboost.py (predictor class)
✅ requirements.txt (dependencies)
✅ Dockerfile (containerization)

🔧 Validating...
✅ Configuration valid
⚠️  Run training to create artifacts/

🚀 Ready! Try:
   ml_server serve
```

## Benefits

1. **Zero Manual Configuration**: Automatically generate all required files
2. **Framework Agnostic**: Support multiple ML frameworks
3. **Best Practices**: Generated code follows MLServer patterns
4. **Interactive Guidance**: User-friendly setup experience
5. **Validation**: Ensure configurations work before deployment
6. **Extensible**: Easy to add new patterns and frameworks

## Technical Considerations

### Public LLM Integration
- **Rate Limiting**: Handle API rate limits gracefully
- **Fallback**: Local analysis when LLM unavailable
- **Privacy**: Only send code patterns, not sensitive data
- **Caching**: Cache LLM responses for common patterns

### Notebook Compatibility
- **Execution State**: Don't require notebook to be executed
- **Variable Tracking**: Handle undefined variables gracefully
- **Cell Dependencies**: Understand cell execution order
- **Error Handling**: Graceful degradation on parse errors

### Generated Code Quality
- **Readable**: Generate clean, documented code
- **Maintainable**: Follow Python best practices
- **Testable**: Include validation and error handling
- **Optimized**: Efficient model loading and inference

This architecture provides a comprehensive foundation for implementing the AI-powered initialization feature that will make MLServer accessible to a much broader audience.