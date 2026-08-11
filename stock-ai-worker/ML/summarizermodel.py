from transformers import pipeline

try:
    # We use "text2text-generation" which is the more accurate technical 
    # category for BART models like the one you are using.
    summarizer = pipeline(
        "text2text-generation", 
        model="sshleifer/distilbart-cnn-12-6", 
        framework="pt"
    )
    print("✅ Summarizer loaded via text2text-generation")
except Exception as e:
    print(f"⚠️ Pipeline failed: {e}")
    summarizer = None

def summarize_news(text):
    if summarizer:
        try:
            # We add a small prefix to help the model
            result = summarizer(f"summarize: {text}", max_length=40, min_length=10, do_sample=False)
            # Check for 'generated_text' (new standard) or 'summary_text' (old standard)
            return result[0].get('generated_text', result[0].get('summary_text', text[:100]))
        except Exception as e:
            print(f"⚠️ Summarization error: {e}")
            return text[:100] + "..."
    return text[:100] + "..."