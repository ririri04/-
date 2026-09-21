"""Fixed caption templates used for every post (no AI-generated text).

The leading "." lines are intentional: Instagram/X collapse truly empty
lines when rendering a caption, so a single "." per line is the standard
trick to keep the vertical spacing before the visible text.
"""

INSTAGRAM_CAPTION = (
    "📷\n"
    "#福岡撮影会 #被写体モデル\n"
    "#ポートレート #portrait\n"
    "#香乃ほのか @b_palette_promotion"
)

X_CAPTION_MORNING = (
    "おはようございます🤍\n"
    ".\n.\n.\n.\n.\n.\n.\n.\n"
    "#福岡撮影会 #被写体モデル\n"
    "#ポートレート #portrait\n"
    "#香乃ほのか @b_palette_p"
)

X_CAPTION_EVENING = (
    "おやすみなさい🌙\n"
    ".\n.\n.\n.\n.\n.\n.\n.\n"
    "#福岡撮影会 #被写体モデル\n"
    "#ポートレート #portrait\n"
    "#香乃ほのか @b_palette_p"
)
