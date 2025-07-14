import openai

def expand_query(user_input, session_history):
    if not session_history:
        return user_input  # 文脈がなければそのまま返す

    context = session_history[-4:]  # 直近2往復分（最大4つ）
    context_text = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in context])

    prompt = [
        {"role": "system", "content": "あなたは曖昧な質問を明確な検索クエリに変換するAIです。"},
        {"role": "user", "content": f"""以下は直前の会話です：

{context_text}

その上で、ユーザーの次の発言を明確な検索文にしてください。
ユーザーの質問：「{user_input}」

→ 変換後の検索文（日本語で）：
"""}
    ]

    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=prompt,
        temperature=0.3,
        max_tokens=100
    )

    expanded = response.choices[0].message.content.strip()
    print("[Query Expansion] Original:", user_input)
    print("[Query Expansion] Expanded:", expanded)
    return expanded if expanded else user_input
