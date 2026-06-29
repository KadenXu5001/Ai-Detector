from signals import call_llm_signal, call_style_signal, combine_scores

inputs = [
    (
        "clearly_ai",
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications. Furthermore, stakeholders across "
        "various sectors must collaborate to ensure responsible deployment.",
    ),
    (
        "clearly_human",
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming. the broth was fine but they put WAY too much sodium in it and "
        "i was thirsty for like three hours after. my friend got the spicy version and "
        "said it was better. probably won't go back unless someone drags me there",
    ),
    (
        "formal_human",
        "The relationship between monetary policy and asset price inflation has been "
        "extensively studied in the literature. Central banks face a fundamental tension "
        "between their mandate for price stability and the unintended consequences of "
        "prolonged low interest rates on equity and real estate valuations.",
    ),
    (
        "edited_ai",
        "I've been thinking a lot about remote work lately. There are genuine tradeoffs — "
        "flexibility and no commute on one side, isolation and blurred work-life boundaries "
        "on the other. Studies show productivity varies widely by individual and role type.",
    ),
]

print(f"{'label':<16} {'llm':>6} {'style':>6} {'combined':>9} {'attribution'}")
print("-" * 55)

for label, text in inputs:
    llm   = call_llm_signal(text)
    style = call_style_signal(text)
    combined = combine_scores(llm, style)

    if combined < 0.35:
        attribution = "likely_human"
    elif combined > 0.65:
        attribution = "likely_ai"
    else:
        attribution = "uncertain"

    print(f"{label:<16} {llm:>6.3f} {style:>6.3f} {combined:>9.3f}  {attribution}")
