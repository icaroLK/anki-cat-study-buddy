# 🐱︎ Cat Study Buddy ᗢᘏᓗ

- **pet_name**: your cat's name (default "Mochi").
- **pet_color**: one of `classical` (cream), `orange`, `grey`, `white`.
- **pet_color_random**: when true, `pet_color` is re-rolled to a random one of the four each time Anki starts (and immediately when you check the box in settings). The color dropdown is disabled while this is on. Default false.
- **mood_neutral_at**: cards/day where mood moves from Sad to Neutral (default 50).
- **mood_happy_at**: cards/day where mood moves from Neutral to Happy (default 100).
- **mood_excited_at**: cards/day where mood moves from Happy to Excited (default 200).
- **sprite_size**: how big the cat renders, in pixels (default 100).
- **show_during_review**: mini cat in the corner during reviews (default true).
- **show_mood_bar**: show the mood label, bar, and today's card count (default true).

## Animation categories
- **neutral**: idle, idle2, waiting, laydown, sleep
- **sad**: cry, sad
- **happy**: excited, dance, surprised
- **actions**: sleepy, bathtub, eating, box1, box2, box3
- **exaggerated**: sick1, sick2, dead

Mood ladder → category: 
Empty = exaggerated
Sad = sad
Neutral = neutral
Happy = neutral + actions
Excited = happy.

## In-review mini cat
While reviewing, the cat sits idle (one of **neutral**) between cards. On every answer it reacts for 2 seconds, then returns to idle:
- **Good / Hard / Easy** → one of **happy**
- **Again** → one of **exaggerated** or **sad**