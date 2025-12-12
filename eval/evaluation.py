import evaluate
import numpy as np

def inference(messages):
    generation_args = {
        "max_new_tokens": 512,
        "return_full_text": False,
        "do_sample": False,
    }

    outputs = pipe(messages, **generation_args)
    return outputs[0]['generated_text']

# ROUGE
rouge_metric = evaluate.load("rouge")

def calculate_rouge(row):
    messages = [
        {"role": "user", "content": row['instruction'] + row['input']},
    ]
    
    response = inference(messages)

    result = rouge_metric.compute(predictions=[response], references=[row['output']], use_stemmer=True)
    
    # Scale results to percentages
    result = {key: value * 100 for key, value in result.items()}
    result['response'] = response
    return result

metricas = dataset['test'].map(calculate_rouge, batched=False)
print("Rouge 1 Mean: ",np.mean(metricas['rouge1']))
print("Rouge 2 Mean: ",np.mean(metricas['rouge2']))
print("Rouge L Mean: ",np.mean(metricas['rougeL']))
print("Rouge Lsum Mean: ",np.mean(metricas['rougeLsum']))

# BLEU
bleu_metric = evaluate.load("bleu")

def calculate_bleu(row):
    result = bleu_metric.compute(predictions=[row["response"]], references=[row['output']])
    
    # Scale results to percentages directly
    result = {key: value * 100 for key, value in result.items()}
    return result

metricas = metricas.map(calculate_bleu, batched=False)
print("BLEU: ",np.mean(metricas['bleu']))