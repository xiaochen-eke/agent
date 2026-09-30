import os; os.environ['no_proxy']='*'
from pipeline import GenerationStage
g = GenerationStage(api_key='test')
if g.lora_available:
    print('LoRA OK - PeftModelForCausalLM')
else:
    print('LoRA FAIL - using GLM-4-Flash')
