import os
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'job_classifier_model')
print(f"Model directory: {MODEL_DIR}")
print(f"Files in directory: {os.listdir(MODEL_DIR)}")

try:
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    print("Tokenizer loaded successfully!")
    
    print("Loading model...")
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    print("Model loaded successfully!")
    
    # Test inference
    test_text = "This is a test job description"
    inputs = tokenizer(test_text, return_tensors="pt", truncation=True, padding=True)
    
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_class_id = logits.argmax(dim=-1).item()
    
    print(f"Test prediction: {predicted_class_id}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc() 