import torch
import sys
import re
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"

def clean_output_text(text: str) -> str:
    """Làm sạch ký tự rác hoặc từ thừa bị sót lại do bỏ qua thẻ </think>"""
    text = text.strip()
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    
    # Loại bỏ các từ thừa phổ biến do tokenization prefix như 'nghèn', 'nghẹn' ở đầu chuỗi
    text = re.sub(r'^(nghèn|nghẹn|nghẽn|[^\w\s\u00C0-\u1EF9]+)\s*', '', text, flags=re.IGNORECASE)
    
    # Viết hoa chữ cái đầu tiên nếu là chữ cái
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text

def main():
    print("==========================================================")
    print("🚀 CHẠY THỬ MÔ HÌNH QWEN3-8B TRÊN GPU RTX 4060 (8GB VRAM)")
    print(f"📂 Nguồn mô hình: {MODEL_PATH}")
    print("==========================================================")

    # 1. Cấu hình BitsAndBytes 4-bit (~5GB VRAM)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    print("\n[1/2] Đang nạp Tokenizer & Mô hình 4-bit (Transformers + BitsAndBytes)...")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_PATH,
        trust_remote_code=True
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        quantization_config=bnb_config,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16
    )
    print("✓ Đã nạp thành công mô hình vào VRAM!")

    # 2. Thử nghiệm sinh văn bản
    prompt = sys.argv[1] if len(sys.argv) > 1 else "hãy viết 1 bài văn ngắn để miêu tả về thành phố hà nội"
    print(f"\n[2/2] Prompt: \"{prompt}\"")
    print("\n=================== KẾT QUẢ MÔ HÌNH ===================")

    messages = [
        {"role": "system", "content": "Bạn là một nhà văn / thi sĩ Việt Nam am hiểu sâu sắc văn hóa và ngôn ngữ Việt."},
        {"role": "user", "content": prompt}
    ]

    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        prompt_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
    else:
        prompt_text = f"<|im_start|>system\nBạn là một nhà văn Việt Nam.<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

    # Bypass CoT reasoning to directly generate answer
#    prompt_text = prompt_text + "</think>\n"
    inputs = tokenizer(prompt_text, return_tensors="pt").to("cuda")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=600,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id
        )

    raw_response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    cleaned_response = clean_output_text(raw_response)

    print(cleaned_response)
    print("==========================================================")

if __name__ == "__main__":
    main()
