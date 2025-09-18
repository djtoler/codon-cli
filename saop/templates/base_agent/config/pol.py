import requests
import json

def fetch_openrouter_models():
    """Fetches raw model data from the OpenRouter API."""
    print("Fetching latest model data from OpenRouter...")
    response = requests.get("https://openrouter.ai/api/v1/models")
    response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
    return response.json()

def process_and_convert_pricing(raw_data):
    """
    Processes raw model data, converting prices to cost per 1 million tokens
    and structuring it for output.
    """
    processed_data = {}
    
    for model in raw_data['data']:
        try:
            # Handle provider name extraction safely
            top_provider = model.get('top_provider', {}) or {}
            provider_name = top_provider.get('name', 'N/A')
            
            # Original prices are per 1k tokens
            prompt_cost_1k = float(model['pricing']['prompt'])
            completion_cost_1k = float(model['pricing']['completion'])
            
            # Convert to cost per 1M tokens
            prompt_cost_1m = prompt_cost_1k * 1000
            completion_cost_1m = completion_cost_1k * 1000
            
            processed_data[model['id']] = {
                'context_length': model.get('context_length'),
                'provider': provider_name,
                'pricing': {
                    'prompt_per_1k_tokens': prompt_cost_1k,
                    'completion_per_1k_tokens': completion_cost_1k,
                    'prompt_per_1m_tokens': prompt_cost_1m,
                    'completion_per_1m_tokens': completion_cost_1m
                }
            }
        except (KeyError, TypeError, ValueError) as e:
            print(f"Skipping model due to parsing error: {model.get('id', 'Unknown')} - {e}")
            
    return processed_data

def save_to_json(data, filename='openrouter_pricing_converted.json'):
    """Saves the provided data to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Pricing data saved to '{filename}'")

def print_pricing_table(pricing_data):
    """Prints a formatted pricing table to the console."""
    print(f"\n{'='*125}")
    print(f"{'MODEL ID':<45} {'INPUT/1M':<12} {'OUTPUT/1M':<12} {'CONTEXT':<12} {'PROVIDER'}")
    print(f"{'='*125}")
    
    # Sort models by input cost for easier comparison
    sorted_models = sorted(pricing_data.items(), key=lambda x: x[1]['pricing']['prompt_per_1m_tokens'])
    
    for model_id, data in sorted_models:
        input_cost = f"${data['pricing']['prompt_per_1m_tokens']:.2f}"
        output_cost = f"${data['pricing']['completion_per_1m_tokens']:.2f}"
        context = f"{data['context_length']:,}" if data['context_length'] else "N/A"
        provider = data['provider']
        
        print(f"{model_id:<45} {input_cost:<12} {output_cost:<12} {context:<12} {provider}")
    
    print(f"{'='*125}")
    print(f"Total models processed: {len(pricing_data)}")

def print_top_models(pricing_data, limit=10, paid_only=False):
    """Prints the cheapest models for quick reference, optionally filtering for paid models."""
    if paid_only:
        title = f"💰 TOP {limit} CHEAPEST PAID MODELS (by input cost/1M)"
        # Filter out models where input or output cost is zero or less
        filtered_models = {k: v for k, v in pricing_data.items() 
                           if v['pricing']['prompt_per_1m_tokens'] > 0 and v['pricing']['completion_per_1m_tokens'] > 0}
    else:
        title = f"🏆 TOP {limit} CHEAPEST MODELS (by input cost/1M, incl. free)"
        filtered_models = pricing_data
        
    print(f"\n{title}")
    print(f"{'-'*80}")
    
    sorted_models = sorted(filtered_models.items(), key=lambda x: x[1]['pricing']['prompt_per_1m_tokens'])[:limit]
    
    for i, (model_id, data) in enumerate(sorted_models, 1):
        input_cost = data['pricing']['prompt_per_1m_tokens']
        output_cost = data['pricing']['completion_per_1m_tokens']
        
        print(f"{i:2d}. {model_id}")
        print(f"    Input: ${input_cost:7.2f}/1M | Output: ${output_cost:7.2f}/1M")
        print(f"    Context: {data['context_length']:,} tokens | Provider: {data['provider']}")
        print()

if __name__ == "__main__":
    print("OpenRouter Model Pricing Tool")
    print("=" * 50)
    
    try:
        # 1. Fetch raw data from the API
        raw_model_data = fetch_openrouter_models()
        
        # 2. Process data and convert prices
        pricing_data = process_and_convert_pricing(raw_model_data)
        
        # 3. Print informative tables to the console
        print_pricing_table(pricing_data)
        print_top_models(pricing_data, limit=10, paid_only=False) # Top 10 cheapest overall
        print_top_models(pricing_data, limit=10, paid_only=True)  # Top 10 cheapest paid
        
        # 4. Save the processed data with converted prices to a JSON file
        save_to_json(pricing_data)
        
    except requests.RequestException as e:
        print(f"Error: Could not fetch data from OpenRouter. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")